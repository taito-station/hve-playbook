# hve-playbook

HypervelocityEngineering (HVE) の設計手法を Claude Code ネイティブで実行するための `.claude/` 設定パッケージ。

Based on [dahatake/HypervelocityEngineering](https://github.com/dahatake/HypervelocityEngineering) (MIT License).

## 概要

ビジネス要件の定義からソフトウェア詳細設計までを 3 つのワークフローで段階的に進める。

```
ARD (要件定義) → AAS (アーキテクチャ設計) → AAD-WEB (Web 詳細設計)
```

| ワークフロー | スキル名 | 内容 |
|---|---|---|
| ARD | `/hve-ard` | 事業分析 → ユースケース抽出 → アプリケーション分類 → 要件定義 |
| AAS | `/hve-aas` | アーキテクチャ選定 → DDD ドメイン分析 → データモデル → テスト戦略 |
| AAD-WEB | `/hve-aad-web` | 画面設計 → サービス設計 → テストスペック → 一貫性レビュー |

補助スキル:

| スキル名 | 内容 |
|---|---|
| `/hve-review` | 敵対的レビュー（6 軸検証） |
| `/hve-qa` | QA 質問票生成 |

## セットアップ

プロジェクトディレクトリに `.claude/` として配置する。

```bash
# 方法 1: クローン
git clone https://github.com/taito-station/hve-playbook.git my-project/.claude

# 方法 2: 既存プロジェクトにコピー
cp -r hve-playbook/ my-project/.claude/
```

## 使い方

### 個別ワークフローの実行

```
# Claude Code セッション内で
/hve-ard          # 要件定義を開始
/hve-aas          # アーキテクチャ設計を開始（ARD 完了後）
/hve-aad-web      # Web 詳細設計を開始（AAS 完了後）
```

### 補助スキル

```
/hve-review       # 成果物の敵対的レビュー
/hve-qa           # QA 質問票の生成
```

## 開発規律

本パッケージは以下の開発規律を `rules/hve/` で強制する（優先順位順）:

1. **捏造禁止** — 根拠のない情報を成果物に含めない
2. **オーバーエンジニアリング禁止** — YAGNI、不要な抽象化を入れない
3. **最小差分原則** — 必要な変更だけを行う
4. **検証必須** — 動作を証明できるまで完了としない
5. **出力品質基準** — 日本語、見出し+箇条書き、出典付き
6. **成果物管理** — ファイル配置・更新ポリシー

## ライセンス

MIT License. See [LICENSE](LICENSE).
