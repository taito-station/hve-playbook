# Claude Code 使用プロンプト集

hve-playbook をプロジェクトに組み込み、HVE 設計ワークフローを実行するためのプロンプトテンプレート。
Claude Code セッション内でコピー&ペーストして使う。

---

## 1. 新規プロジェクトにセットアップ

プロジェクトディレクトリがまだ存在しない、またはほぼ空の状態から始める場合。

```
新規プロジェクト「{プロジェクト名}」を作成し、HVE 設計手法で要件定義から始めたい。

セットアップ手順:
1. プロジェクトディレクトリを作成
2. git init
3. bash hve-playbook/setup.sh {プロジェクト名}

対象企業: {企業名}
対象事業: {事業名または「全事業を俯瞰」}

セットアップが完了したら /hve-ard で要件定義を開始してください。
```

ディレクトリを作って `git init` したあとは、2 節のプロンプトで適用してもよい。

### パラメータ補足

| 置換箇所 | 説明 | 例 |
|---|---|---|
| `{プロジェクト名}` | プロジェクトのディレクトリ名 | `my-saas-app` |
| `{企業名}` | ARD の分析対象企業 | `株式会社〇〇` |
| `{事業名}` | 特定事業に絞る場合に指定。省略時は事業ポートフォリオ全体を分析 | `EC事業部の受注管理業務` |

ARD にはこのほか任意パラメータがある（`include_kpi_okr`, `attached_docs`, `survey_base_date`, `survey_period_years`, `target_region`, `analysis_purpose`）。詳細は `skills/hve-ard/SKILL.md` のパラメータ表を参照。

---

## 2. 既存プロジェクトに追加

プロジェクトの Claude Code セッションで次の 1 行を送る（`~/workspace/hve-playbook` は hve-playbook を clone した場所に読み替える）。`.claude/` や CLAUDE.md が既にあるかどうかは問わない。

```
~/workspace/hve-playbook/docs/prompts/apply-hve-playbook.md を読んで、このリポジトリに hve-playbook を適用して
```

Claude が [`docs/prompts/apply-hve-playbook.md`](prompts/apply-hve-playbook.md) の手順に沿って進める。

- ブランチを切る
- `setup.sh` を実行する
- 既存の CLAUDE.md へ差分マージする（食い違いは質問票で確認）
- `.gitignore` を整える
- 検証して PR にする

---

## 3. ワークフロー実行プロンプト

### ARD（要件定義）

```
/hve-ard

企業名: {企業名}
対象事業: {事業名}
```

事業を絞らず全体を俯瞰する場合:

```
/hve-ard

企業名: {企業名}
```

添付資料がある場合:

```
/hve-ard

企業名: {企業名}
対象事業: {事業名}
添付資料: docs/input/business-plan.pdf
```

### AAS（アーキテクチャ設計）

ARD 完了後に実行する。以下が存在していることが前提。
- `docs/catalog/app-catalog.md`
- `docs/catalog/use-case-catalog.md`
- `docs/architectural-requirements-app-*.md`

```
/hve-aas
```

### AAD-WEB（Web 詳細設計）

AAS 完了後に実行する。`docs/catalog/` 配下に AAS の成果物が揃っていることが前提（詳細な前提ファイル一覧は `skills/hve-aad-web/SKILL.md` を参照）。

```
/hve-aad-web
```

### フルパイプライン（ARD → AAS → AAD-WEB 順次実行）

3 フェーズを順次実行する。各フェーズ完了後に次のスキルを手動で起動する。
（参考: `workflows/hve-design-pipeline.js` に 3 フェーズの依存関係を定義したパイプラインスクリプトがある）

```
/hve-ard

企業名: {企業名}
対象事業: {事業名}
```

ARD 完了後:

```
/hve-aas
```

AAS 完了後:

```
/hve-aad-web
```

---

## 4. 補助スキル

### 敵対的レビュー

成果物に対して 6 軸（要件充足性・技術的正確性・整合性・非機能品質・捏造検出・オーバーエンジニアリング検出）で検証する。

```
/hve-review

対象: docs/catalog/service-catalog.md
```

複数ファイルをまとめてレビューする場合:

```
/hve-review

対象: docs/catalog/ 配下の全カタログファイル
```

### QA 質問票生成

成果物やタスク指示から不明点・確認事項を構造化された質問票として抽出する。事前 QA（タスク実行前の指示に対する確認）と事後 QA（成果物に対する確認）の 2 モードがある。

事後 QA（成果物に対して）:

```
/hve-qa

対象: docs/business-requirement.md
```

事前 QA（タスク指示に対して）:

```
/hve-qa

対象: 次のタスクの指示内容
モード: 事前
```

---

## 5. Tips

- **途中から再開**: ワークフローが途中で中断した場合、SKILL.md の「実行手順」を見て、完了済みステップの成果物（`docs/` 配下）を確認し、次のステップから手動で指示できる
- **スコープ縮小**: ARD で全事業を分析すると時間がかかる。`対象事業` を指定して絞るのが実用的
- **成果物の確認**: 各ステップ完了後に `/hve-review` で品質チェックを挟むと、後工程での手戻りを減らせる
- **.claude/ を git 管理するか**: HVE 資産は git 管理する（プロジェクト固有の調整と、適用した hve-playbook の版を履歴に残すため）。`.claude/` を ignore していると、再セットアップ時に setup.sh が削除・置き直したファイルを git で復元できない
- **再セットアップ**: `setup.sh` は冪等に動作する。hve-playbook を更新後に再実行すれば最新ファイルが配置される。`.claude/rules/hve-local/` には触れないので、プロジェクト固有の補足は消えない

