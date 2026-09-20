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

### パラメータ補足

| 置換箇所 | 説明 | 例 |
|---|---|---|
| `{プロジェクト名}` | プロジェクトのディレクトリ名 | `my-saas-app` |
| `{企業名}` | ARD の分析対象企業 | `株式会社〇〇` |
| `{事業名}` | 特定事業に絞る場合に指定。省略時は事業ポートフォリオ全体を分析 | `EC事業部の受注管理業務` |

ARD にはこのほか任意パラメータがある（`include_kpi_okr`, `attached_docs`, `survey_base_date`, `survey_period_years`, `target_region`, `analysis_purpose`）。詳細は `skills/hve-ard/SKILL.md` のパラメータ表を参照。

---

## 2. 既存プロジェクトに追加（`.claude/` なし）

プロジェクトはあるが `.claude/` ディレクトリがまだない場合。

```
このプロジェクトに HVE 設計手法を導入したい。

bash hve-playbook/setup.sh .

対象企業: {企業名}
対象事業: {事業名}
```

---

## 3. 既存プロジェクトに追加（`.claude/` あり）

すでに `.claude/` ディレクトリに独自の rules や skills がある場合。`setup.sh` は既存設定を壊さずに HVE ファイルだけを配置する。

```
このプロジェクトにはすでに .claude/ 設定がある。
HVE の設計手法（hve-playbook）を追加したい。

bash hve-playbook/setup.sh .

CLAUDE.hve.md が作成された場合は、既存の CLAUDE.md へ手動でマージしてください。
```

---

## 4. ワークフロー実行プロンプト

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

## 5. 補助スキル

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

## 6. Tips

- **途中から再開**: ワークフローが途中で中断した場合、SKILL.md の「実行手順」を見て、完了済みステップの成果物（`docs/` 配下）を確認し、次のステップから手動で指示できる
- **スコープ縮小**: ARD で全事業を分析すると時間がかかる。`対象事業` を指定して絞るのが実用的
- **成果物の確認**: 各ステップ完了後に `/hve-review` で品質チェックを挟むと、後工程での手戻りを減らせる
- **.claude/ を git 管理するか**: プロジェクト固有のカスタマイズを加える場合は git 管理する。playbook そのままなら `.gitignore` に追加して管理外にする
- **再セットアップ**: `setup.sh` は冪等に動作する。hve-playbook を更新後に再実行すれば最新ファイルが配置される
