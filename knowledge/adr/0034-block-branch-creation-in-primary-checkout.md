# primary の checkout での作業ブランチの作成を main-commit-guard で止め、着手を worktree にする

## ステータス

Accepted — 2026-11-08

## 背景と課題

next-issue skill の手順 5 は、「`/resolve-issue N` は main から切った worktree で始める（他セッションと clone を共有しているときは、元の clone のブランチを切り替えない）」と定めていた。2026-11-07 のセッションでは、#111 と #109 を primary の checkout（clone の本体の作業ツリー。`git rev-parse --git-dir` と `--git-common-dir` が同じもの）でブランチを切り替えて対応した。#109 では、別のセッションが同じリポジトリの worktree で #108 を作業中だと把握しながら「primary を使っているのは自分だけ」と判断して外れ、ユーザーに指摘された。2026-10-18 には、別のセッションに primary のブランチを切り替えられ、作業中の checkout が別ブランチになった前例もある（#52 の対応中）。

primary のブランチを切り替えると、同じ clone を使う他のセッションの作業ツリーを書き換え、未コミットの変更を巻き込む。hve-playbook の primary は `~/.claude` の symlink 先でもあり（ADR 0020 の結果）、切り替えるとライブの設定も変わる。規則を文書や memory に書くだけでは、モデルが自分の判断で例外にするのを止められなかった。

あわせて、規則どうしが食い違っていた。branching.md の「作業開始時の手順」と resolve-issue の Step 3 は、今の作業ツリーで `git switch -c` するよう案内し、next-issue の「worktree で始める」と並び立っていた。main-commit-guard の deny message と branching.md は、main 上で作った変更を `git switch -c` で退避するよう案内していた。

## 意思決定の要因

- 規則から外れる余地を、モデルの判断に残さない（Issue #117）
- ADR 0020・0033 の方針に沿う（Bash の hook はこれ以上増やすなら統合を検討する、誤操作の防止が目的で迂回への防御ではない、hook を外す手段は設けない）
- ADR 0020 で却下した「同じコマンド内のブランチの切り替えを追う」と同じく、追う形が次々に増える静的解析にしない
- 正規の手順（デフォルトブランチへの切り替えと pull、post-merge-cleanup の `switch --detach`、`git worktree add`、remote の無い一時リポジトリでの作業）を止めない
- 規則の正本を branching.md の 1 つにする

## 検討した選択肢

- 適用範囲: remote を持つリポジトリすべて（並走 clone を含む）／他の worktree が既にあるリポジトリだけ／起動したリポジトリだけ
- 止める操作: 新しいブランチの作成だけ／既存ブランチへの切り替えも
- 切り替えた後の状態: hook では扱わない／警告を出す（SessionStart・UserPromptSubmit・PreToolUse）
- 逃げ道: `# via:primary-branch-ok: <理由>` を設ける／設けない
- 置き場所: main-commit-guard に追加する／新しい hook を足す
- main 上の未コミットの変更の退避: タグ付きの stash で worktree へ移す／default ブランチ上に変更があるときだけ primary での `git switch -c` を通す／via を付けた `git switch -c`

## 決定内容

選択した選択肢: **remote を持つリポジトリの primary の checkout での新しいブランチの作成を main-commit-guard で止め、SessionStart で primary が作業ブランチにいれば警告する。着手は worktree で始め、main 上の未コミットの変更はタグ付きの stash で worktree へ移す**。質問票の回答（`qa/primary-branch-switch-guard-questionnaire.md`）と、Plan の敵対的レビューの反映（Issue #117 のコメント）による。

