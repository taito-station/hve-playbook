# hve-playbook

Claude Code の開発基盤設定（user-level）と HVE 設計手法（project-level）を一元管理するリポジトリ。

Based on [dahatake/HypervelocityEngineering](https://github.com/dahatake/HypervelocityEngineering) (MIT License).
Includes [youhei-ushio/dotclaude-public](https://github.com/youhei-ushio/dotclaude-public) (MIT License).

## 構成

本リポジトリは 2 つの役割を持つ:

| 役割 | デプロイ方法 | デプロイ先 | 内容 |
|---|---|---|---|
| **user-level 基盤** | `sync-dotclaude.sh` (symlink) | `~/.claude/` | hooks, global skills, scripts, rules/global, agents/global, settings |
| **project-level HVE** | `setup.sh` (copy) | target/.claude/ | rules/hve, HVE skills/agents/workflows, knowledge の検査スクリプト（hve-scripts → scripts/hve） |

## 使う前に

### 位置づけ

- **project-level HVE（`setup.sh`）**: 導入先プロジェクトに HVE の rules・skills・agents・workflows を配る。導入先の `.claude/` 配下に symlink が無ければ、`~/.claude` は変えない。導入先の `.claude/` の HVE 資産（`rules/hve/`・`skills/hve-*`・`agents/hve-*.md`・`workflows/hve-*.js`・`scripts/hve/`）は削除してから置き直す。`.claude/CLAUDE.md` が無ければ HVE 方法論を `.claude/CLAUDE.md` として作り、あれば `.claude/CLAUDE.hve.md` を作る（上書きする）。ほかに `docs/` を作り、cq/mdq が無ければ HypervelocityEngineering を使用中の Python 環境に `pip install -e` する。HypervelocityEngineering は、既存の clone（hve-playbook の隣のディレクトリか `HVE_REPO_PATH`）があればそれを使い、無ければ隣に clone する。版は固定しない。使用中の Python 環境を汚したくなければ、venv を有効にしてから実行するか、cq/mdq を先に入れておく（詳細は[適用プロンプトの前提](docs/prompts/apply-hve-playbook.md)）
- **user-level 基盤（`sync-dotclaude.sh`）**: 作者の個人設定（[ADR-0007](knowledge/adr/0007-consolidate-user-level-rules-and-agents.md)）。`~/.claude/` を書き換える。Laravel・Livewire・sail 前提の skill と hook、Obsidian 前提の `learn` skill、Homebrew 前提の `brew-update-all` skill のほか、`settings.json` に作者の好み（`permissions.defaultMode: acceptEdits`（ファイルの編集を確認なしで通す）、`language: japanese`、`model: opus`、`env.DISABLE_AUTOUPDATER`、allow の `Bash(gh pr merge *)` など）を含む。hook も既定で有効になる。許可を求めた操作の内容（コマンドなど）を `~/.claude/logs/` に平文で追記する hook や、すべての Bash 呼び出しの前に検査する hook がある

第三者には project-level だけを勧める。下の「1. user-level 基盤の同期」は実行せず、clone して「2. プロジェクトへの HVE 導入」だけを行う。

```bash
git clone https://github.com/taito-station/hve-playbook.git
bash hve-playbook/setup.sh /path/to/my-project
```

既存のプロジェクトに入れる（再適用を含む）ときは、下の「2.」の適用プロンプトを使う。setup.sh の前に、上書きされるファイルや導入先の `.claude/` 配下の symlink を確かめる。

user-level から一部の skill などだけを使いたいときは、sync は使わず、`skills/global/<名前>/` などを自分の `~/.claude/` に手で取り込む（sync は全部を張る作りで、選べない）。HVE の規則（`rules/hve/`）には、user-level の skill（create-pr・review-pr・documentation-standards）があることを前提にした記述がある。無い場合は、該当の手順を手で行う（PR は `gh pr create` など）。

### 動作環境

対応 OS は macOS・Linux・WSL2 を想定する（確認したのは macOS）。ネイティブ Windows は、`fcntl` を使う hook があるので動かない。

| 対象 | 必須 | 任意 |
|---|---|---|
| project-level（`setup.sh` と導入先の `scripts/hve/`） | bash | git・python3・pip（cq/mdq の導入。失敗しても警告して続行する）、python3・git（`scripts/hve/` の knowledge の検査スクリプト） |
| user-level（`sync-dotclaude.sh` と hook・statusline） | bash、git、python3 3.9 以上（標準ライブラリのみ。`settings.json` の生成と hook）、jq（statusline） | gh（マージ済み PR への push の検査と一部の skill）、tmux（ペインの状態表示の hook。リポ直下の `tmux-grid.sh` も使う）、drawio・Xvfb（drawio の SVG 書き出し。一部の skill が使う）、通知音のプレイヤー（WSL2 は powershell.exe、Linux は paplay・pw-play・ffplay・aplay のどれか。無ければ鳴らない） |

### user-level を使う場合

`sync-dotclaude.sh` は、既存の `~/.claude/` を次のように扱う。

- 実体のファイル・ディレクトリが同じ名前で置いてあれば、触らずにスキップして WARN を出す（終了コード 2）。リポ版はそこに張られない
- 別の場所を指す symlink（自分の dotfiles を指す `CLAUDE.md` など）は、退避せずにリポへの symlink に張り替える。リンク先の中身は残る
- `settings.json` は、リポ版と `settings.machine.json` をマージした生成物に置き換える。実体なら、前回配置したものとも今回の生成版とも JSON として違うとき（初回を含む）に `settings.json.bak-<日時>-XXXX` へ退避する。symlink なら退避しない
- `settings.machine.json` では `model`・`language`・`permissions.defaultMode`・`env` の値などを上書きでき、hook や allow を追加できる（編集のたびに確認したいなら `permissions.defaultMode` を `default` にする）。リポ版の hook や allow は外せない（[ADR-0006](knowledge/adr/0006-generate-settings-json-with-machine-overlay.md)）

そのため、初めて sync する前に `~/.claude/` の中身を丸ごと退避する（`~/.claude` がまだ無ければ退避は要らない）。

先に、`~/.claude` の中に symlink のサブディレクトリが無いかを確かめる。`hooks`・`skills`・`rules`・`agents`・`scripts` のどれかが symlink（dotfiles 管理など）だと、sync はリンク先に項目ごとのリンクを書き込み、下の退避・戻しでは元に戻らない（リンク先に増えたリンクは手で消す）。

```bash
find ~/.claude/ -maxdepth 1 -type l
```

退避する。末尾の `/` で、`~/.claude` 自体が symlink でもリンク先の中身を複製する（sync はリンク先に書き込む）。表示された退避先のパスを控えておく。

```bash
B=~/.claude.bak-$(date +%Y%m%d%H%M%S)
cp -a ~/.claude/ "$B" && echo "$B"
```

戻すときは Claude Code をすべて終了してから、同期後の中身をどけて退避を置く。`~/.claude` が symlink なら、リンクはそのまま残してリンク先の中身を入れ替える。1 行目の右辺は、退避のときに表示されたパスに置き換える（`ls -d ~/.claude.bak-*` で探せる）。置き換えていなければ、何もせずに終わる。最後に `restored` と出れば戻っている。

```bash
B=~/.claude.bak-YYYYMMDDhhmmss
T=$(cd ~/.claude && pwd -P)
test -d "$B" && test -n "$T" && test ! -e "$T.synced" && mv "$T" "$T.synced" && mv "$B" "$T" && echo restored
```

退避のあとに増えたセッション履歴（`projects/`・`history.jsonl` など）は、戻した環境には入らない（`<実体のパス>.synced` に残るので、要るものは手で移す）。退避した写しには認証情報や履歴・ログが含まれうるので、要らなくなったら消す。

下の「冪等・何度実行しても安全」は、一度同期した環境で sync をやり直す場合のことを指す。

## セットアップ

### 1. user-level 基盤の同期

作者の個人設定。実行する前に「使う前に」の退避を行う。第三者は「2.」へ進む。

```bash
git clone https://github.com/taito-station/hve-playbook.git
bash hve-playbook/sync-dotclaude.sh
```

`sync-dotclaude.sh` は `~/.claude/` に symlink を張る（冪等・何度実行しても安全）。以降は `git -C hve-playbook pull --ff-only && bash hve-playbook/sync-dotclaude.sh --prune` を **1 回のコマンドで** 実行して最新化する。この clone で switch / checkout / rebase / merge をするときも、同じく `&& bash hve-playbook/sync-dotclaude.sh --prune` と続ける。git 操作と sync を別々に実行すると、hook を削除した更新を取り込んだとき、その間は `~/.claude/settings.json` に残った hook 行が消えたファイルを呼ぶ。その結果、Bash が全面ブロックされる。そうなったら、Claude Code の外のターミナルで `bash hve-playbook/sync-dotclaude.sh --prune` を実行して復旧する（[ADR-0010](knowledge/adr/0010-drop-serena-for-builtin-lsp.md)）。

`~/.claude/settings.json` だけは symlink ではなく、リポの `settings.json` と `~/.claude/settings.machine.json`（マシン固有の hook・permissions 等。任意）をマージした生成物になる。`~/.claude/settings.json` を直接編集しても次の同期で上書きされるため、マシン固有の設定は `settings.machine.json` に書く（user レベルの `~/.claude/settings.local.json` は Claude Code に読まれない。[ADR-0006](knowledge/adr/0006-generate-settings-json-with-machine-overlay.md)）。既存の `~/.claude/settings.json` が前回配置したものとも今回の生成版とも JSON として違えば（初回を含む）、`settings.json.bak-<日時>-XXXX` に退避してから置き換える。symlink だった場合は退避しない。生成には `python3` が必要。

`rules/global/`・`agents/global/` も同じく `~/.claude/rules/<category>`・`~/.claude/agents/<name>.md` に symlink する。これらを `~/.claude` に実体で置いていた環境は、sync が WARN でスキップする（exit 2）ので、一度だけ実体を退避して sync をやり直す（[ADR-0007](knowledge/adr/0007-consolidate-user-level-rules-and-agents.md)）。次の手順は、作者の旧環境にあった固定のファイル名を mv するもので、第三者は実行しない（存在しないファイルでエラーになる。同じ名前の実体があっても sync は WARN でスキップするだけで、自分のファイルは残り、リポ版はそこに張られない）:

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

`hve-scripts/` は導入先に配る knowledge の検査スクリプト（stale 検出・決定ログの不変性・sha の追従・hook）。setup.sh が導入先の `.claude/scripts/hve/` に置く。使い方は `rules/hve/knowledge-maturity.md` の「Stale 検出の仕組み」（[ADR-0014](knowledge/adr/0014-knowledge-check-scripts-and-sha-follow-up.md)）。

このリポジトリ自身にも pre-push で適用している。clone したら一度だけ `git -C hve-playbook config core.hooksPath .githooks` を実行して有効にする。

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
