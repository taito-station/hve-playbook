# Git ブランチ運用規約

すべてのプロジェクトに適用するブランチ・PR・コミット運用の規約。GitHub Flow をベースとする。

## ブランチ戦略: GitHub Flow

- **`main`** が常にデプロイ可能な唯一の長命ブランチ
- 作業は `main` から短命の作業ブランチを切る
- PR でレビュー → `main` にマージ → 作業ブランチ削除
- `develop` / `release/*` / `hotfix/*` のような長命補助ブランチは作らない

### 作業開始時の手順

`main` で直接コミット・push しない（`main` を常にデプロイ可能に保つため、変更は PR でレビューしてからマージする）。開発業務で git を使うときは、コードを書き始める前に作業ブランチを切る。

作業ブランチは worktree に切る。primary の checkout（clone の本体の作業ツリー。`git rev-parse --git-dir` と `--git-common-dir` が同じもの）のブランチは切り替えず、デフォルトブランチのまま使う。primary は並走するセッション（同じ clone の worktree で動くものを含む）と共有されうるうえ、`~/.claude` の symlink 先にもなっているので、ブランチを切り替えると他のセッションの作業ツリーや設定を書き換えてしまう。並走 clone（parallel-setup）も、それぞれの clone の primary として同じに扱う。空いているように見えても、自分の判断で例外にしない（ADR 0034）。

```sh
# primary の checkout から始めるとき（リポジトリのトップレベルで実行する）
git fetch origin
git worktree add --no-track -b <type>/<short-kebab-description> .claude/worktrees/<名前> origin/<default>
# Claude Code では、続けて EnterWorktree の path にこのパスを渡して移る

# すでに worktree の中にいるとき（EnterWorktree の name で作った worktree など）
git fetch origin
git switch --no-track -c <type>/<short-kebab-description> origin/<default>
```

- `<default>` はデフォルトブランチ（`git rev-parse --abbrev-ref origin/HEAD` の `origin/` を外したもの。無ければ main / master）。worktree は `origin/<default>` を基点にするので、着手のために primary を切り替えたり pull したりしない。primary の更新は post-merge-cleanup skill の条件（primary が `<default>` にいて変更が無く、同じリポジトリを扱う他のセッションがいない）に委ねる
- `--no-track` を付ける。付けないと作業ブランチの追跡先が `origin/<default>` になり、素の `git push` が名前の不一致で失敗する（`push.default=upstream` ではデフォルトブランチへ push される）
- worktree の置き場所は、リポジトリのトップレベルの `.claude/worktrees/<名前>`（EnterWorktree と同じ）。`.claude/worktrees/` を `.gitignore` に入れる
- 既存ブランチの確認（他人の PR など）は、worktree か `git show` / `git diff` で行うのが望ましい。primary で切り替えた場合は、自分の作業が終わったら戻す。他のセッションが切り替えた primary は自分の判断で戻さず（自分は worktree で続ける）、戻す必要があれば、他のセッションが使っていないかをユーザーに確かめてから戻す
- Docker Compose（Laravel Sail を含む）で動かすリポジトリでは、primary で立ち上げた stack は primary の作業ツリーを見ているので、worktree の変更を検証しない。テスト・ブラウザテストは worktree に立てた stack で行う（下の「worktree で Docker Compose の stack を立てる」）
- remote の無いリポジトリ（`git init` 直後や検証用の一時リポジトリ）と、コミットの無いリポジトリ（worktree を作る基点が無い）は、この節の対象外で、従来どおり `git switch -c` でよい

primary の checkout での `git switch -c|-C|--create|--force-create|--orphan` と `git checkout -b|-B|--orphan` は hook（main-commit-guard）が止める（remote が無い・コミットが無いリポジトリは対象外）。ユーザーが primary での作業を明示的に指示したときだけ、コマンド中のコメントで `# via:primary-branch-ok: <理由>` を付ける。hook はオプションだけで判定するので、`git branch <名前>` と `git switch <名前>` の 2 手に分けて回避しない。セッションの開始時に primary がデフォルトブランチ以外にあれば、同じ hook が警告を出す。

