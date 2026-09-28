---
paths:
  - "**/*.sql"
  - "**/repositories/**/*.rs"
---

# SQL クエリスタイル・トランザクション規約

PostgreSQL を対象とする DML / SELECT のスタイルとトランザクション・整合性の規約。Rust の `interface/rdb-gateway/` 配下のインライン SQL も対象とする。

## クエリスタイル

### 整形ルール

- **予約語は大文字**（`SELECT`, `FROM`, `WHERE`, `JOIN` 等）
- カラム名・テーブル名は小文字
- インデント 4 スペース、句ごとに改行
- 列は 1 行 1 カラム（短い場合は同一行可）

```sql
SELECT
    u.id,
    u.email,
    u.name,
    COUNT(r.id) AS recipe_count
FROM users AS u
LEFT JOIN recipes AS r
    ON r.user_id = u.id
WHERE u.created_at >= $1
GROUP BY u.id, u.email, u.name
ORDER BY u.created_at DESC
LIMIT $2;
```

### `SELECT *` 禁止

`SELECT *` は禁止。必要な列を明示的に列挙する。

- 理由: スキーマ変更時の意図しない影響、N+1 や転送量の肥大化、`FromRow` derive とのカラム順依存問題
- 例外: `EXISTS (SELECT 1 FROM ...)` のような存在確認のみ

### `AS` でエイリアスを明示

テーブルエイリアス・カラムエイリアスには `AS` を書く。`u users` のような暗黙エイリアスは禁止。

### JOIN 種別を明記

`JOIN` 単独ではなく `INNER JOIN` / `LEFT JOIN` / `RIGHT JOIN` を明示する。`RIGHT JOIN` は原則使わず `LEFT JOIN` で書き直す。

## パラメータバインド

### プレースホルダ必須

ユーザー入力を含むクエリは **必ず** `$1, $2` 形式のプレースホルダを使う。文字列連結や `format!()` での SQL 組み立ては禁止。

```rust
// OK
sqlx::query_as::<_, UserRow>("SELECT id, email, name FROM users WHERE email = $1")
    .bind(email)
    .fetch_optional(&pool)
    .await?;

// NG（SQL インジェクション）
let q = format!("SELECT id, email, name FROM users WHERE email = '{}'", email);
```

### IN 句の動的な要素数

要素数が動的な `IN` 句は `ANY($1)` を使う:

```sql
SELECT id, name FROM users WHERE id = ANY($1)
```

```rust
.bind(&ids)  // Vec<i64> 等
```

## トランザクション

### 複数書き込みは必ずトランザクション

複数行の INSERT/UPDATE/DELETE が業務上アトミックであるべき場合は必ずトランザクションで括る。

```rust
let mut tx = pool.begin().await?;
sqlx::query("INSERT INTO orders (...) VALUES (...)").execute(&mut *tx).await?;
sqlx::query("INSERT INTO order_items (...) VALUES (...)").execute(&mut *tx).await?;
tx.commit().await?;
```

### 分離レベル

- 既定は **READ COMMITTED**（PostgreSQL のデフォルト）
- 重複登録を避ける、同一行の更新が並ぶケースは **SELECT ... FOR UPDATE** で行ロックを取る
- 集計結果の一貫性が必要なら明示的に `BEGIN ISOLATION LEVEL REPEATABLE READ` を指定

### 行ロックと UPSERT

#### `INSERT ... ON CONFLICT`

冪等な書き込みは `ON CONFLICT` で書く。アプリ側で「存在チェック → INSERT」をしない（競合する）。

```sql
INSERT INTO users (id, email, name)
VALUES ($1, $2, $3)
ON CONFLICT (email) DO UPDATE
    SET name = EXCLUDED.name,
        updated_at = now()
RETURNING id;
```

#### `SELECT ... FOR UPDATE`

更新対象を先に取得してから書き換える場合に使う:

```sql
SELECT id, balance FROM accounts WHERE id = $1 FOR UPDATE;
```

`FOR UPDATE SKIP LOCKED` はキューイング処理で他ワーカーと衝突を避けたいときに使う。

## 整合性

### 楽観ロック

長時間トランザクションを避けたい場合は `updated_at` または `version` カラムを使った楽観ロックを採用する:

```sql
UPDATE recipes
   SET title      = $1,
       updated_at = now()
 WHERE id         = $2
   AND updated_at = $3
RETURNING id;
```

`RETURNING` の結果が空ならコンフリクト発生として上位でエラーにする。

### 外部キーは DB 側で保証

アプリ側のチェックだけに頼らず、必ず外部キー制約と CHECK 制約を DB に置く。`schema.md` の規約に従って `FK` を貼ること。

## パフォーマンス

### `EXPLAIN ANALYZE`

新規クエリ・大量データを扱うクエリは `EXPLAIN ANALYZE` で実行計画を確認する。Seq Scan が想定外の箇所で出ていないか、想定インデックスが使われているかをチェック。

### N+1 回避

ループ内で個別クエリを発行しない:

```rust
// NG
for user in &users {
    let recipes = sqlx::query!("SELECT id FROM recipes WHERE user_id = $1", user.id)
        .fetch_all(&pool).await?;
}

// OK: 一括取得
let user_ids: Vec<_> = users.iter().map(|u| u.id).collect();
let recipes = sqlx::query_as::<_, RecipeRow>(
    "SELECT id, user_id, title FROM recipes WHERE user_id = ANY($1)"
).bind(&user_ids).fetch_all(&pool).await?;
```

### ページネーションは keyset 推奨

`OFFSET` ベースのページネーションは大きなページ番号で遅くなる。安定したソートキーがあるなら **keyset** を使う:

```sql
SELECT id, created_at, title
  FROM recipes
 WHERE (created_at, id) < ($1, $2)
 ORDER BY created_at DESC, id DESC
 LIMIT 20;
```

## sqlx 連携注記

Rust 規約 (`~/.claude/rules/rust/conventions.md`) との統一点:

- `query_as!` マクロは使わない（コンパイル時 DB 接続が必要なため）
- `query_as::<_, Row>(...)` 関数 + `FromRow` derive で型安全マッピングする
- DB 行 → ドメイン型の変換は `interface/rdb-gateway/src/dto/{entity}.rs` の `TryFrom<Row> for Entity` 実装に集約
