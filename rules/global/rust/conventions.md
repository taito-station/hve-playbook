---
paths:
  - "**/*.rs"
---

# Rust コーディング規約

クリーンアーキテクチャ Rust プロジェクトでのコーディング規約。`architecture.md` と併せて読むこと。

## 標準トレイト優先

独自メソッドより標準トレイトを優先する。

- 値オブジェクトの構築は `TryFrom<String>` で実装し、`new()` メソッドは作らない
  - 例外: UUID 自動生成のような副作用ありのコンストラクタは `pub fn new()` で OK
- 型変換は `From` / `TryFrom`、`Into` / `TryInto` を使う
- 文字列化は `Display` (`strum_macros::Display` を活用)

## 値オブジェクトのパターン

`PhantomData` で「外部から `struct { ... }` 構文で構築できないこと」を保証する。

```rust
#[derive(Debug, Clone, PartialEq)]
pub struct UserId {
    value: Uuid,
    _hide_default_constructor: PhantomData<()>,
}

impl UserId {
    pub fn new() -> Self {
        Self::from(Uuid::new_v4())
    }
    pub fn value(&self) -> Uuid { self.value }
}

impl From<Uuid> for UserId { /* ... */ }
impl TryFrom<String> for UserId { /* バリデーション込み */ }
```

エンティティも同様に `_hide_default_constructor: PhantomData<()>` を持ち、`pub fn new(...)` 経由でのみ構築させる。

## 文字列バリデーションは `define_string!` マクロで統一

ドメイン層に以下のマクロを置き、文字列値オブジェクトを宣言的に定義する。

```rust
// src/domain/src/user/user_name.rs
use crate::string::define_string;
define_string!(UserName, max = 25);

// src/domain/src/user/raw_password.rs
define_string!(RawPassword, min = 10, max = 30);

// カスタムバリデーター
define_string!(Tag, max = 20, validator = |c: char| c.is_ascii_alphanumeric());
```

マクロ本体は `src/domain/src/string.rs`（`pub(crate)` で公開）。生成される型は `TryFrom<String>` を実装し、エラーは `domain::Error::InvalidLengthRange` / `InvalidFormat` を返す。

デフォルトバリデーターは「Unicode 英数字 + スペース + ハイフン + アンダースコア」を許可、絵文字・特殊記号は禁止。

## async fn in trait（async-trait 不使用）

ネイティブ async fn in trait（Rust 1.75+）を使う。`async-trait` クレートは導入しない。

```rust
pub trait Repository: Send + Sync {
    fn save_user(&self, user: &User) -> impl Future<Output = Result<()>> + Send;
    fn find_user_by_id(&self, id: &str) -> impl Future<Output = Result<Option<User>>> + Send;
}
```

`Send` 境界を明示する（actix-web のマルチスレッドランタイムで必要）。

## DI はジェネリクスで

trait object (`Box<dyn Repository>`) ではなく `Interactor<R: Repository>` の形でジェネリクスにする。

```rust
pub struct Interactor<R: Repository> {
    pub repository: R,
    pub jwt_config: JwtConfig,
}

impl<R: Repository> Interactor<R> {
    pub async fn handle_register_user(&self, req: RegisterUserRequest) -> Result<User> { ... }
}
```

- 各ユースケースは `impl<R: Repository> Interactor<R> { ... }` のメソッドとして追加
- ハンドラ・ルーターも `<R: Repository>` のジェネリックを引き回す

## エラーハンドリング

- 各レイヤーで `Error` enum と `pub type Result<A> = std::result::Result<A, Error>;` を定義
- 上位レイヤーには `From<下位::Error> for 上位::Error` で変換
- ロジック分岐用エラーには `String` メッセージを持たせ、ログとレスポンス本文の両方で利用
- `?` 演算子でエラーを伝播
- `unwrap()` / `expect()` は起動時の初期化失敗など「panic で止めて良い」ケースに限定

## sqlx の使い方

- `query!` 系マクロ（`query!` / `query_as!` / `query_scalar!` / `query_file!` など。ビルドに DB 接続か `cargo sqlx prepare` のオフラインデータが要る）は使わない。`query_as` 関数 + `FromRow` derive で型安全マッピングする
- DTO は `interface/rdb-gateway/src/dto/{entity}.rs` に定義し、ドメイン型への変換は `TryFrom` で実装
- マイグレーションは `deployments/db/migrations/` にリバーシブル形式（`.up.sql` / `.down.sql`）で配置

## ログ

`tracing` + `tracing-subscriber` を使う。`log` クレートからの橋渡しは `tracing-log` の `LogTracer::init()`。

リクエストごとのスパンとアクセスログは Apps 層（`apps/<bin>/src/setup.rs` 周辺）で初期化する。

## テスト

- インテグレーションテストは `src/apps/<bin>/tests/` に配置。`Cargo.toml` の `[[test]]` で `path = "tests/lib.rs"` を指定
- `helper/mod.rs` にテスト用 `App` 構築・DB クリーンアップ・テスト用 `JwtConfig` を集約
- 実 PostgreSQL に接続するテストは `--test-threads=1` で直列実行

## 命名

- モジュール・ファイル名: `snake_case`
- 型名: `UpperCamelCase`
- 値オブジェクト: `{Entity}{Attribute}`（例: `UserId`, `UserName`, `Email`）
- ハンドラメソッド: `handle_{action}_{entity}`（例: `handle_register_user`, `handle_login`）
- Repository メソッド: `save_*` / `find_*_by_*` / `update_*` / `delete_*`
