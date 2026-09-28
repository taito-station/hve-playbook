---
paths:
  - "**/Cargo.toml"
  - "**/Cargo.lock"
---

# Cargo Workspace 規約

クリーンアーキテクチャ Rust プロジェクトの workspace 構成と Cargo.toml 規約。

## ルート Cargo.toml

`resolver = "3"` を使い、`workspace.dependencies` にライブラリバージョンを集約する。各メンバーは `{ workspace = true }` で参照する。

```toml
[workspace]
resolver = "3"
members = [
    "src/apps/rest-server"
]

[workspace.dependencies]
# 外部ライブラリ
actix-web = { version = "4.12.*" }
actix-http = { version = "3.11.*" }
argon2 = { version = "0.5.*", features = ["std"] }
chrono = { version = "0.4.*", features = ["serde"] }
dotenvy = { version = "0.15.*" }
envy = { version = "0.4.*" }
jsonwebtoken = { version = "9.*" }
serde = { version = "1.0.*", features = ["derive"] }
serde_json = { version = "1.0.*" }
sqlx = { version = "0.8.*", features = ["runtime-tokio", "tls-native-tls", "postgres", "uuid", "chrono", "migrate"] }
strum_macros = { version = "0.27.*" }
tracing = { version = "0.1.*" }
tracing-log = { version = "0.2.*" }
tracing-subscriber = { version = "0.3.*" }
uuid = { version = "1.20.*", features = ["serde", "v4"] }

# ワークスペース内クレート
my-app-config       = { path = "src/infrastructure/config" }
my-app-domain       = { path = "src/domain" }
my-app-use-case     = { path = "src/use-case" }
rest-controller     = { path = "src/interface/rest-controller" }
# rdb-gateway は apps から path で直接参照（DB実装の差し替えを意図する場合）
```

`members` には**バイナリクレートのみ**を列挙する。ライブラリクレートは workspace.dependencies 経由で path 参照されることで自動的に workspace に取り込まれる。

## 各メンバー Cargo.toml

`edition = "2024"` を使う。バージョンは `0.1.0` 固定（workspace 内で個別バージョニングしない）。

```toml
[package]
name = "my-app-domain"
version = "0.1.0"
edition = "2024"

[dependencies]
uuid = { workspace = true }
strum_macros = { workspace = true }
chrono = { workspace = true }
```

## レイヤー別の依存ルール

依存方向を Cargo.toml レベルで強制する。**逆方向の依存を書かない**。

| クレート | 依存できる相手 |
|---|---|
| `domain` | 外部依存のみ（`uuid`/`chrono`/`strum_macros` 等） |
| `use-case` | `domain` + 外部依存 |
| `rest-controller` (interface) | `domain` + `use-case` + `actix-web` 等 |
| `rdb-gateway` (interface) | `domain` + `use-case` + `sqlx` 等 |
| `config` (infrastructure) | `use-case`（`JwtConfig` 等の型のため） + `dotenvy`/`envy` |
| `apps/<bin>` | 全レイヤー（DI 構築のため） |

## `[[bin]]` と `[[test]]` の指定

ライブラリ + バイナリ構成の場合、`[lib]` `[[bin]]` を明示する:

```toml
[lib]
path = "src/lib.rs"

[[bin]]
name = "rest-server"
path = "src/bin.rs"

[[test]]
name = "integration_test"
path = "tests/lib.rs"
```

## rust-toolchain.toml

リポジトリルートに `rust-toolchain.toml` を置き、ツールチェーンを固定する:

```toml
[toolchain]
channel = "1.93.0"
```

## 依存追加のチェックリスト

新規クレート追加時:
1. ルート `Cargo.toml` の `[workspace.dependencies]` に追加
2. 利用するメンバーの `[dependencies]` に `{ workspace = true }` で追加
3. 依存方向のルールに違反していないか確認（例: domain から sqlx を引かない）

## バージョン指定

- メジャー固定 + マイナー以降ワイルドカード（例: `"4.12.*"`, `"1.20.*"`）を基本とする
- ただし破壊的変更が頻繁なクレート（`jsonwebtoken` 等）はメジャー固定 (`"9.*"`)
- `Cargo.lock` はバイナリプロジェクトなのでコミットする