- **止める操作**（`hooks/main-commit-guard.py`、PreToolUse・matcher `Bash`）
  - 判定するリポジトリ（main への commit と同じく `git -C`・`cd`・`env -C`・payload の `cwd`）が primary の checkout で、remote を持ち、HEAD がコミットを指すときの、新しいブランチを作るオプション: `git switch` の `-c`・`-C`・`--create`・`--force-create`・`--orphan`、`git checkout` の `-b`・`-B`・`--orphan`。短いオプションをまとめた形（`-qb`）と値を詰めた形（`-cfeat/x`）を含み、`--` の後ろは見ない
  - primary の判定は `git rev-parse --path-format=absolute --git-dir --git-common-dir` の 2 つが同じこと。並走 clone（parallel-setup）もそれぞれの clone の primary として止める。共有されているかは hook から判定できず、条件付きにすると「今は自分だけ」と判断して外れる余地が残るため
  - 止めないもの: 既存ブランチへの切り替え（`git switch <名前>`・`git checkout <名前>`・`gh pr checkout`）、デフォルトブランチへの切り替え、ファイルの復元（destructive-guard の担当）、`--detach`、`git worktree add -b`、worktree の中、remote の無いリポジトリ、unborn の HEAD（worktree を作る基点が無い。ADR 0023 の初回 commit の状況）
  - 止める理由が重なったら、main への commit → 起動したリポジトリ以外への書き込み → primary でのブランチの作成の順に示す（他のリポジトリに worktree の手順を案内しないため）
  - 逃げ道は `# via:primary-branch-ok: <理由>`（理由必須）。書式と有効な位置は `# via:main-commit-ok:` と同じで、他の判定には効かない
  - deny の message で、リポジトリのトップレベルを `-C` に渡した `git worktree add --no-track -b <branch> .claude/worktrees/<名前> origin/<default>` → EnterWorktree の `path`、main 上の変更の退避手順を案内し、`git branch` と `git switch` の 2 手に分けて回避しないよう書く
  - SessionStart の警告に埋め込むブランチ名は JSON の文字列としてエスケープし（非 ASCII・引用符・バックスラッシュ・制御文字。fork の PR の head など、リポジトリの外から決まるブランチ名をモデルの文脈にそのまま入れないため）、100 文字で切る。primary のパスはホームを `~` に置き換える
  - 警告は「自分の判断で戻さない。戻す必要があれば、他のセッションが使っていないかをユーザーに確かめてから戻す」と案内する（primary を切り替えたセッションが戻さずに終わったときの回復の経路）
- **警告**（同じ hook、SessionStart・matcher `startup|resume|clear`）
  - 起動したリポジトリ（`CLAUDE_PROJECT_DIR`、無ければ payload の `cwd`）の primary の checkout（`git worktree list --porcelain` の先頭。worktree のセッションでも primary を見る）が remote を持ち、デフォルトブランチ（`refs/remotes/origin/HEAD` の先、無ければ main と master）以外のブランチにいれば、標準出力に「primary を戻したり切り替えたりせず、worktree で作業する」警告を出す。常に exit 0
  - SessionStart の標準出力がモデルの文脈に入ることは、公式ドキュメント（hooks guide）で確かめた。PreToolUse の `additionalContext` は公式ドキュメントで確かめられず、`permissionDecision: "allow"` で理由を渡す方法は許可の確認そのものを飛ばすので採らない
- **規則の正本**: branching.md の「作業開始時の手順」に、worktree で始める手順（primary にいるとき・worktree の中にいるとき）、hook と via、main 上の変更の退避手順（`git status --porcelain` で確かめ、自分の変更だけを `git stash push -u -m <タグ> -- <パス>` → `git worktree add` → worktree で `git stash apply <SHA>` → タグで探し直して drop。自分が作ったと言い切れない変更は移さずユーザーに確認する。素の `git stash pop` は使わない。apply が衝突したら止まって報告）、Docker Compose（Laravel Sail を含む）のリポジトリで worktree に stack を立てる手順を書く。resolve-issue（Step 0・Step 1・Step 3）・next-issue（手順 5）・commit-workflow・hve-implement と implement-flow の Step 0・hve-akm・apply-hve-playbook（手順 3）・git-push-merged-pr-check の message はそれを参照する。hve-implement・implement-flow（rules/hve と rules/global/workflow は同じ行を保つ）・hve-akm は導入先に配り、hook は配らないので、hook のことは書かず「ブランチ運用規約に作業開始の手順があればそれに従い、無ければ並走するセッションと共有しうるときは worktree に切る」と書く（ADR 0020 と同じ。user-level では branching.md があるので、実質的に常に worktree になる）
  - worktree は `origin/<default>` を基点にし、`--no-track` を付ける（付けないと追跡先が `origin/<default>` になり、素の `git push` が名前の不一致で失敗する。`push.default=upstream` ではデフォルトブランチへ push される）
  - 着手のために primary を切り替えたり pull したりしない。resolve-issue の Step 1 は `git fetch origin` だけにし、worktree を作るまでのコードと knowledge の読み取りは `origin/<default>` の内容で行う。Step 0 は primary の checkout では未コミットの変更を理由に stash・commit を求めない。primary の更新は post-merge-cleanup の条件（primary が `<default>` にいて変更が無く、同じリポジトリを扱う他のセッションがいない）に委ねる
  - Docker Compose（Laravel Sail を含む）で動かすリポジトリも対象に含め、worktree に stack を立ててテストする（PR のセルフレビューでのユーザーの判断。primary で立てた stack は primary の作業ツリーを見るので、worktree の変更を検証しない）。worktree には ignore された `.env`・`vendor/`・`node_modules/` が無いので、`.env` をコピーして依存を入れ直す。project 名は常に `<リポジトリ名>-<worktree の名前>` にして `docker compose -p` で渡し（コピーした `.env`・compose ファイルの `name:`・セッションの環境変数は primary と同じ名前になるため）、`up` の前に primary と違うことを確かめる。片付けは `-v` を付けない `down` のあと、worktree の project の volume だけを確かめて消す。ポートは primary と同時に立てるときに分ける。parallel-setup・resolve-issue・create-pr はこの手順を参照する
