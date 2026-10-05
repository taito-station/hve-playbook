# hve-playbook 適用プロンプト

他のリポジトリに hve-playbook（HVE 設計手法の rules / skills / agents / workflows）を導入するときに、そのリポジトリの Claude Code セッションへ渡すプロンプト。

## 使い方

導入したいリポジトリで Claude Code を開き、次の 1 行を送る（`<hve-playbook>` は hve-playbook を clone した場所。例: `~/workspace/hve-playbook`）。

```
<hve-playbook>/docs/prompts/apply-hve-playbook.md を読んで、このリポジトリに hve-playbook を適用して
```

以下の「手順」は、このファイルを読んだ Claude が実行する内容。

---

## 手順（このファイルを読んだ Claude が実行する）

### 前提

- 対象は、いま開いているリポジトリのルート（`git rev-parse --show-toplevel`）。以下 `<target>` と書く。
- 配置は hve-playbook の `setup.sh` が行う。手作業でファイルをコピーしない（再実行で hve-playbook の版に揃えられるようにするため）。
- `setup.sh` が変更するのは次のとおり。
  - `<target>/.claude/rules/hve/`・`skills/hve-*`・`agents/hve-*.md`・`workflows/hve-*.js` を**削除してから**置き直す。
  - `<target>/.claude/rules/hve-local/`（プロジェクト固有の補足）には触れない。書式は `.claude/rules/hve/local-overrides.md`。
  - `<target>/.claude/CLAUDE.md` が無ければ、HVE 方法論をそのまま `.claude/CLAUDE.md` として作る。あれば `.claude/CLAUDE.md` は変えず、`.claude/CLAUDE.hve.md` を作る・上書きする。
  - `<target>/docs/` を作る（空のディレクトリ）。
  - cq/mdq が未導入なら、`HypervelocityEngineering` を使用中の Python 環境に `pip install -e` する。環境変数 `HVE_REPO_PATH` の場所か hve-playbook の隣のディレクトリに既存の clone があればそれを使い、無ければ `dahatake/HypervelocityEngineering` を hve-playbook の隣に `git clone` する。
  - user-level の設定（`~/.claude`）は変えない（`<target>/.claude` 配下に symlink が無い場合。手順 2 で確かめる）。
- Bash ツールはコマンドごとにシェルの状態を引き継がない。手順 1 で決めた hve-playbook の絶対パスは、以降のコマンドに毎回そのまま書き込む（以下 `<hve-playbook>` と書く）。

### 1. hve-playbook の場所と状態を確かめる

- 場所: 読み込んだこのファイル（`<hve-playbook>/docs/prompts/apply-hve-playbook.md`）のあるディレクトリの 2 つ上を第一候補にする。`<hve-playbook>/setup.sh` があることを確かめる。
  - 見つからなければ、`~/.claude/CLAUDE.md` の symlink 先のディレクトリを候補にする（sync-dotclaude.sh を使っている場合）。
  - それでも見つからなければ、ユーザーに尋ねる。
- 状態: `setup.sh` は hve-playbook の**作業ツリー**をそのままコピーする。次を確かめる。
  - `git -C <hve-playbook> status -sb`
  - `git -C <hve-playbook> fetch -q && git -C <hve-playbook> status -sb`
- 次の場合は、そのまま適用してよいかユーザーに確認する（配置される中身がデフォルトブランチの最新と違うため）。
  - デフォルトブランチ以外にいる
  - 未コミットの変更がある
  - 上流より遅れている

### 2. 対象リポジトリの状態を確かめる

- git 管理下でなければ、`git init` してよいかユーザーに確認する。
- 追跡済みファイルに未コミットの変更（`git -C <target> status --short --untracked-files=no`）があれば、先にコミットか stash をしてもらう。setup.sh は未コミットの編集を上書きし、git では復元できないので、そのままでは進めない。
- 次のものがあるかを確かめる。
  - `.claude/rules/hve/`（あれば再適用。その旨をユーザーに伝えてから進める）
  - `.claude/CLAUDE.md`・`.claude/CLAUDE.hve.md`・ルートの `CLAUDE.md`
- **symlink を確かめる**: `find <target>/.claude -maxdepth 2 -type l`（`<target>/.claude` 自体が symlink かも `test -L` で確かめる）。symlink があれば、setup.sh はリンク先（リポジトリの外や `~/.claude` の場合もある）で削除・上書きを行い、git の検出もすり抜ける。リンク先を示してここで止め、ユーザーに確認する。
- **git 管理外の HVE 資産を守る**: 未追跡のファイル（ignore されているものも、単に未コミットのものも）は、`setup.sh` が削除・上書きすると git で復元できない。`git -C <target> ls-files --others -- .claude` で未追跡のファイルをすべて列挙する（除外指定を付けないので ignore されたものも出る）。
  - 前提に挙げた削除対象（`rules/hve/`・`skills/hve-*`・`agents/hve-*.md`・`workflows/hve-*.js`）か `.claude/CLAUDE.hve.md` が含まれていれば、`setup.sh` の前に `<target>/work/hve-backup-<日時>/` へ同じ相対パスでコピーして退避する。
