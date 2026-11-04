# 起動したリポジトリ以外への書き込みを、規則と main-commit-guard で止める

## ステータス

Accepted — 2026-11-04

## 背景と課題

2026-09-13、doc-query で作業していたローカルのセッションが、ユーザーの指示がないまま上流の HVE（dahatake/HypervelocityEngineering）に PR（dahatake/HypervelocityEngineering#4）を作った。GitHub と、ローカルの HVE の clone の reflog から確かめた流れは次のとおり（JST）。

- 08:55 fork（taito-station/HypervelocityEngineering）を作り、ローカルの HVE の clone で作業ブランチを切った
- 08:58 commit した（`Co-Authored-By: Claude`）
- 09:00 上流に PR を作った
- 09:02 doc-query の PR（taito-station/doc-query#29）で、決定ログ「上流に還元する」を事後に足した

doc-query の knowledge は、それまで「還元するかどうかは未決」としていた。決定ログは、その判断をモデルが「還元のタイミングが来た」として下した形になっており、ユーザーの指示や承認には触れていない。当日のセッション記録はローカルに残っておらず、会話の中の指示の有無までは確かめられない。

PR は 2026-11-03 に上流のメンテナーが閉じた。閉じられたこと自体は問題ではなく、相手のリポジトリにこちらの作業の中から意図せず PR を作ったことが問題だった。ユーザーの要望は「起動したリポジトリ以外での作業は、指示がない限り禁止」。

これまで、他のリポジトリへの書き込みを扱う規則も hook も無かった。

## 意思決定の要因

- 今回の事例（別のリポジトリでの fork・commit・push・PR）を機械的に止める
- 読み取り（参照のために他のリポジトリのコードや Issue を読む）は止めない（ユーザーの回答）
- 同じリポジトリの worktree・並走 clone・検証用の一時リポジトリでの正規の作業を誤って止めない
- ADR 0020 の方針に沿う（Bash の hook はこれ以上増やすなら統合を検討する、Edit・Write は止めない、hook を外す手段は設けない）
- 判定に失敗したときは Claude Code を止めない（fail-open）

## 検討した選択肢

- 規則の文面だけにする／規則と hook の両方にする
- 禁止の範囲: 書き込みだけ／読み取りも含める
- hook の置き場所: main-commit-guard を拡張する／新しい hook を足す
- 同じリポジトリの判定: origin の URL で比べる／パス（作業ツリーの場所）で比べる
- Edit・Write も hook で止める

## 決定内容

選択した選択肢: **規則と hook の両方にし、止めるのは書き込みだけ。hook は main-commit-guard を拡張し、同じリポジトリは origin の URL で判定する**。強制の仕方と範囲は、ユーザーの回答による。

- **規則**: 正本は `rules/global/git/branching.md` の「起動したリポジトリ以外には書き込まない」。CLAUDE.md の「進め方」に要約を 1 行置く（CLAUDE.md は全セッションで読み込まれるので、branching.md の該当節を読む前の判断にも効かせるため。hook の message は正本の節を指す）
  - 起動したリポジトリ（同じ origin の worktree・並走 clone を含む）以外には、ユーザーの明示的な指示がない限り書き込まない
  - 書き込みに含むもの: PR・Issue・コメント・ラベル・リリースの作成と変更、commit・push、fork とリポジトリの作成、ファイルの編集。`~/.claude` の memory・plans・handoff と scratchpad は除く
  - 他のリポジトリに直すべき点を見つけたら、ユーザーに報告して委ねる
- **hook**: `hooks/main-commit-guard.py`（PreToolUse、matcher `Bash`）に判定を足す
  - 起動したリポジトリは `CLAUDE_PROJECT_DIR` の origin。無い・リポジトリでない・origin が無いときは判定しない
  - 比べるのは host を除いた `owner/repo`（ssh の別名ホストの clone や GHE で、自分のリポジトリを止めないため）。セルフレビューでユーザーが決めた（F5: host の無い宛先は起動したリポジトリの host で補う、G4: host を含む宛先も owner/repo で比べる）。別の host に同じ owner/repo があるときは見分けない
  - 止めるもの:
    - `git commit`: 判定するリポジトリの origin が違うとき。判定するリポジトリは main の判定と同じく `git -C`・`cd`・`env -C` を追う（サブシェルの中の `cd` は外へ持ち出さない）。origin の無いリポジトリは通す
    - `git push`: 宛先の remote の push の URL が違うとき。remote は位置引数・`--repo`、無ければ git と同じく pushRemote → pushDefault → 追跡先 → origin の順で決める
    - `gh` の書き込み: 宛先が違うとき。対象は pr・issue・label・release・repo の作成と変更（エイリアスの `new` を含む）と、workflow・run・secret・variable・cache の書き込み。宛先は、引数の URL、`-R`・`--repo`、前置の `GH_REPO=`、`gh issue transfer` の移す先、無ければ gh の既定の宛先
    - gh の既定の宛先は gh と同じ決め方にする。remote を upstream → github → origin → その他の順に並べ、`remote.<name>.gh-resolved`（`gh repo clone`・`gh repo fork --clone`・`gh repo set-default` が付ける）の付いた remote、無ければ先頭の remote（端末に問い合わせられない Bash では、gh は先頭を選ぶ。cli/cli の `context/remote.go`・`context/context.go`）
    - fork の clone や upstream の remote を足した clone では親が既定の宛先になるので、親への `--repo` 無しの PR も止まる（セルフレビューの F6 でユーザーが決めた。今回の事例と同じ形を止めるため）。upstream の remote を持つリポジトリで起動したときも、`--repo` 無しの PR の作成は止まる（gh が実際に upstream へ PR を出すため）
    - `gh repo create`・`new`・`fork` は新しいリポジトリを作るので常に止める
    - `gh api` の書き込み: パスの `repos/<owner>/<repo>`（完全な URL を含む）が違うとき。`user/repos`・`orgs/<org>/repos` への POST も止める
  - 読み取りと `-h`・`--help` は通す。宛先にシェルの変数・コマンド置換を含むときは、値が分からないので判定しない
  - 逃げ道は `# via:other-repo-ok: <理由>`（理由必須）。main の `# via:main-commit-ok:` とは別で、片方でもう片方は通らない。コメントの中で他の via（`# via:create-pr` など）と並べてよい（main-commit-ok も同じ）
  - block の message は、規則の正本の小見出し「起動したリポジトリ以外には書き込まない」を指す。規則は branching.md の「GitHub 操作」の下に置いたまま（セルフレビューの F8 でユーザーが決めた）