- 契約は `tests/test_main_commit_guard.sh` の P 系列（止める・通す・via・優先順位）と S 系列（SessionStart）で固定する

### 結果（Consequences）

- 良い結果: primary の checkout で作業ブランチを作ることが、モデルの判断によらず止まる。規則が「primary はデフォルトブランチのまま、作業は worktree」の 1 つになり、branching.md・resolve-issue・next-issue の食い違いが解消する。他のセッションに primary を切り替えられた状態にも、次のセッションの開始時に気づける
- 悪い結果・既知の限界:
  - 判定はオプションだけで行う。`gh pr checkout`（`-b` で名前を付ける形を含む）、origin にだけあるブランチの名前での `git switch <名前>`（git が推測でローカルブランチを作る）、`--track`、`git stash branch`、`git branch <名前>` と `git switch <名前>` の 2 手に分けた形、長いオプションの省略形（`--cre`）、git の alias（`git co -b`）は、primary にブランチを作って切り替えても止まらない。既存ブランチへの切り替えを止めないと決めた（質問票の Q2）ことと、ADR 0020 の「追う形を増やさない」方針による。目的は誤操作の防止で、迂回への防御ではない。primary を切り替えた後の状態は SessionStart の警告で補う
  - hve-playbook の primary で `gh pr checkout` などをすると、`~/.claude` のライブの設定が別ブランチ版になる（review-pr skill の注意と同じ）。これは止めず、次のセッションの開始時の警告で気づく
  - 警告は SessionStart の 1 回だけで、セッションの途中で他のセッションが primary を切り替えても、そのセッションでは気づけない
  - 並走 clone（parallel-setup）でも、着手は worktree になる
  - Docker Compose・Sail のリポジトリでは、worktree ごとに stack を立てる手間（`.env` のコピー・依存の入れ直し・migrate と seed・ポートの調整）とディスク・メモリが増える。worktree で stack を立てる手順は実機で検証していない雛形で、プロジェクトの起動手順があればそちらに合わせる
  - submodule の作業ツリーは git-dir と git-common-dir が同じなので primary と判定され、remote とコミットがあれば止まる（submodule の中で作業ブランチを作るときは via を付けるか、submodule の worktree を使う）
  - `git worktree add` で作った worktree は lock されない（EnterWorktree の `name` で作ったものは lock される）。post-merge-cleanup は `path` で入った worktree を、マージ済みの PR・変更が無いこと・祖先であることで判定するので、片付けは変わらない
  - 導入先（apply-hve-playbook の手順 3）でも、remote があれば worktree に作業ブランチを切る。導入先で `.claude/worktrees/` が ignore されていなければ、作業ブランチで `.gitignore` に足す
  - main 上の変更の退避は 1 手（`git switch -c`）から stash を使う数手になる。stash は全 worktree と並走するセッションで共有されるので、タグと SHA で自分の stash だけを扱う
  - main-commit-guard が SessionStart でも動くので、SessionStart ごとに git の呼び出しが 3 回前後増える
  - 決定内容のうち ADR 0020 の B の「main 上で作った変更は `git switch -c` で退避してから commit する」は、primary の checkout ではこの ADR の退避手順に置き換わる（ADR 0020 のステータス節に書く）。ADR 0023 の「コミットして」のときに作業ブランチへ退避してから commit する決定は、退避の手段を定めていないので変わらない

