# 言語を問わないクリーンアーキテクチャ規約を rules/hve に置き、コードを読んだときに読み込む

## ステータス

Accepted — 2026-10-12

## 背景と課題

hve-playbook を導入するリポジトリで、Rust 以外の言語でも [ttm-bros/rust-backend-template](https://github.com/ttm-bros/rust-backend-template)（`develop`）と同じクリーンアーキテクチャを取りたい（[hve-playbook#34](https://github.com/taito-station/hve-playbook/issues/34)）。

アーキテクチャ規約は言語ごとに分かれていた。user-level の `rules/global/rust/architecture.md` と `rules/global/php/architecture.md` は fridgers-backend 型で、TypeScript・Python などには規約が無い。手本のテンプレートは README の無い最小のサンプルで、構成と命名は fridgers 型と違う（`controller/`・`gateway/` を最上位に置き、use-case 側の抽象を gateway と呼ぶ。依存の組み立ては controller の builder）。DB の gateway・エラーと HTTP の対応・認証は持たない。

問い: 言語に依存しない規約をどこに置き、既存の言語別規約とどう両立させるか。

## 意思決定の要因

- HVE 導入先で、言語を問わず効く（PO 回答 Q1）
- 導入先で自己完結する（ADR-0002）
- 常時読み込みにしてコンテキストを消費しない
- paddock など fridgers 型の既存コードを壊さない（Q3）
- 規約が言語別規約と同時に載ったとき、どちらに従うかが一意に決まる

## 検討した選択肢

- `rules/hve/clean-architecture.md` に置き、`paths:` にソースコードの拡張子を付ける
- `rules/global/` に置いて sync で配る
- global と hve の両方に置き、ずれを検査する（ADR-0007 型）
- 新規実装のときに読む skill にする

## 決定内容

選択した選択肢: **`rules/hve/clean-architecture.md` に置き、`paths:` にソースコードの拡張子を付ける**。

- 規約は、原則（言語・バックエンド・クライアント共通）、バックエンドのレイヤー構成と命名（テンプレート準拠、バックエンドに限る）、未定義の領域、言語別規約との関係、クライアントの扱いの節を持つ
- `paths:` は .rs .go .py .rb .php .java .kt .cs .ts .tsx .js .jsx .vue .svelte .swift .dart。クライアントの拡張子も含め、原則はクライアントにも効かせる（Q4）。.sh・.md は含めない
- 言語別規約（Rust / PHP）は書き換えない（Q3）。新しいリポジトリやこの規約の構成のコードはこの規約に従い、既存コードがこの規約の構成でなければ（fridgers 型を含む）既存コードの構成と命名、原則の適用の度合いに合わせる（fridgers 型で言語別規約が載っていれば言語別規約に従う）。この規約への移行は各リポジトリの Issue で決める（Q1）。対応表で名前を対応づける
- 手本にも無い領域（DB の gateway、エラーと応答の対応、認証、DTO）は決めず、各リポジトリが hve-local に書く
- クライアントの具体的な規約は別 Issue（[hve-playbook#58](https://github.com/taito-station/hve-playbook/issues/58)）で作る。具体的な手本は、テンプレートのように別のリポジトリで管理してよい（Q4）

### 結果（Consequences）

- 良い結果: HVE 導入先で、どの言語のコードを読んでも同じ原則と構成が効く。fridgers 型の既存コードはそのまま言語別規約で書ける
- 悪い結果:
  - `paths:` の rule は、該当するファイルを Read したときに載る。Write だけでファイルを作る場面では載らない（2026-10-12 に一時リポジトリで実測。.ts の Read では載り、.md の Read と、.ts の Write だけでは載らなかった）。既存コードを読まずに書き始める新しいリポジトリでは、この規約を明示的に読む必要がある
  - Rust / PHP のファイルでは言語別規約と両方が載るので、従う側を規約の文面（優先順位）で決めている。user-level の言語別規約は導入先の hve-local では止められない
  - TypeScript・Python などでは、未定義の領域の参考になる言語別規約が無い
  - `.claude/rules/hve-local/clean-architecture.md` は `paths:` を付けない（local-overrides.md）ので常時載る。補足は短く保つ
  - 手本のテンプレートは ttm-bros の非公開リポジトリで、関係者以外は開けない
  - HVE の AAS 工程（hve-architect）はコードを読まないので、この規約は載らない

## 選択肢の評価（Pros and Cons）

### rules/hve に置き、paths を付ける

#### メリット

- 導入先で自己完結し、コードを読んだときだけ載る

#### デメリット

- HVE を導入していないリポジトリには効かない。Write だけの場面では載らない

### rules/global に置く

#### メリット

- HVE を導入していないリポジトリでも、作者の環境なら効く

#### デメリット

- 導入先で自己完結せず、ほかの開発者や CI の環境には届かない（ADR-0002）

### global と hve の両方に置く

#### メリット

- どちらの環境でも効く

#### デメリット

- 管理するものとずれの検査が増える。HVE 未導入のリポジトリへの展開は求められていない

### skill にする

#### メリット

- コンテキストの消費が最小

#### デメリット

- 呼び忘れると効かない

## 関連リンク

- Related: [0002-integrate-dotclaude-public-into-hve-playbook](0002-integrate-dotclaude-public-into-hve-playbook.md)
- Related: [0007-consolidate-user-level-rules-and-agents](0007-consolidate-user-level-rules-and-agents.md)
- Related: [0012-project-local-overrides-in-hve-local](0012-project-local-overrides-in-hve-local.md)
- Related: [hve-playbook#34](https://github.com/taito-station/hve-playbook/issues/34)
