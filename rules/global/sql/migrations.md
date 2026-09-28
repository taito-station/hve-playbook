---
paths:
  - "**/deployments/db/migrations/**/*.sql"
  - "**/migrations/**/*.sql"
---

# SQL マイグレーション運用規約

PostgreSQL + sqlx-cli ベースのマイグレーション運用規約。Rust + sqlx プロジェクトを主対象とする。

> Laravel プロジェクトでは `php artisan make:migration` 経由のマイグレーションを使う（`~/.claude/rules/php/composer.md` 参照）。本ファイルの規約は **生 SQL マイグレーション** のみを対象とする。

## ツールとファイル形式

- **sqlx-cli** を使う。`cargo install sqlx-cli --no-default-features --features postgres`
- **リバーシブル形式** を必須とする（`sqlx migrate add -r <name>`）
- ファイル配置: `deployments/db/migrations/`（Rust 規約 `architecture.md` と整合）
- ファイル名: `{timestamp}_{name}.up.sql` と `{timestamp}_{name}.down.sql` のペア
  - 例: `20260425120000_create_users.up.sql` / `20260425120000_create_users.down.sql`

## 基本原則

### 1 マイグレーション 1 目的

1 ファイルで複数の関心事を扱わない。「テーブル追加」と「データ移行」と「制約追加」は別マイグレーションに分ける。

### `down` で完全に巻き戻せること

`up` で行ったすべての変更を `down` で取り消せること。`DROP TABLE IF EXISTS` で済ますのではなく、列追加なら列削除、制約追加なら制約削除を明示的に書く。

```sql
-- 20260425120000_add_users_email_unique.up.sql
ALTER TABLE users ADD CONSTRAINT uq_users_email UNIQUE (email);
```

```sql
-- 20260425120000_add_users_email_unique.down.sql
ALTER TABLE users DROP CONSTRAINT uq_users_email;
```

### 冪等性は基本的に求めない

sqlx は適用済みマイグレーションを管理するため、`IF NOT EXISTS` を機械的に付ける必要はない。ただし以下のケースでは推奨:

- 既存環境への初回適用で衝突する可能性があるとき → `CREATE TABLE IF NOT EXISTS`
- ロールバックの安全性を高めたいとき → `DROP TABLE IF EXISTS`（down 側）

## DDL の安全運用

### インデックス追加（本番）

大規模テーブルへのインデックス追加は `CONCURRENTLY` を付ける（通常の `CREATE INDEX` は書き込みをロックするため）。ただし `CONCURRENTLY` はトランザクション外でしか実行できないため、マイグレーションファイルを分けるか、`-- sqlx:no-transaction` を使う。

```sql
-- 20260425120000_add_recipes_user_id_index.up.sql
-- sqlx:no-transaction
CREATE INDEX CONCURRENTLY idx_recipes_user_id ON recipes (user_id);
```

```sql
-- 20260425120000_add_recipes_user_id_index.down.sql
-- sqlx:no-transaction
DROP INDEX CONCURRENTLY IF EXISTS idx_recipes_user_id;
```

### NOT NULL 化（既存テーブル）

既存テーブルへの NOT NULL 列追加は段階的に行う:

1. NULL 許容で列追加（DEFAULT 付き）
2. 既存行を backfill（別マイグレーション）
3. NOT NULL 制約を付与（別マイグレーション）

新規テーブルの作成と同時の NOT NULL 列は通常通り 1 マイグレーションで OK。

### 列の型変更

- 互換性のある型変更（`INTEGER` → `BIGINT` 等）は `ALTER COLUMN` で直接可能
- 互換性のない型変更は「新列追加 → backfill → 旧列削除 → リネーム」の段階を踏む

## 命名規約

| 用途 | プレフィックス | 例 |
|---|---|---|
| テーブル作成 | `create_{table}` | `create_users` |
| テーブル削除 | `drop_{table}` | `drop_legacy_logs` |
| 列追加 | `add_{table}_{column}` | `add_users_phone_number` |
| 列削除 | `drop_{table}_{column}` | `drop_users_phone_number` |
| 制約追加 | `add_{table}_{constraint_name}` | `add_users_email_unique` |
| インデックス追加 | `add_{table}_{column}_index` | `add_recipes_user_id_index` |
| データ移行 | `backfill_{table}_{column}` | `backfill_users_full_name` |

## 適用前チェックリスト

PR 作成前に確認:

- [ ] `up.sql` と `down.sql` が両方存在する
- [ ] ローカルで `sqlx migrate run` → `sqlx migrate revert` → `sqlx migrate run` を 1 サイクル試した
- [ ] `down.sql` が `up.sql` の変更を完全に巻き戻している（手動で確認）
- [ ] 大規模テーブルへの DDL がある場合、`CONCURRENTLY` などの本番安全策が取られている
- [ ] アプリケーションコードと **後方互換** を保っている（マイグレーション適用後にデプロイ前のアプリが動くか）
- [ ] スキーマ規約 `schema.md` の命名・型ポリシーに従っている

## マイグレーションとアプリのデプロイ順序

ゼロダウンタイムを前提にする場合の基本順序:

1. **マイグレーション先行**: 列追加・制約緩和・新テーブルなど、旧アプリと互換のある変更
2. **アプリのデプロイ**: 新スキーマを使うコードに更新
3. **マイグレーション後追い**: 旧列削除・制約強化など、新アプリでないと壊れる変更

`down.sql` はあくまで開発時のロールバック用であり、本番ではフォワードオンリーの追加マイグレーションで対応するのが安全。

## トラブルシュート

- マイグレーションが途中で失敗した場合は `sqlx migrate info` で適用状況を確認する
- 適用済みマイグレーションのファイル内容を **後から書き換えない**（チェックサム不整合になる）。修正したい場合は新しいマイグレーションを追加する
