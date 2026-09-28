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

- タイトル: Conventional Commits 形式で書く（例: `feat: ユーザーログインを実装`）
- 本文: 以下のテンプレートを基本とする

```markdown
## Summary
- 何を変えたか（1-3 個の箇条書き）

## Test plan
- [ ] 動作確認の手順
- [ ] 自動テストの結果
```

`gh pr create` を使い、本文は HEREDOC で渡す。

### レビュー & マージ

- 1 PR = 1 トピック。複数の関心事は分割する
- レビュー承認後にマージする
- マージ戦略は **Merge commit**（`--no-ff` 相当、PR の存在が履歴に残る）
  - Squash や Rebase は使わない（コミット粒度を保ちたいため）
- マージ後に作業ブランチを削除する（GitHub の "Automatically delete head branches" を有効化推奨）

### マージ後の同期

ローカルの `main` を最新化してから次の作業ブランチを切る:

```sh
git switch main
git pull --ff-only
git switch -c feat/<next-task>
```

## コミットの粒度

**1 コミット = 1 機能単位（または 1 修正単位）** を原則とする。レビューと bisect のしやすさを担保するため。

### 推奨される分け方

- 「機能 A の追加」と「無関係なリファクタ」は別コミット
- 「DB マイグレーション」と「アプリ側の対応コード」は別コミット（マイグレーション単独で適用できる状態を保つ）
- 「実装」と「テスト追加」は同じコミットでよい（同一機能の一部とみなす）
- 「フォーマット修正」「依存更新」のような雑多な変更は機能コミットに混ぜず、`style:` / `chore:` で独立させる

### 避ける書き方

- `WIP` / `fix typo` / `update` のような曖昧な単発コミットを `main` ブランチ向け PR に残す
- 1 つのコミットに複数の Conventional Commits type が混在する（例: 機能追加とリファクタを同時）
- 100 ファイル超の巨大コミットに「全部入り」で詰め込む

### 作業途中の細かいコミットの整理

ローカルで `WIP` 的なコミットを重ねるのは自由。PR を出す前に `git rebase -i` で機能単位に再構成する（公開済みブランチでなければ履歴改変 OK）。

```sh
# 作業ブランチをローカル整理
git rebase -i main
# その後 push
git push origin <branch>
```

## コミットメッセージ規則: Conventional Commits

形式: `<type>(<scope>): <subject>`

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

- **本文・件名は日本語**（このユーザーの基本言語が日本語のため）
- 件名は 72 文字以内、末尾にピリオドを付けない
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

これらは user の明示的な指示があるときのみ可。

## GitHub 操作

- 認証済み `gh` CLI を使う（アカウント: taito-station）
- PAT をファイルにハードコードしない
- リポジトリ操作の前にデフォルトブランチを `gh repo view --json defaultBranchRef` で確認する