- cq/mdq が導入済みかを確かめる（`python3 -m cq --help` と `python3 -m mdq --help` が両方とも成功するか）。
  - 未導入なら、`setup.sh` が `pip install -e`（既存の clone が無ければ外部リポジトリの `git clone` も）を行うことをユーザーに伝え、了承を得てから進める。
  - 了承が得られなければ、ここで止めて報告する（`setup.sh` には導入を省く方法が無い）。

### 3. 作業ブランチを切る

- コミットがあれば、`chore/apply-hve-playbook` を切る（リモートの有無は問わない）。リモートがあれば、先にデフォルトブランチを pull して最新にする。同名のブランチがあれば、末尾に日付を付ける。ブランチ運用規約があればそれに従う。
- `git init` した直後などでコミットが無い場合は、ブランチは切らずにデフォルトブランチ上で進める。

### 4. setup.sh を実行する

```bash
bash <hve-playbook>/setup.sh <target>
```

出力を確認する。

- 出力で CLAUDE.md の扱いを確かめる（手順 5 の分岐に使う）。
  - `[INFO] CLAUDE.md を配置しました`: `.claude/CLAUDE.md` を新しく作った
  - `[WARN] ... CLAUDE.hve.md として配置しました`: `.claude/CLAUDE.hve.md` を新しく作った
  - `[INFO] CLAUDE.hve.md を最新版で更新しました`: `.claude/CLAUDE.hve.md` を上書きした
- 再適用で、git 管理下の HVE 資産に独自の変更があった場合は、`git -C <target> diff` で上書きされた差分を示す。写しには戻さず、`.claude/rules/hve-local/` に移すかどうかをユーザーに確認する（標準に取り込まれた内容なら移さず捨てる）。
- 手順 2 で退避したファイルがあれば、置き直された版と `diff -r` で比べ、独自の変更を同じく hve-local に移すかどうかをユーザーに確認する。
- `.claude/rules/hve-local/` があれば、標準の変更（`git -C <target> diff -- .claude/rules/hve .claude/skills`）と見比べ、hve-local の見出しが指す節が標準に実在し、「上書き」節が追従しているかを確かめる。
- cq/mdq の導入に失敗しても `grep`/`find` にフォールバックして動く。失敗した場合は、その旨を報告に書く。

### 5. CLAUDE.md を整える

`.claude/CLAUDE.hve.md` は Claude Code に自動では読み込まれない。HVE 方法論の原本（次回の適用で差分を見る基準）として残し、git 管理する。

- `.claude/CLAUDE.md` が新しく作られた場合（HVE 方法論がそのまま入る）は、内容はそのままでよい。次回の差分の基準にするため、`cp <hve-playbook>/CLAUDE.hve.md <target>/.claude/CLAUDE.hve.md` で原本も置く（次回の setup.sh は「更新」の分岐に入る）。
- `.claude/CLAUDE.hve.md` が新しく作られた場合（`.claude/CLAUDE.md` が既にあった）は、その内容を `.claude/CLAUDE.md` に差分マージする。
  - 既存の記述は書き換えない。HVE の方法論・出力ディレクトリ構造などの節を足す。
  - 既に取り込み済みの節がある場合は、重複させない。
- `.claude/CLAUDE.hve.md` が更新された場合（再適用）は、まず `.claude/CLAUDE.md` に HVE の節（方法論・出力ディレクトリ構造など）が入っているかを確かめる。入っていなければ（以前の運用で `CLAUDE.hve.md` だけが置かれ、マージされていなかった場合など）、「新しく作られた場合」と同じく全体を差分マージする。入っていれば、`git -C <target> diff -- .claude/CLAUDE.hve.md` で hve-playbook 側の変更点を確認し、その差分だけを `.claude/CLAUDE.md` に反映する。未追跡だった場合は、手順 2 で退避したコピーと `diff` を取る。
- ルートに `CLAUDE.md` がある場合は、両方が読み込まれる。`.claude/CLAUDE.md` と食い違っていないか確認する。
- どの場合も、既存の記述と食い違う点（出力先ディレクトリ・言語・規約など）は推測で片方に寄せず、質問票にしてユーザーに確認する（各設問に推奨案と理由を添える）。

### 6. git 管理の方針