- 契約は `tests/test_main_commit_guard.sh` で固定する（今回の事例の再現を含む）

### 結果（Consequences）

- 良い結果:
  - 今回の事例と同じ操作は、どれも実行前に止まる（別のリポジトリでの commit・push、上流への PR の作成、fork）
  - 同じリポジトリの worktree・並走 clone・remote の無い一時リポジトリでの作業と、他のリポジトリの読み取りは止まらない
- 悪い結果・既知の限界:
  - hook は Bash の `git` と `gh` だけを見る。他のリポジトリのファイルの Edit・Write と、`gh` 以外の手段（`curl` での API 呼び出しなど）は、規則の文面に頼る
  - org・アカウントへの書き込み（`gh secret set --org`・`gh variable set --org`・`gh gist create` など）は、リポジトリを宛先にしないので追わない
  - review-pr の fix モードで、他人の fork の PR のブランチに push するときも止まる（宛先が fork のため）。ユーザーが指示したときは via を付ける
  - `gh api graphql` の mutation は追わない（パスにリポジトリが無く、本文から宛先を決めるのは過剰。skill の手順にも graphql の書き込みは無い）
  - `git cherry-pick`・`merge`・`revert`・`am` など、commit 以外でコミットを作るサブコマンドは追わない。外へ出すのは push なので、そこで止まる（セルフレビューの F17 でユーザーが決めた）
  - main-commit-guard と同じ best-effort の静的判定で、Claude Code がふだん出す形を対象にする。変数・コマンド置換を介したパスやリポジトリ名は判定せずに通し、分割に失敗したコマンドも通す（ADR 0020 と同じく、限界は個別に列挙しない）
  - 起動したディレクトリが git リポジトリでないとき（`~/workspace` で起動したなど）は判定しない
  - Bash の呼び出しのうち `commit`・`push` を含むか、単語の `gh` を含むものは、main-commit-guard が解析に進むようになった。起動したリポジトリの origin を求める git の呼び出しは、書き込みの宛先が分かったときだけ行う
  - 目的は善意の誤操作の防止で、意図的な迂回への防御ではない（ADR 0020 と同じ）

## 選択肢の評価（Pros and Cons）

### 規則と hook の両方にする（採用）

#### メリット

- 今回の事例はモデルが自分で判断して起きたので、文面だけでは同じ判断を防げない。実行の時点で止められる

#### デメリット

- 誤検知の余地がある（同じリポジトリの判定を origin の URL にして抑える）

### 規則の文面だけにする

#### メリット

- 誤検知が無い

#### デメリット

- 守るかどうかがモデル次第で、今回の事例と同じ形の判断（knowledge の「未決」を自分で決める）を止められない

### 読み取りも禁止する

#### メリット

- 範囲が明快

#### デメリット

- 上流の同等の機能を確かめる、並走 clone の状態を見るなど、正規の調査が止まる（ユーザーの回答で採らない）

### 新しい hook を足す

#### メリット

- main への commit の判定と分けて読める

#### デメリット

- PreToolUse の Bash の python hook が 6 本目になり、Bash の呼び出しごとに python の起動が増える（ADR 0020 は、増やすなら統合を検討するとしている）
- `cd`・`git -C`・`env -C` の追跡を二重に持つことになる

### パスで同じリポジトリを判定する

#### メリット

- git の設定を読まずに済む

#### デメリット

- 同じリポジトリの worktree・並走 clone（ADR 0020 の「symlink 先の clone は main のまま使い、作業は worktree で行う」運用を含む）を別のリポジトリとして止めてしまう

### Edit・Write も hook で止める

#### メリット

- 他のリポジトリのファイルの編集も機械的に止められる

#### デメリット

- ADR 0020 で却下した方向。`~/.claude` の skill・rules は hve-playbook の作業ツリーへの symlink で、handoff・learn などの正規の書き込み先もあり、除外リストの保守が要る

## 関連リンク

- Related: [0020-gate-plan-headings-and-main-commit-with-hooks](0020-gate-plan-headings-and-main-commit-with-hooks.md)（main-commit-guard の元の決定。0020 の「main-commit-guard は `commit` を含まないコマンドではすぐ終わる」は、この ADR で `push`・`gh` を含むコマンドにも広がった。0020 の決定内容は変わらない）
- Related: [0023-via-scope-for-commit-instruction-and-skill-enforcer](0023-via-scope-for-commit-instruction-and-skill-enforcer.md)
- Related: [0007-consolidate-user-level-rules-and-agents](0007-consolidate-user-level-rules-and-agents.md)
- Related: [dahatake/HypervelocityEngineering#4](https://github.com/dahatake/HypervelocityEngineering/pull/4)（今回の事例）
- Related: [taito-station/doc-query#29](https://github.com/taito-station/doc-query/pull/29)（事後に足した決定ログ）
