---
paths:
  - "**/*.rs"
  - "**/Cargo.toml"
---

# Rust クリーンアーキテクチャ規約

このルールは Rust + Actix-web でバックエンド API を構築するときの規約。`ttm-bros/fridgers-backend` をリファレンスとする。

## レイヤー構造と依存方向

依存方向は **Apps → Interface → Use-Case → Domain**。逆方向の依存を作らない。

```
src/
├── apps/<bin-name>/         # バイナリ層（HTTPサーバー、DI構築）
├── interface/
│   ├── rest-controller/     # REST APIアダプター（handler/router/schema）
│   └── rdb-gateway/         # DBアダプター（Repositoryトレイトの実装）
├── use-case/                # ビジネスロジック（Repositoryトレイト定義 + Interactor）
├── domain/                  # コアエンティティと値オブジェクト
└── infrastructure/
    └── config/              # 環境変数ベースの設定
```

## 各レイヤーの責務

### Domain (`src/domain/`)
- エンティティと値オブジェクトのみ。**外部依存なし**（`uuid`/`chrono`/`strum_macros` 程度に限定）
- バリデーションは値オブジェクトの `TryFrom<String>` 実装に集約
- 文字列バリデーションは `define_string!` マクロで統一（`conventions.md` 参照）
- ドメインエラーは `InvalidFormat` / `InvalidLengthRange` のみに留める

### Use-Case (`src/use-case/`)
- フレームワークから独立。Actix-web 等の依存を持ち込まない
- `Repository` トレイトを定義（実装は Interface 層）
- `Interactor<R: Repository>` 構造体にビジネスロジックを実装
- DTO は `dto/{entity}/{action}/request.rs` `response.rs` に配置
- 各ユースケースは `interactor/{entity}/{action}.rs` で `impl<R: Repository> Interactor<R>` のメソッドとして定義
- `Error` enum は HTTP ステータスコードに対応（`InvalidArgument`/`Unauthorized`/`Forbidden`/`NotFound`/`AlreadyExist`/`PreconditionFailed`/`ExternalServer`）
- `domain::Error` から `use_case::Error` への `From` 実装で変換

### Interface (`src/interface/`)
- **rest-controller**: Actix-web の `handler` / `router` / `schema` を分離
  - `handler/{entity}.rs`: HTTPハンドラ。Interactor を呼ぶだけ
  - `router/{entity}.rs`: ルーティング設定（`pub fn configure<R: Repository>(cfg: &mut ServiceConfig)`）
  - `schema/{entity}/{action}/request.rs` `response.rs`: API スキーマ（serde derive）
  - `error/mod.rs`: HTTP 用 `Error` enum + `ResponseError` 実装。use-case Error からの `From` 変換
- **rdb-gateway**: `Repository` トレイト実装
  - `dto/{entity}.rs`: DB行をドメインモデルに変換する DTO（`TryFrom<Row> for Entity`）
  - `repositories/{entity}.rs`: テーブル単位の SQL 実装

### Apps (`src/apps/<bin-name>/`)
- HTTP サーバーの起動と DI 構築のみ
- `setup.rs`: ロガー初期化、`PgPool` → `PostgresRepository` → `Interactor<PostgresRepository>` の組み立て
- `app.rs`: ルート設定 (`fn configure_routes<R: Repository + 'static>`)
- `bin.rs`: エントリポイント

### Infrastructure (`src/infrastructure/config/`)
- `dotenvy` で `.env` 読み込み
- `envy` でプレフィックス付き環境変数を構造体にマッピング（`LOG_*`/`SERVER_*`/`AUTH_*` 等）
- `Config::from_env() -> Result<Self>` を提供

## エラーマッピング

```
use_case::Error               → HTTP Status
─────────────────────────────────────────
InvalidArgument         → 400
Unauthorized            → 401
Forbidden               → 403
NotFound                → 404
AlreadyExist            → 409
PreconditionFailed      → 412
ExternalServer          → 500
```

各レイヤーが独自の `Error` enum と `Result<T>` 型エイリアスを持ち、`From` 実装で上位レイヤーへ変換する。

## 新リソース追加時のファイル作成手順

`{Entity}` を新しいエンティティ名に置換して以下を作成（`mod.rs` / `lib.rs` への宣言追加を忘れない）。

1. **Domain**: `src/domain/src/{entity}/` — エンティティ本体 (`mod.rs`)、値オブジェクト (`{entity}_id.rs`, `{entity}_name.rs` 等)
2. **Use-Case DTO**: `src/use-case/src/dto/{entity}/{action}/` — `request.rs` / `response.rs`
3. **Use-Case Interactor**: `src/use-case/src/interactor/{entity}/{action}.rs` — `impl<R: Repository> Interactor<R>` にメソッド追加
4. **Repository トレイト**: `src/use-case/src/repository.rs` にメソッド追加（`save_*`/`find_*_by_id`/`update_*`/`delete_*` 等）
5. **RDB Gateway 実装**: `src/interface/rdb-gateway/src/repositories/{entity}.rs` — SQL 実装
6. **RDB DTO**: `src/interface/rdb-gateway/src/dto/{entity}.rs` — DB 行のマッピング (`TryFrom`)
7. **REST Schema**: `src/interface/rest-controller/src/schema/{entity}/{action}/` — `request.rs` / `response.rs`
8. **REST Handler**: `src/interface/rest-controller/src/handler/{entity}.rs`
9. **REST Router**: `src/interface/rest-controller/src/router/{entity}.rs` — `pub fn configure<R: Repository>` を公開
10. **Migration**: `deployments/db/migrations/` — リバーシブル形式 (`.up.sql` / `.down.sql`)

## 認証

認証が必要な場合は fridgers-backend の `src/use-case/src/auth.rs` パターンを踏襲:
- パスワードは `argon2` でハッシュ化（ランダムソルト）
- JWT は `jsonwebtoken` で発行（Claims: `sub`/`exp`/`iat`）
- `JwtConfig { secret, expiry_hours }` を `Interactor` が保持
- 環境変数は `AUTH_JWT_SECRET` / `AUTH_JWT_EXPIRY_HOURS`

## 参考リポジトリ

具体実装は https://github.com/ttm-bros/fridgers-backend を参照。