すでに `main` で変更を作ってしまった場合は、作業ブランチへ退避してから commit する（`main` には残さない）。

- primary の checkout では、自分の未コミットの変更だけを stash で worktree へ移す。primary は並走するセッションやユーザーと共有されうるので、先に `git status --porcelain` で変更を確かめ、自分が作ったと言い切れない変更は移さずにユーザーに確認する。stash は全 worktree と並走するセッションで共有されるので、タグを付けて自分の stash だけを扱い、素の `git stash pop` は使わない

  ```sh
  # リポジトリのトップレベルで実行する
  git stash push -u -m "<固有のタグ>" -- <自分が変えたパス>...
  git stash list --format='%H %gs' | grep "<固有のタグ>"   # 自分の stash の SHA を控える
  git worktree add --no-track -b <type>/<short-kebab-description> .claude/worktrees/<名前> origin/<default>
  git -C .claude/worktrees/<名前> stash apply <控えた SHA>
  # apply が成功したら、タグで今の stash@{n} を探し直して git stash drop stash@{n}
  ```

  apply が衝突したら（ローカルの `main` が origin より遅れていたときなど）、解消を試みずに止まってユーザーに報告する（stash は drop せずに残す）
- worktree の中・remote の無いリポジトリ・コミットの無いリポジトリでは、`git switch -c <branch>` で退避してよい

#### worktree で Docker Compose の stack を立てる

Docker Compose（Laravel Sail を含む）で動かすリポジトリで worktree に着手したら、テストの前に worktree に stack を立てる（手順は未検証の雛形。プロジェクトの README・CLAUDE.md に起動の手順があればそれに合わせる）。

- worktree には ignore された `.env`・`vendor/`・`node_modules/` が無い。`.env` は primary からコピーし（秘密情報を含むのでコミットしない）、依存は worktree で入れ直す（`composer install`・`npm ci` など。Sail なら `vendor/bin/sail` が入るまではコンテナの外で入れる）
- worktree の stack は、primary の stack を止めているときも含めて常に primary と別の project 名にする。名前は `<リポジトリ名>-<worktree の名前>` とし、compose を叩くたびに `docker compose -p <名前>` で渡す（Sail は `.env` を読むので、worktree の `.env` の `COMPOSE_PROJECT_NAME` に書く）。コピーした `.env` の `COMPOSE_PROJECT_NAME`、compose ファイルの `name:`、セッションの環境変数（parallel-setup の `settings.local.json` の env。`.env` より優先される）は primary と同じ名前になるので、`-p` の無い素の `docker compose` は使わない（インラインの `COMPOSE_PROJECT_NAME=… docker compose` は sail-env-inline-block hook が止める）
- `up` の前に `docker compose -p <名前> config | grep '^name:'` で、project 名が primary の名前（primary で `docker compose config` が返す名前）と違うことを確かめる。同じなら実行せずに止まる
- primary の stack と同時に立てるときは、ホストに公開するポート（Sail なら `APP_PORT`・`FORWARD_DB_PORT` など）をずらす。DB の volume は project 名ごとに分かれるので、migrate・seed をやり直す
- テスト（`docker compose exec` / `sail test` など）とブラウザテストは worktree の stack に対して行う。primary の stack のコンテナで `docker exec` すると、primary の作業ツリーを検証してしまう
- 作業が終わったら、worktree を片付ける前に worktree の stack を止めて消す（`docker compose -p <名前> down`。parallel-setup のとおり `-v` は付けない）。残った volume は `docker volume ls --filter label=com.docker.compose.project=<名前>` で worktree の project のものだけであることを確かめてから、`docker volume rm` で消す

`main` / `master` 上の `git commit` は hook（main-commit-guard）が止める（remote の無いリポジトリは対象外）。ユーザーが `main` への commit を明示的に指示したときだけ、コマンド中のコメントで `# via:main-commit-ok: <理由>` を付ける。「コミットして」だけでは `main` への明示的な指示に当たらないので、remote を持つリポジトリでは作業ブランチへ退避してから commit し、切ったブランチ名を報告する。作業ブランチへの退避と commit は別の Bash 呼び出しで実行する（hook は実行前の HEAD で判定するので、1 つのコマンドにつなぐと止まる）。

