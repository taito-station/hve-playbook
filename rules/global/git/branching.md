# Git ブランチ運用規約

すべてのプロジェクトに適用するブランチ・PR・コミット運用の規約。GitHub Flow をベースとする。

## ブランチ戦略: GitHub Flow

- **`main`** が常にデプロイ可能な唯一の長命ブランチ
- 作業は `main` から短命の作業ブランチを切る
- PR でレビュー → `main` にマージ → 作業ブランチ削除
- `develop` / `release/*` / `hotfix/*` のような長命補助ブランチは作らない

### 作業開始時の手順

`main` で直接コミット・push しない（`main` を常にデプロイ可能に保つため、変更は PR でレビューしてからマージする）。開発業務で git を使うときは、コードを書き始める前に作業ブランチを切る。

```sh
# 作業開始の標準手順
git switch main
git pull --ff-only
git switch -c <type>/<short-kebab-description>
```

すでに `main` で変更を作ってしまった場合は、`git switch -c <branch>` で作業ブランチへ退避してから commit する（`main` には残さない）。

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

ローカルの `main` を最新化してから次の作業ブランチを切る:

```sh
git switch main
git pull --ff-only
git switch -c feat/<next-task>
```

## PR とコミットの粒度

**1 PR = 1 機能単位（または 1 修正単位）** を原則とする。まだ push していないブランチは、create-pr skill が PR を作る前に 1 コミットにまとめる（`git reset --soft <base>` + `git commit`）ので、未 push のブランチから作った PR は 1 コミットになる。レビューと bisect のしやすさを担保するため。

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