- `.claude/` の HVE 資産（`CLAUDE.hve.md` を含む）は git 管理する。プロジェクト固有の調整と、適用した hve-playbook の版を履歴に残すため。
- `.claude/` が ignore されている場合は、HVE 資産を ignore の例外にするかをユーザーに確認する。
  - 例外にすると、既存の `.claude/CLAUDE.md` も中身ごと git 管理に入り、リモートに push される。意図して非公開にしていた可能性があるので、確認のときにそのことを伝える。コミット前に、秘密情報・内部 URL・個人情報が含まれていないかを確かめる。含まれていれば、`.claude/CLAUDE.md` は例外から外し、HVE の節の置き場所（ルートの `CLAUDE.md` など）を質問票で確認する。
  - 除外がリポジトリの `.gitignore` ではなく `.git/info/exclude` や global の excludes にある場合は、その場所をユーザーに伝えて扱いを確認する。
  - git は除外されたディレクトリの中を `!` で戻せないので、`.claude/` の行は残したまま、その後ろに次の行を足す（`!.claude/rules/hve/` を足すだけでは効かない）。先頭の `/` で対象をルートの `.claude/` に限り、下層の `.claude/`（モノレポのパッケージなど）は ignore したままにする。

  ```gitignore
  !/.claude/
  /.claude/*
  !/.claude/CLAUDE.md
  !/.claude/CLAUDE.hve.md
  !/.claude/rules/
  /.claude/rules/*
  !/.claude/rules/hve/
  !/.claude/rules/hve-local/
  !/.claude/skills/
  /.claude/skills/*
  !/.claude/skills/hve-*/
  !/.claude/agents/
  /.claude/agents/*
  !/.claude/agents/hve-*.md
  !/.claude/workflows/
  /.claude/workflows/*
  !/.claude/workflows/hve-*.js
  ```
- `.gitignore` に次が無ければ足す。
  - `work/`（HVE の一時作業ファイル。手順 2 の退避先もここ）
  - `**/.claude/settings.local.json`
  - `docs/temp/`（create-pr / review-pr skill の一時ファイル。skill を使わない場合も足してよい）
  - `**/.mdq/*` と `!**/.mdq/config.toml`、`**/.cq/*` と `!**/.cq/config.toml`（mdq / cq のローカル索引と利用記録。実行したディレクトリに作られるので全階層に当てる。設定ファイルは追跡できるよう中身だけを除外する）。既に `.mdq/`・`.cq/`（ディレクトリ指定）があれば、追記ではなくこの行に置き換える（ディレクトリごと除外すると `!` の例外が効かない）

### 7. 検証する

- 配置されたファイルを一覧で確認する（`find <target>/.claude -maxdepth 2 | sort`）。
- `.claude/rules/hve/implement-flow.md` などの規則ファイルが揃っているか確認する。
- `git -C <target> status --short -uall` で、HVE 資産（`CLAUDE.hve.md` を含む）・`.claude/rules/hve-local/`（あれば）・CLAUDE.md・`.gitignore` が変更または untracked として見えることを確認する。見えなければ ignore の例外が効いていない。 逆に、それ以外のファイル（下層の `.claude/` や独自の設定）が新しく見えるようになっていれば、例外が広すぎるので直す。
- `git -C <target> check-ignore -v --no-index .mdq/usage.jsonl` が `.gitignore` の行を返し、`git -C <target> check-ignore --no-index .mdq/config.toml` が何も返さない（exit 1）ことを確認する。返らなければ、索引の除外か `config.toml` の例外が効いていない。
- コミットにはこれらだけを含める。無関係な変更はステージしない（破棄はしない。破棄が必要ならユーザーに確認する）。

### 8. コミットして PR にする

- リモートがあれば PR にする。create-pr skill があれば使い、無ければ `gh pr create` を使う。
- リモートが無い（`git init` 直後など）場合は、コミットまでで止め、リモートをどうするかをユーザーに確認する。
- PR 本文（またはコミットメッセージ）には次を書く。
  - 適用した hve-playbook の版（`git -C <hve-playbook> rev-parse --abbrev-ref HEAD` と `git -C <hve-playbook> describe --always --dirty`）
  - 配置したもの
  - CLAUDE.md のマージ内容
  - 手順 2 の退避・質問票で確認した事項

### 9. 次の一手を伝える

- 新規プロジェクトや要件定義から始める場合は、`/hve-ard` で ARD（要件定義）を始める。
  - 引数: 企業名、対象事業（任意）
- 既存コードの改修が中心の場合は、`.claude/rules/hve/implement-flow.md` などの規律が自動で適用される。
  - 今後の設計判断は `knowledge/adr/` に記録する（決定ログをインライン方式で運用しているプロジェクトは、`.claude/rules/hve-local/artifact-management.md` で宣言して各 knowledge の `## 決定ログ` 節に記録する）。
- 詳しい使い方は `<hve-playbook>/docs/usage-prompts.md` を参照する。