## ブランチ命名規則

`<type>/<short-kebab-description>` の形式。`<type>` は Conventional Commits の type と揃える。

| パターン | 用途 |
|---|---|
| `feat/<desc>` | 新機能 |
| `fix/<desc>` | バグ修正 |
| `refactor/<desc>` | リファクタ |
| `chore/<desc>` | ビルド・依存・設定など |
| `docs/<desc>` | ドキュメント |
| `test/<desc>` | テスト追加・修正 |

例: `feat/user-login`, `fix/jwt-expiry-validation`, `chore/bump-actix-web`

Issue 番号と紐づける場合は `feat/123-user-login` の形にする。

## PR ベースの進め方

`main` への直 push は禁止。すべての変更は PR 経由でマージする。

### PR 作成

- タイトル: コミットメッセージと同じ形式で書く（既定は Conventional Commits。例: `feat: ユーザーログインを実装`）
- 本文: 以下のテンプレートを基本とする

```markdown
## Summary
- 何を変えたか（1-3 個の箇条書き）

## Test plan
- [ ] 動作確認の手順
- [ ] 自動テストの結果
```

`gh pr create` を使い、本文は一時ファイルに書いて `--body-file` で渡す（create-pr skill の手順に従う）。

### レビュー & マージ

- 1 PR = 1 トピック。複数の関心事は分割する
- レビュー承認後にマージする
- マージ戦略は **Merge commit**（`--no-ff` 相当、PR の存在が履歴に残る）
  - Squash や Rebase は使わない（PR の単位を merge commit として履歴に残すため）
- マージ後に作業ブランチを削除する（GitHub の "Automatically delete head branches" を有効化推奨）

### マージ後の同期

作業ブランチと worktree を片付け、ローカルの `main` を最新化する（post-merge-cleanup skill の手順）。次の作業ブランチは、「作業開始時の手順」のとおり worktree に切る。

## PR とコミットの粒度

**1 PR = 1 機能単位（または 1 修正単位）** を原則とする。まだ push していないブランチは、create-pr skill が PR を作る前に 1 コミットにまとめる（`git reset --soft <base>` + `git commit`）ので、未 push のブランチから作った PR は 1 コミットになる。レビューと bisect のしやすさを担保するため。例外として、HVE の knowledge の検査スクリプトがあるリポジトリで、squash によって knowledge 文書の `distilled_from_sha` が指すコミットが履歴から外れたときは、create-pr が sha の追従コミットを 1 つ積むので 2 コミットになる（ADR 0014）。このようなリポジトリでは、PR を merge commit でマージする（squash・rebase merge では追従した sha が main から辿れなくなる）。

### 推奨される分け方

- 「機能 A の追加」と「無関係なリファクタ」は別 PR
- 「DB マイグレーション」を単独で適用する必要があるなら、「アプリ側の対応コード」とは別 PR（マイグレーション単独で適用できる状態を保つ）
- 「実装」と「テスト追加」は同じ PR でよい（同一機能の一部とみなす）
- 「フォーマット修正」「依存更新」のような雑多な変更は機能の PR に混ぜず、`style:` / `chore:` の PR として独立させる

### 避ける書き方

- 1 つの PR に複数の type の変更を混ぜる（例: 機能追加とリファクタを同時）
- 100 ファイル超の巨大な PR に「全部入り」で詰め込む

### 作業途中の細かいコミット

ローカルで `WIP` 的なコミットやレビュー対応のコミットを重ねるのは自由（未 push なら PR 作成時に 1 コミットにまとまる）。

push 済みのブランチはコミットを畳まない（公開済みのコミットを保つため）。そのまま複数コミットで PR にするので、`WIP` / `fix typo` のような曖昧な件名のコミットは push する前に避ける。push 済みの履歴を書き換えてよいのは、禁止事項の例外に当たる場合だけ。

## コミットメッセージ規則: Conventional Commits

