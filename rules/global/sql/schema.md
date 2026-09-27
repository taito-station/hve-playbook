---
paths:
  - "**/*.sql"
  - "**/migrations/**/*.sql"
---

# SQL スキーマ設計・命名規約

PostgreSQL を対象とするスキーマ設計と命名規約。`migrations.md` と `queries.md` に併せて読むこと。

## 前提

- DB エンジンは **PostgreSQL** を前提とする。MySQL/SQLite は対象外
- `gen_random_uuid()` を使う場合は `pgcrypto` 拡張を有効化する

## 命名規則

| 対象 | 規則 | 例 |
|---|---|---|
| テーブル | `snake_case`、複数形 | `users`, `recipe_ingredients` |
| カラム | `snake_case` | `created_at`, `user_id` |
| 主キー | `id` 単一カラム固定 | `id` |
| 外部キー | `{参照テーブル単数}_id` | `user_id`, `recipe_id` |
| インデックス | `idx_{table}_{cols}` | `idx_users_email` |
| ユニーク制約 | `uq_{table}_{cols}` | `uq_users_email` |
| CHECK 制約 | `ck_{table}_{rule}` | `ck_users_age_non_negative` |
| 外部キー制約 | `fk_{table}_{column}` | `fk_recipes_user_id` |
| 中間テーブル | `{a}_{b}`（アルファベット順、両方単数） | `recipe_tag` |

予約語との衝突を避けるため、テーブル名・カラム名は `user`/`order` 等の単独使用を避け、複数形またはプレフィックスを付ける。

## 型ポリシー

| 用途 | 推奨型 | 備考 |
|---|---|---|
| 主キー | `BIGSERIAL` または `UUID DEFAULT gen_random_uuid()` | UUID は分散・推測困難性が必要なケース |
| 文字列 | `TEXT` + `CHECK (char_length(col) <= N)` | `VARCHAR(N)` は使わない |
| 真偽値 | `BOOLEAN` | NULL を避けたい場合は NOT NULL DEFAULT false |
| 整数 | `INTEGER` / `BIGINT` | 金銭は `NUMERIC` を使う |
| 金額・厳密小数 | `NUMERIC(precision, scale)` | 例: `NUMERIC(12, 2)` |
| 時刻 | `TIMESTAMPTZ` | `TIMESTAMP` (without time zone) は使わない |
| 日付 | `DATE` | |
| 列挙 | `CREATE TYPE ... AS ENUM` または `TEXT` + `CHECK (col IN (...))` | アプリ側 enum と必ず同期 |
| JSON | `JSONB` | `JSON` は使わない |

## NOT NULL 既定

- カラムは原則 **NOT NULL** で宣言する。NULL 許容は意味的に必要な場合のみ
- 文字列の「空文字」と「NULL」は区別しない設計を基本とし、未設定は NULL ではなく空文字またはデフォルト値で表す（または NOT NULL のまま）

## 標準カラム

すべてのテーブルに以下を必ず含める:

```sql
id          BIGSERIAL PRIMARY KEY,
created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
```

論理削除を採用するテーブルのみ追加:

```sql
deleted_at  TIMESTAMPTZ
```

`updated_at` の自動更新はアプリケーション層で行う（トリガー乱立を避ける）。

## 外部キーと ON DELETE 戦略

外部キーは必ず明示的な `ON DELETE` 戦略を持つ:

| 戦略 | 用途 |
|---|---|
| `ON DELETE CASCADE` | 親が消えれば子も無意味になる関連（例: `users` → `user_settings`） |
| `ON DELETE RESTRICT` | 子が存在する間は親を消させない（既定） |
| `ON DELETE SET NULL` | 親消失でも子は残すが参照を外す。子側 FK カラムは NULL 許容必須 |

`ON DELETE NO ACTION` は使わない（暗黙の RESTRICT と紛らわしい）。

## 中間テーブル（多対多）

```sql
CREATE TABLE recipe_tag (
    recipe_id  BIGINT NOT NULL REFERENCES recipes(id) ON DELETE CASCADE,
    tag_id     BIGINT NOT NULL REFERENCES tags(id)    ON DELETE CASCADE,
    PRIMARY KEY (recipe_id, tag_id)
);
```

- テーブル名はアルファベット順、両方単数で連結（`recipe_tag` であって `recipes_tags` ではない）
- 主キーは合成キー
- 両方の FK 列にインデックスが必要なため、合成 PK のカラム順とは別に逆向きの個別インデックスも追加検討

## インデックス指針

- **すべての外部キー列にインデックスを張る**（PostgreSQL は FK で自動作成しない）
- 検索条件・ソートに使うカラムにインデックスを張る
- 複合インデックスは「等価条件で使うカラム → 範囲条件・ソートで使うカラム」の順
- ユニーク制約は `UNIQUE` で宣言する（自動的にインデックスが作られる）
- 大量行のテーブルへの追加は `CREATE INDEX CONCURRENTLY`（詳細は `migrations.md`）

## DDL の書き方

```sql
CREATE TABLE users (
    id          BIGSERIAL PRIMARY KEY,
    email       TEXT        NOT NULL,
    name        TEXT        NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT uq_users_email           UNIQUE (email),
    CONSTRAINT ck_users_email_non_empty CHECK  (char_length(email) > 0),
    CONSTRAINT ck_users_name_length     CHECK  (char_length(name) BETWEEN 1 AND 50)
);

CREATE INDEX idx_users_created_at ON users (created_at DESC);
```

- 列の縦位置を揃えて読みやすくする
- 制約は `CONSTRAINT` 名を必ず付ける（命名規則に従う）
- インデックスは `CREATE TABLE` の外で個別に作成する（マイグレーション分割しやすいため）