## 選択肢の評価（Pros and Cons）

### remote を持つリポジトリすべてに適用する（採用）

#### メリット

- 共有の有無を hook が判定しなくて済み、モデルが例外にする余地が無い

#### デメリット

- 1 つのセッションだけが使う並走 clone や導入先でも、worktree で始める手間が増える

### 他の worktree が既にあるリポジトリだけに適用する

#### メリット

- worktree を使っていない clone の作業の流れを変えない

#### デメリット

- worktree の無い primary を 2 つのセッションが同時に使う状況を止められない。条件から外れる余地が残る

### 起動したリポジトリだけに適用する

#### メリット

- 導入先や別のリポジトリでの作業を変えない

#### デメリット

- 並走 clone や、`git -C` で触る別の clone の primary を止められない

### 新しいブランチの作成だけを止める（採用）

#### メリット

- `git checkout <x>` がブランチかパスかを判定しなくてよく、静的解析が単純になる。他人の PR の確認などの読み取りの切り替えを止めない

#### デメリット

- 既存ブランチへの切り替え、作成のオプションを使わずにブランチを作る形は止まらない（結果の限界のとおり）

### 既存ブランチへの切り替えも止める

#### メリット

- primary の HEAD を動かす操作をすべて止められる

#### デメリット

- 確認のための切り替えも止まる。`git checkout <x>` のブランチとパスの区別、DWIM、`gh pr checkout` などを追う必要がある（ユーザーの判断で不採用）

### SessionStart で警告する（採用）

#### メリット

- モデルの文脈に渡る経路が公式ドキュメントで確かめられている。git の呼び出しはセッションの開始時の数回で済む

#### デメリット

- セッションの途中の切り替えには気づけない

### UserPromptSubmit で警告する

#### メリット

- セッションの途中の切り替えにも気づける

#### デメリット

- primary が作業ブランチにいる間、発言のたびに同じ警告が出る

### PreToolUse で警告する

#### メリット

- git の操作の直前に気づける

#### デメリット

- 止めずにモデルへ文を渡す方法（`additionalContext`）を公式ドキュメントで確かめられない。`permissionDecision: "allow"` は許可の確認を飛ばす

### main-commit-guard に追加する（採用）

#### メリット

- Bash の python hook を増やさない。`git -C`・`cd`・`env -C`・サブシェルの追跡と via の判定を共有できる（ADR 0033 と同じ理由）

#### デメリット

- hook の名前（main への commit）と役割がさらに離れる

### 新しい hook を足す

#### メリット

- 名前と役割が一致する

#### デメリット

- python hook が 6 本目になり、追跡の処理を二重に持つ（ADR 0033 で却下した理由と同じ）

### タグ付きの stash で worktree へ移す（採用）

#### メリット

- primary の HEAD を動かさずに未コミットの変更を移せる。規則が「primary は動かさない」の 1 つで済む

#### デメリット

- 手数が増える。origin のデフォルトブランチを基点にするので、ローカルの `main` が遅れていると apply が衝突しうる（止まって報告する）

### default ブランチ上に変更があるときだけ primary での `git switch -c` を通す

#### メリット

- 退避が 1 手のまま

#### デメリット

- 変更があるかどうかで判定が分かれ、#109 と同じ状況（main 上で作業を始める）をそのまま通しうる

### via を付けた `git switch -c` で退避する

#### メリット

- 手順を変えずに済む

#### デメリット

- via が日常の手順になり、ユーザーの明示的な指示のときだけという逃げ道の意味が薄れる

## 関連リンク

- Related: [0020-gate-plan-headings-and-main-commit-with-hooks](0020-gate-plan-headings-and-main-commit-with-hooks.md)（main-commit-guard の導入。退避の手順の一部をこの ADR で置き換える）
- Related: [0023-via-scope-for-commit-instruction-and-skill-enforcer](0023-via-scope-for-commit-instruction-and-skill-enforcer.md)
- Related: [0033-block-writes-outside-launched-repository](0033-block-writes-outside-launched-repository.md)
- Related: [hve-playbook#117](https://github.com/taito-station/hve-playbook/issues/117)