形式: `<type>(<scope>): <subject>`

既存のコミット履歴に別の形式（`[カテゴリ] 概要` など）や別の言語があるプロジェクトでは、コミットメッセージと PR タイトルをその形式・言語に合わせる。履歴が無い・混在している場合は、この節の Conventional Commits と下の規約に従う。この節がコミット形式の正本で、commit-workflow skill はこれに従う。

| type | 用途 |
|---|---|
| `feat` | 新機能の追加 |
| `fix` | バグ修正 |
| `refactor` | 振る舞いを変えないコード整理 |
| `perf` | パフォーマンス改善 |
| `docs` | ドキュメントのみの変更 |
| `test` | テストの追加・修正 |
| `style` | フォーマット・空白等（コード意味は変えない） |
| `chore` | ビルド・依存更新・設定など |
| `ci` | CI 設定変更 |
| `build` | ビルドシステムの変更 |
| `revert` | 過去のコミットの取り消し |

### 規約

- 本文・件名はプロジェクトの言語で書く（このユーザーのリポジトリでは日本語。既存履歴があればその言語に合わせる）
- 件名（= PR タイトル）は 70 文字以内、末尾にピリオドを付けない
- 破壊的変更は `feat!:` のように `!` を付けるか、本文に `BREAKING CHANGE:` を含める
- scope は省略可。プロジェクト内のレイヤー名やモジュール名を入れる（例: `feat(auth): JWT検証を追加`）

例:
```
feat(auth): メール+パスワードログインを追加
fix(repository): ユーザー検索時の NULL 取り扱いを修正
chore: actix-web を 4.12 系に更新
refactor!: Repository トレイトの命名を変更
```

## 禁止事項

- `main` への直 push
- `git push --force` / `--force-with-lease` を共有ブランチに対して実行（自分の作業ブランチでも user に確認してから）
- `--no-verify` で pre-commit / pre-push フックをスキップ
- 公開済みコミットへの `--amend` や履歴改変
- `git reset --hard` で他人の変更を吹き飛ばすこと

これらは user の明示的な指示があるときのみ可。例外として、create-pr skill が push 済みの作業ブランチを base に rebase したあと、fetch 前に固定したリースで `--force-with-lease` するのは確認なしで行ってよい（他人のコミットを上書きしないため）。

## GitHub 操作

- 認証済み `gh` CLI を使う（アカウント: taito-station）
- PAT をファイルにハードコードしない
- リポジトリ操作の前にデフォルトブランチを `gh repo view --json defaultBranchRef` で確認する

### 起動したリポジトリ以外には書き込まない

Claude Code を起動したリポジトリ（同じ origin の worktree・並走 clone を含む）以外には、ユーザーの明示的な指示がない限り書き込まない（ADR 0033）。

- 書き込みに含むもの: 他のリポジトリ（作業ツリーとその remote・GitHub 上のリポジトリ）への PR・Issue・コメント・ラベル・リリースの作成と変更、commit・push、fork とリポジトリの作成、ファイルの編集
- 書き込みに含まないもの: `~/.claude` の memory・plans・handoff と scratchpad、検証のために自分で作った remote の無い一時リポジトリ、skill の手順が定める書き込み先（update-config の `~/.claude/settings.json`、learn の vault、setup.sh の導入先など。ユーザーの指示でその skill を使うとき）
- 読み取り（参照のために他のリポジトリのコードや Issue を読む）はしてよい
- 作業の途中で他のリポジトリ（上流・vendor 元・依存先など）に直すべき点を見つけたら、自分で PR・Issue・push をしない。ユーザーに報告し、出すかどうかを委ねる。knowledge や決定ログに「還元するかは未決」のような記述があっても、自分で決めない
- 「PR 作って」「コミットして」の指示は、起動したリポジトリへの指示として読む。他のリポジトリへの指示とは読まない
- hook（main-commit-guard）が、他のリポジトリへの commit・push と `gh` の書き込みを止める。ユーザーが明示的に指示したときだけ、コマンド中のコメントで `# via:other-repo-ok: <理由>` を付ける
