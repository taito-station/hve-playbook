# hve-playbook

Claude Code の開発基盤設定（user-level）と HVE 設計手法（project-level）を一元管理するリポジトリ。

Based on [dahatake/HypervelocityEngineering](https://github.com/dahatake/HypervelocityEngineering) (MIT License).
Includes [dotclaude-public](https://github.com/taito-station/dotclaude-public) by youhei-ushio (MIT License).

## 構成

本リポジトリは 2 つの役割を持つ:

| 役割 | デプロイ方法 | デプロイ先 | 内容 |
|---|---|---|---|
| **user-level 基盤** | `sync-dotclaude.sh` (symlink) | `~/.claude/` | hooks, global skills, scripts, rules/global, agents/global, settings |
| **project-level HVE** | `setup.sh` (copy) | target/.claude/ | rules/hve, HVE skills/agents/workflows |

## セットアップ

### 1. user-level 基盤の同期

```bash
git clone https://github.com/taito-station/hve-playbook.git
bash hve-playbook/sync-dotclaude.sh
```

`sync-dotclaude.sh` は `~/.claude/` に symlink を張る（冪等・何度実行しても安全）。以降は `git -C hve-playbook pull --ff-only && bash hve-playbook/sync-dotclaude.sh --prune` を **1 回のコマンドで** 実行して最新化する。この clone で switch / checkout / rebase / merge をするときも、同じく `&& bash hve-playbook/sync-dotclaude.sh --prune` と続ける。git 操作と sync を別々に実行すると、hook を削除した更新を取り込んだとき、その間は `~/.claude/settings.json` に残った hook 行が消えたファイルを呼ぶ。その結果、Bash が全面ブロックされる。そうなったら、Claude Code の外のターミナルで `bash hve-playbook/sync-dotclaude.sh --prune` を実行して復旧する（[ADR-0010](knowledge/adr/0010-drop-serena-for-builtin-lsp.md)）。

`~/.claude/settings.json` だけは symlink ではなく、リポの `settings.json` と `~/.claude/settings.machine.json`（マシン固有の hook・permissions 等。任意）をマージした生成物になる。`~/.claude/settings.json` を直接編集しても次の同期で上書きされるため、マシン固有の設定は `settings.machine.json` に書く（user レベルの `~/.claude/settings.local.json` は Claude Code に読まれない。[ADR-0006](knowledge/adr/0006-generate-settings-json-with-machine-overlay.md)）。前回の同期後に `~/.claude/settings.json` が直接編集されていた場合は、`settings.json.bak-<日時>` に退避してから上書きする。生成には `python3` が必要。

`rules/global/`・`agents/global/` も同じく `~/.claude/rules/<category>`・`~/.claude/agents/<name>.md` に symlink する。これらを `~/.claude` に実体で置いていた環境は、sync が WARN でスキップする（exit 2）ので、一度だけ実体を退避して sync をやり直す（[ADR-0007](knowledge/adr/0007-consolidate-user-level-rules-and-agents.md)）:

```bash
mkdir -p ~/.claude/backups/pre-consolidate
mv ~/.claude/rules/{git,php,rust,sql,workflow} ~/.claude/agents/impl-sonnet.md \
   ~/.claude/skills/{brew-update-all,learn,review-doc} ~/.claude/backups/pre-consolidate/
bash hve-playbook/sync-dotclaude.sh   # exit 0 で終わることを確認
```

### 2. プロジェクトへの HVE 導入

```bash
bash hve-playbook/setup.sh /path/to/my-project
```

対象プロジェクトの `.claude/` に HVE 関連ファイル（rules, skills, agents, workflows）をコピーする。

対象プロジェクトの Claude Code セッションに「`~/workspace/hve-playbook/docs/prompts/apply-hve-playbook.md` を読んで、このリポジトリに hve-playbook を適用して」と送れば（パスは clone した場所に読み替える）、ブランチ作成から setup.sh の実行、CLAUDE.md のマージ、PR 作成（リモートが無ければコミット）までを Claude が進める（[適用プロンプト](docs/prompts/apply-hve-playbook.md)）。

## HVE 設計ワークフロー

ビジネス要件の定義からソフトウェア詳細設計までを 3 つのワークフローで段階的に進める。

```
ARD (要件定義) → AAS (アーキテクチャ設計) → AAD-WEB (Web 詳細設計)
```

| ワークフロー | スキル名 | 内容 |
|---|---|---|
| ARD | `/hve-ard` | 事業分析 → ユースケース抽出 → アプリケーション分類 → 要件定義 |
| AAS | `/hve-aas` | アーキテクチャ選定 → DDD ドメイン分析 → データモデル → テスト戦略 |
| AAD-WEB | `/hve-aad-web` | 画面設計 → サービス設計 → テストスペック → 一貫性レビュー |

補助スキル: `/hve-review`（敵対的レビュー）、`/hve-qa`（QA 質問票生成）

## Global Skills（user-level）

`sync-dotclaude.sh` で配置される汎用スキル。全プロジェクトで利用可能。

主なスキル:

| スキル名 | 内容 |
|---|---|
| `/create-pr` | PR 作成 + セルフレビュー + AKM チェック + セッション費用表示 |
| `/review-pr` | 敵対的セルフレビュー（多観点・複数巡） |
| `/commit-workflow` | Conventional Commits 準拠のコミット作成 |
| `/resolve-issue` | Issue 分析から PR 作成までの一貫フロー |

## Scripts

| スクリプト | 内容 |
|---|---|
| `scripts/session-cost.py` | セッション JSONL からトークン使用量と費用を集計 |

## 推奨ツール

| ツール | 用途 |
|---|---|
| cq (Code Query) | ソースコード検索（SQLite + BM25 + tree-sitter） |
| mdq (Markdown Query) | Markdown/CSV ドキュメント検索（SQLite + BM25） |

インストール方法は `rules/hve/tool-usage.md` を参照。

## 開発規律

`rules/hve/` で以下の規律を強制する（優先順位順）:

1. **捏造禁止** — 根拠のない情報を成果物に含めない
2. **オーバーエンジニアリング禁止** — YAGNI、不要な抽象化を入れない
3. **最小差分原則** — 必要な変更だけを行う
4. **検証必須** — 動作を証明できるまで完了としない
5. **出力品質基準** — 日本語、見出し+箇条書き、出典付き
6. **成果物管理** — ファイル配置・更新ポリシー
7. **ツール利用ポリシー** — cq/mdq/LSP/grep の優先順位

## 使い方の詳細

プロジェクトへの組み込み方やワークフロー実行のプロンプト例は [docs/usage-prompts.md](docs/usage-prompts.md) を参照。

## ライセンス

MIT License. See [LICENSE](LICENSE).
