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
3. hve-playbook を .claude/ として配置（git clone https://github.com/taito-station/hve-playbook.git .claude）
4. docs/ ディレクトリを作成

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

---

## 2. 既存プロジェクトに追加（`.claude/` なし）

プロジェクトはあるが `.claude/` ディレクトリがまだない場合。

```
このプロジェクトに HVE 設計手法を導入したい。

1. hve-playbook を .claude/ として配置してください
   git clone https://github.com/taito-station/hve-playbook.git .claude
2. .gitignore に .claude/ を追加するかどうかは聞いてください

対象企業: {企業名}
対象事業: {事業名}
```

---

## 3. 既存プロジェクトに追加（`.claude/` あり）

すでに `.claude/` ディレクトリに独自の rules や skills がある場合。既存設定を壊さずにマージする。

```
このプロジェクトにはすでに .claude/ 設定がある。
HVE の設計手法（hve-playbook）を既存設定とマージして追加したい。

手順:
1. hve-playbook を一時ディレクトリにクローン
2. 以下を .claude/ 配下にコピー（既存ファイルは上書きしない）:
   - rules/hve/          → .claude/rules/hve/
   - skills/hve-ard/     → .claude/skills/hve-ard/
   - skills/hve-aas/     → .claude/skills/hve-aas/
   - skills/hve-aad-web/ → .claude/skills/hve-aad-web/
   - skills/hve-review/  → .claude/skills/hve-review/
   - skills/hve-qa/      → .claude/skills/hve-qa/
   - agents/hve-*.md     → .claude/agents/
   - workflows/hve-*.js  → .claude/workflows/
3. CLAUDE.md に HVE の出力ディレクトリ構造と規律セクションを追記（既存内容は残す）
4. 一時ディレクトリを削除
5. 変更内容を見せてください
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

ARD 完了後に実行する。`docs/catalog/app-catalog.md` が存在していることが前提。

```
/hve-aas
```

### AAD-WEB（Web 詳細設計）

AAS 完了後に実行する。`docs/catalog/` 配下に AAS の成果物が揃っていることが前提。

```
/hve-aad-web
```

### フルパイプライン（ARD → AAS → AAD-WEB 一括）

3 フェーズを連続実行する。途中で QA 質問票が生成された場合は回答が必要。

```
/hve-ard から始めて、ARD → AAS → AAD-WEB を順に実行してください。
各フェーズ間で成果物の存在を確認し、不足があれば報告してください。

企業名: {企業名}
対象事業: {事業名}
```

---

## 5. 補助スキル

### 敵対的レビュー

成果物に対して 6 軸（正確性・完全性・一貫性・実現可能性・保守性・セキュリティ）で検証する。

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

成果物から不明点・確認事項を構造化された質問票として抽出する。

```
/hve-qa

対象: docs/business-requirement.md
```

---

## 6. Tips

- **途中から再開**: ワークフローが途中で中断した場合、SKILL.md の「実行手順」を見て、完了済みステップの成果物（`docs/` 配下）を確認し、次のステップから手動で指示できる
- **スコープ縮小**: ARD で全事業を分析すると時間がかかる。`対象事業` を指定して絞るのが実用的
- **成果物の確認**: 各ステップ完了後に `/hve-review` で品質チェックを挟むと、後工程での手戻りを減らせる
- **.claude/ を git 管理するか**: プロジェクト固有のカスタマイズを加える場合は git 管理する。playbook そのままなら `.gitignore` に追加して管理外にする
