# クライアントのクリーンアーキテクチャ規約を、Web（React）とモバイル（Flutter）に分けて定める

## ステータス

Accepted — 2026-10-31

## 背景と課題

ADR 0018 で、言語を問わないクリーンアーキテクチャ共通規約 `rules/hve/clean-architecture.md` を作った。原則（依存は内側にだけ向ける、ドメインモデルは外部依存を持たない、外部依存はユースケース側の抽象越しに使う、組み立ては外側、エラーはレイヤーごとに変換）はクライアントにも効かせたが、レイヤー構成と命名はバックエンドに限り、クライアントは別 Issue で作ると決めていた（[hve-playbook#58](https://github.com/taito-station/hve-playbook/issues/58)）。

着手時の調査（2026-10-31）では、作者の手元のクライアントは paddock/web（React 19 + Vite + TypeScript の SPA）と、非公開のモバイルクライアント（Flutter）の 2 つで、どちらもレイヤー分けをしていなかった。クライアントの手本のテンプレートは無く、上流 HVE にもクライアントの構成の規約は無い。Flutter には公式のアーキテクチャガイドと case study（https://docs.flutter.dev/app-architecture/guide 、https://docs.flutter.dev/app-architecture/case-study 。2026-10-31 に参照）がある。ガイドは UI 層（View・ViewModel）と Data 層（Repository・Service）を基本にし、Domain 層（Use-case）を任意としている。case study は `lib/ui/`・`lib/domain/models/`・`lib/data/`・`config/`・`routing/` のパッケージ構成を示している。React には公式のレイヤー構成のガイドが無い。

問い: クライアントのレイヤー構成と命名を、どの範囲で、どう定めるか。

## 意思決定の要因

- PO が「基本的にクリーンアーキテクチャは採用したい」としている（質問票 `qa/client-clean-architecture-questionnaire.md`）
- 共通規約の原則と矛盾しない
- 根拠の無い技術の構成を書かない（手元に実在する技術に限る）
- それぞれのプラットフォームの開発者が読み慣れた名前にする（Q02・Q07）
- 使う先の見えない手本やライブラリの指定を足さない（YAGNI）

## 検討した選択肢

- Web とモバイルで節を分け、Web はバックエンドの名前、Flutter は公式 case study の名前を使う
- フレームワークに依存しない構成を 1 つ定め、React と Flutter の置き場所を対応表で示す
- 今は作らず、原則だけで運用する
- 手本のテンプレートのリポジトリを作る

## 決定内容

選択した選択肢: **Web とモバイルで節を分け、Web はバックエンドの名前、Flutter は公式 case study の名前を使う**。Issue #58 の質問票（Q01〜Q06）と追加の確認（Q07・Q08）で確定した。

- 適用範囲は React の SPA と Flutter。それ以外のクライアント（Vue・Svelte・SwiftUI、ファイルの配置でルーティングを決めるフレームワーク（Next.js など））は原則の節だけを適用し、構成は各リポジトリの `.claude/rules/hve-local/clean-architecture.md` に書く
- Web: model（`src/domain/model/`）・use-case（`src/domain/use-case/` の `interactor/`・`gateway/`・`errors/`）・gateway（`src/gateway/<外部サービス名>/`）・presentation（`src/presentation/`）・app（`src/app/`）
- Flutter: case study のパッケージ構成を基にし、外れる点を 2 つにする。use-case の層を必須にして `lib/domain/use_cases/` に置くことと、repository の抽象を `lib/domain/repositories/` に置くこと（case study は domain に抽象の置き場所を設けていない。原則「外部依存はユースケース側の抽象越し」に合わせる）。原則の gateway は repository に当たる
- use-case の層は Web・モバイルとも必須にする（Q08）。画面の層（presentation・ui）は model と use-case だけに依存し、gateway・repository は抽象も実装も直接使わない。公式ガイドが use-case を任意とし、ViewModel から repository を直接呼ぶ点には倣わない
- エラーは、データの層のエラーを use-case のエラーへ、use-case のエラーを画面の層で利用者向けの表示へ変換し、画面には内部の詳細を出さない（詳細はログに残し、秘密情報・認証情報・個人情報は出さない）。Flutter の data がこの変換を書けるよう、use-case のエラー型を `lib/domain/use_cases/errors/` に置き（エラー型は model だけに依存する）、data と repository の抽象はそれに依存してよいとする
- クライアントのコードと設定は利用者の手元に配られるので、秘密情報を置かない。認可はサーバで判定し、クライアントでの判定は表示の制御に留める。利用者に見せてはいけないデータは、サーバの応答に含めない（認証情報の保存先は、未定義の領域の「認証・認可の置き場所」として各リポジトリが決める）
- ドメインの概念を持たない補助（Web は `src/utils/`、Flutter は `lib/utils/`）は層に属さず、どの層からも使ってよい（補助は層のコードを import しない）。ルートのパスの定数は、Web は `src/presentation/` に、Flutter は `lib/routing/routes.dart` に置き、画面の層から参照してよい。どちらも循環を作らないための置き場所
- Web の presentation は、interactor を受け取る口（Context と hook、または props）を自分の中に置き、値は app が渡す（presentation は app を import しない）
- 状態管理・ルーティング・サーバの状態のキャッシュに使うライブラリは決めず、「未定義の領域」に加える。置くレイヤー（画面の状態は presentation・view model、取得とキャッシュは gateway・repository の実装）だけを表に書く（Q05）。キャッシュのライブラリが画面の層で動く形（React の hook など）のときは、取得を use-case 経由にすれば、キャッシュを画面の層に置いてよい（PR のセルフレビューの指摘を受け、PO が判断）
- 既存のクライアントがこの構成でなければ、既存の構成と命名に合わせる。移行するかは各リポジトリの Issue で決め、本 Issue では起票しない（Q06。ADR 0018 の既存コードの扱いと同じ）
- 手本のリポジトリは作らない。要るようになったら、バックエンドのテンプレートと同じく別のリポジトリとして作る（Q04）
- 契約は `tests/test_clean_architecture_contract.sh` で固定する

### 結果（Consequences）

- 良い結果: React の SPA と Flutter で新しくクライアントを作るとき、レイヤー・置き場所・依存してよい先が決まる。どちらも use-case を通して外部依存を扱うので、バックエンドと同じ原則でテストできる（use-case を抽象の差し替えで単体テストできる）
- 悪い結果:
  - 手本のコードが無いので、この構成が実際の開発に耐えるかは、最初にこの構成でクライアントを作るときに確かめることになる
  - Web と Flutter で同じ概念の名前が違う（外部依存の抽象が gateway と repository、画面の層が presentation と ui）。Flutter の節に対応を書いて補う
  - use-case を必須にしたので、元の処理を渡すだけの use-case が小さな画面で増える
  - 規約の分量が増える（約 6.6KB → 約 12KB）。`paths:` は 16 の拡張子で共通なので、クライアントの無いバックエンドだけのリポジトリ（.rs・.php・.go・.py など）でも、クライアントの節が載る。クライアントの節を別の rule に分ける案は採らなかった（.ts・.js はサーバ側にもあり、分けても TypeScript のバックエンドでは載る。`paths:` を変えない前提も保つ）。.ts・.js はサーバ側のコードでも載るので、節の冒頭でバックエンドとクライアントの見分け方を書いた
  - `paths:` の rule は、該当するファイルを Read したときに載り、Write だけで新しくファイルを作る場面では載らない（ADR 0018 の実測）。この規約の主な対象は新しく作るクライアントなので、新しいクライアントでは規約を明示的に読ませる（`docs/usage-prompts.md` の注意と同じ）
  - 手元の 2 つのクライアントはこの構成でないので、既存の構成に合わせる側に入り、この規約は効かない
  - #34 の後に setup.sh を再適用していない導入先には、`clean-architecture.md` 自体がまだ無い（2026-10-31 に手元で確認）。導入先で効かせるには setup.sh を再適用する

## 選択肢の評価（Pros and Cons）

### Web とモバイルで分け、それぞれの慣習の名前を使う（採用）

#### メリット

- Flutter は公式の用語とパッケージ構成で読める。Web はバックエンドと同じ名前で読める

#### デメリット

- 規約が長くなり、同じ概念に 2 つの名前が付く

### 1 つの構成と対応表

#### メリット

- 覚えるレイヤーと名前が 1 組で済み、規約が短い

#### デメリット

- Flutter の公式の用語と食い違う。PO が Q02 で分ける方を選んだ

### 今は作らない

#### メリット

- 使う先の見えない規約を足さない

#### デメリット

- 新しいクライアントを書くときに具体的な指針が無い。PO は ADR 0018（#34 の Q4）でクライアントの規約を作ると決めており、Q01 でも作る方を選んだ

### 手本のテンプレートを作る

#### メリット

- コードで構成を確かめられる

#### デメリット

- 手本を使う新しいクライアントの予定が見えず、保守だけが残る（Q04）

## 関連リンク

- Related: [0018-language-agnostic-clean-architecture-rule](0018-language-agnostic-clean-architecture-rule.md)（クライアントの規約を別 Issue で作るとした決定の実行。0018 の決定は変えない）
- Related: [0012-project-local-overrides-in-hve-local](0012-project-local-overrides-in-hve-local.md)
- Related: [hve-playbook#58](https://github.com/taito-station/hve-playbook/issues/58)
