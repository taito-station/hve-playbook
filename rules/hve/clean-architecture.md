---
paths:
  - "**/*.rs"
  - "**/*.go"
  - "**/*.py"
  - "**/*.rb"
  - "**/*.php"
  - "**/*.java"
  - "**/*.kt"
  - "**/*.cs"
  - "**/*.ts"
  - "**/*.tsx"
  - "**/*.js"
  - "**/*.jsx"
  - "**/*.vue"
  - "**/*.svelte"
  - "**/*.swift"
  - "**/*.dart"
---

# クリーンアーキテクチャ共通規約

言語を問わず、新しく書くコードのレイヤー構成と依存の向きを揃える規約。手本は [ttm-bros/rust-backend-template](https://github.com/ttm-bros/rust-backend-template)（`develop` ブランチ。ttm-bros の関係者だけが開ける）。

## 原則（言語・バックエンド・クライアント共通）

- 内側は外側に依存しない: 外側（入口・外部アダプター・起動）→ ユースケース → ドメインモデルの向きだけを許す（外側同士は、バックエンドでは下の表の範囲で許す。クライアントでは #58 で決める）。内側は外側の型・ライブラリを知らない
- ドメインモデルは外部依存を持たない（フレームワーク・DB・HTTP クライアントを import しない）
- 外部依存（外部 API・DB・ファイル・時計など）は、ユースケース側に置いた抽象（gateway）越しに使う。実装は外側のレイヤーが持つ
- 依存の組み立て（実装を生成して抽象に差し込む）は外側で行う。ドメインモデルとユースケースは実装を参照しない
- レイヤーごとに独自のエラー型を持ち、外側へ渡すときに変換する。内側のエラーに外側の概念（HTTP ステータスなど）を持ち込まない

## バックエンドのレイヤー構成と命名（バックエンドに限る）

各レイヤーを独立したビルド単位（Rust は crate、他の言語はパッケージ・モジュール・ディレクトリ）にし、できる言語では依存をビルド単位で強制する。

| レイヤー | 置き場所（手本） | 中身 | 依存してよい先 |
|---|---|---|---|
| model | `domain/model/` | エンティティ・値オブジェクト（例: `time/date_time.rs`） | なし |
| use-case | `domain/use-case/` | `interactor/`（ユースケース。1 ユースケース 1 ファイル）、`gateway/`（外部依存の抽象。1 外部依存 1 ファイル）、`errors/` | model |
| controller | `controller/<入口>/`（例: `controller/rest/`） | `handlers/<version>/<resource>/`（`handler` と、入出力の `schema`。ヘルスチェックは `handlers/health/<種類>/`）、`builder`、`errors/` | model・use-case・gateway の実装 |
| gateway | `gateway/<外部サービス名>/` | use-case の gateway の実装。`handlers/<操作>/`（外部の形式からモデルへの変換を含む）、`builder`、`errors/` | model・use-case |
| app | `app/<実行形態>/`（例: `app/rest-server/`） | 起動とルーティングの登録 | controller |

- 命名
  - ユースケースは `Interactor`。ユースケースごとに `interactor/` に 1 ファイルを足し、`Interactor` のメソッドとして実装する（手本: `interactor/get_now_time.rs` の `impl Interactor { async fn get_now_time() }`）
  - 外部依存の抽象は `gateway`（例: `trait WorldTimeApi`）。抽象をまとめる入れ物を `Gateway` とし、`Interactor::new(gateway)` で渡す
  - gateway の実装は `<抽象名>Impl`（例: `WorldTimeApiImpl`）。生成は `<名前>Builder`（`with_<設定>()` を連ねて `build()`）
  - 入口の入出力の型は `schema` に置き、モデルから変換して作る（`From<Model>` など）
- 依存の組み立て: 手本は controller の `InteractorBuilder` が gateway の実装を生成して `Interactor` を作り、app はそれを呼ぶだけ。app で組み立ててもよく、そのときは app が use-case と gateway の実装にも依存してよい
- エラーの変換: gateway のエラーは use-case のエラーへ（`From`）、use-case のエラーは入口の応答へ変換する。応答には内部エラーの詳細を含めず、詳細はログに残す（秘密情報・認証情報・個人情報は出さない）。手本の handler がエラーの文字列を応答に含める点には倣わない

## 未定義の領域

次は手本にも無く、この規約では決めない。各リポジトリで決めて `.claude/rules/hve-local/clean-architecture.md` に書く。

- DB の gateway の構成（リポジトリの単位、トランザクションの境界）
- use-case のエラーの種類と、HTTP ステータスなど入口の応答への対応表
- 認証・認可の置き場所
- ユースケースの入出力専用の型（DTO）を設けるか

Rust と PHP は、言語別規約（下記）がトランザクションの境界を除くこれらを定めている。

## 言語別規約との関係

hve-playbook は Rust と PHP に、fridgers-backend 型の言語別規約（hve-playbook の `rules/global/rust/architecture.md`・`rules/global/php/architecture.md`）を user-level の rule として配っている（入っている環境でだけ、該当ファイルを読んだときに載る）。どちらに従うかは次で決める。

- 新しく作るリポジトリ、または既存コードがこの規約の構成なら、この規約に従う。言語別規約は「未定義の領域」の参考にだけ使う
- 既存コードがこの規約の構成でなければ（fridgers 型を含む）、既存コードの構成と命名、原則の適用の度合いに合わせる。fridgers 型で言語別規約が載っていれば、言語別規約に従う。この規約への移行は各リポジトリの Issue で決める

| この規約 | Rust 言語別規約 | PHP 言語別規約 |
|---|---|---|
| `domain/model` | `src/domain` | `app/Domain` |
| `domain/use-case` の `interactor` | `src/use-case` の `Interactor<R>` | `app/UseCase` の `{Action}{Entity}Interactor` |
| `domain/use-case` の `gateway` | `Repository` trait | `{Entity}RepositoryInterface` |
| `controller/rest` | `src/interface/rest-controller` | `app/Interface/Http` |
| `gateway/<service>` | `src/interface/rdb-gateway` | `app/Interface/Persistence/Eloquent` |
| `app/<実行形態>` | `src/apps/<bin>` | Laravel のエントリポイント・`AppServiceProvider` |

## クライアント（フロントエンド・モバイル）

原則の節だけを適用する。レイヤー構成と命名の規約はまだ無い（[hve-playbook#58](https://github.com/taito-station/hve-playbook/issues/58) で作る）。