---

## 6. rules/hve/ 運用ガイド

`setup.sh` でファイルを配置した後、実際にどう運用するかのガイド。
rules/hve/ 配下のルールは Claude Code が自動読み込みし、該当タスクで自動適用される。

### 開発規律の優先順位

以下の順で優先される（上位が下位に優先）:

1. **捏造禁止** — 根拠のない ID/URL/名称/数値を作らない
2. **オーバーエンジニアリング禁止** — YAGNI、不要な抽象化を作らない
3. **最小差分原則** — 必要な変更だけを行う
4. **検証必須** — 動作を証明できるまで完了としない
5. **出力品質基準** — 日本語、見出し+箇条書き、出典付き
6. **成果物管理** — `docs/` に恒久成果物、`work/` に一時ファイル

### 実装フロー（implement-flow）

実装タスク（feat / fix / refactor / 改修）に自動適用される 9 段ゲートフロー。
ドキュメントのみ・設定変更のみ・依存更新のみの変更には適用されない。

```
Step 0: ブランチ作成
Step 1: Plan（スコープ特定）
Step 2: Knowledge 検索（Plan の各領域を網羅）
Step 3: 棄却済み案チェック
Step 4: ギャップ分析 → 質問票
Step 5: テスト設計
Step 6: 実装
Step 7: Knowledge 同期
Step 8: PR 作成
```

各ステップに STOP 条件（矛盾検出・テスト失敗等）があり、条件に該当した場合は自動停止して人間に報告する。詳細は `rules/hve/implement-flow.md` を参照。

フローを順に実行するには `/hve-implement` を使う。Step 1〜4 を Plan モードで進め、Step 4 の後に計画の承認を得てから実装に入る:

```
/hve-implement

対象: Issue #123（または実装したい内容）
```

resolve-issue skill は、導入先に hve-implement があれば bug / feature パスで自動的に呼ぶ（計画の前に Step 2〜4、実装で Step 5〜7）。

### Knowledge 管理（AKM）

implement-flow の Step 2（Knowledge 検索）と Step 7（Knowledge 同期）で構成される知識管理の仕組み。

#### Knowledge とは

プロジェクトに蓄積された以下の情報を指す:

- **確定知**: 仕様書・設計ドキュメント・API 定義など確定済みの事実
- **決定ログ**: 設計判断の記録。採用した案と却下した代替案（却下理由付き）
- **コード構造**: 既存の実装パターン・依存関係・命名規則

#### Knowledge 検索（Step 2）

Plan（Step 1）で特定した影響領域ごとに知識ベースを網羅的に検索する。

**検索ツールの優先順位**（`rules/hve/tool-usage.md` に従う）:

| 優先度 | ツール | 用途 |
|---|---|---|
| 1 | cq (Code Query) | ソースコード検索 |
| 2 | mdq (Markdown Query) | ドキュメント検索 |
| 3 | LSP ツール | シンボル定義・参照検索 |
| 4 | grep / find | フォールバック |

**検索のポイント**:

- キーワードを変えて複数回検索する（1 回では漏れる）
- ドキュメントとコードの両方を検索する
- 既存実装と矛盾する知識が見つかった場合 → STOP（人間に報告）

#### Knowledge 同期（Step 7）

実装完了後、確定知の前提が変わった場合に同じ PR で知識ベースを更新する。

- 仕様変更があれば該当ドキュメントを更新
- 設計判断を伴う変更は決定ログに追記（採用案 + 却下した代替案 + 理由）
- 更新時に既存の知識と矛盾が生じた場合 → STOP（Conflict 宣言、人間判断）

#### Knowledge 基盤の準備

プロジェクトに AKM を導入する際に準備すべきもの:

1. **`docs/` ディレクトリ**: `setup.sh` が自動作成する
2. **cq / mdq のインストール**（推奨、必須ではない）: `setup.sh` が自動インストールする。ローカルに HypervelocityEngineering リポがあれば `HVE_REPO_PATH` 環境変数で指定可能
3. **決定ログの運用開始**: 設計判断が発生したら記録を始める。既存プロジェクトでは過去の決定を遡って書く必要はない（今後の判断から記録すれば十分）

### 適用時の注意事項

- **段階的に導入可**: 全ルールを一度に適用する必要はない。implement-flow だけ先に導入し、Knowledge 管理は決定ログが溜まってから本格化する運用でもよい
- **cq/mdq なしでも動作する**: 未インストール時は grep/find にフォールバックする。検索精度は下がるが動作はする
- **rules/hve/ は自動適用**: `setup.sh` で `.claude/rules/hve/` に配置すれば、Claude Code が自動で読み込む。プロンプトで明示的に指示する必要はない
- **プロジェクト固有のカスタマイズ**: rules/hve/ や skills/hve-* の写しは編集しない（`setup.sh` を再実行すると上書きされる）。補足・上書きは `.claude/rules/hve-local/` に書く。書式と優先順位は `.claude/rules/hve/local-overrides.md` を参照
