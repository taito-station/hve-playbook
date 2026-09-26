# 既定モデルを opus エイリアスにし、既定の権限モードは acceptEdits を維持する

## ステータス

Accepted — 2026-09-26

## 背景と課題

`settings.json` は `sync-dotclaude.sh` によって `~/.claude/settings.json` に symlink され、このリポジトリを同期している全環境の user-level 設定になる。

従来の既定モデルは `claude-opus-4-6[1m]` で、特定の版に固定されていた。作者は `/model` で既定を `opus` に保存しており、リポジトリの既定と食い違っていた。

あわせて、既定の権限モードを `acceptEdits` から `auto` に変えるかを検討した。`acceptEdits` では、ファイル編集と `permissions.allow` に一致するものが自動承認され、それ以外は都度確認になる。

## 意思決定の要因

- `ANTHROPIC_MODEL` を設定していない同期先の環境で、最新の Opus に追従させたい。
- 特定の版に固定したい環境は `ANTHROPIC_MODEL` で固定できる。`ANTHROPIC_MODEL` は settings の `model` より優先される。作者の環境は `~/.zshrc` で `claude-opus-5-5` に固定している。
- `hooks/destructive-guard.py` は、allowlist 外の mutator（`cp` / `mv` / `dd` / `truncate`）による上書きや、オプション付きの wrapper（`sudo -u root rm` など）を、自分では止めない。これらは都度確認（許可プロンプト）で止める前提で設計されている。
- PreToolUse hook のうち、安全ガードは destructive-guard・git-push-merged-pr-check・sail-env-inline-block・sql-schema-check。serena-enforcer と skill-enforcer は、探索手段や skill への誘導が目的。いずれの hook も、WebFetch・MCP ツールなどは止めない。

## 検討した選択肢

### モデル

- `opus` エイリアスにする
- `claude-opus-5-5` のように版を固定する
- `claude-opus-4-6[1m]` を維持する

### 権限モード

- `acceptEdits` を維持する
- `auto` を既定にする
- `auto` を既定にし、危険な操作を `permissions.ask` に入れる

## 決定内容

- モデル — 選択した選択肢: **`opus` エイリアスにする**。
  - 採用理由: 同期先の環境で最新の Opus に追従でき、版を固定したい環境は `ANTHROPIC_MODEL` で固定できる。
  - 実機確認（2026-09-26、`ANTHROPIC_MODEL` を外して `claude -p` で起動）: `opus` は `claude-opus-5-5` に解決され、コンテキストは 1,000,000 だった。そのため `[1m]` の指定は外してよい。
- 権限モード — 選択した選択肢: **`acceptEdits` を維持する**。
  - 採用理由: destructive-guard は、自分で止めない破壊的操作を許可プロンプトで止める前提で設計されている。この前提を、同期先の全環境で保つ。`auto` を使いたいときは、その都度セッション内で切り替える。

### 結果（Consequences）

- 良い結果: 同期先の既定モデルが最新の Opus に追従する。破壊的操作に対する二段目の防御（許可プロンプト）が、同期先の全環境で保たれる。
- 悪い結果: `opus` は、モデルのリリースに応じて解決先が変わる。`auto` を使いたい場合は、セッションごとに切り替える必要がある。

## 選択肢の評価（Pros and Cons）

### モデル: `opus` エイリアスにする（採用）

#### メリット

- 最新の Opus に自動で追従する。

#### デメリット

- 解決先がリリースに応じて変わり、再現性が下がる（固定は `ANTHROPIC_MODEL` で行う）。

### モデル: 版を固定する（却下）

#### メリット

- 解決先が変わらない。

#### デメリット

- 新しい版が出るたびに `settings.json` の更新が要る。固定したい環境は `ANTHROPIC_MODEL` で個別に固定できる。

### モデル: `claude-opus-4-6[1m]` を維持する（却下）

#### メリット

- 変更が無い。

#### デメリット

- 作者が `/model` で保存した既定と食い違ったままになり、旧世代のモデルが既定になる。

### 権限モード: `acceptEdits` を維持する（採用）

#### メリット

- destructive-guard の設計の前提（許可プロンプトが二段目の防御）が保たれる。

#### デメリット

- ファイル編集と allow 以外は都度確認になり、作業が中断しやすい。

### 権限モード: `auto` を既定にする（却下）

#### メリット

- 確認による中断が減る。

#### デメリット

- hook で止めない Bash の破壊的操作（`cp` / `mv` / `dd` による上書き、オプション付きの `sudo` wrapper など）、WebFetch・MCP ツール（外部送信・削除を含む）が、auto の安全判定だけで実行される。
- PermissionRequest が減り、permission-request-logger のログ・review-permissions skill・tmux の input 表示の入力が減る。

### 権限モード: `auto` にし、危険な操作を `permissions.ask` に入れる（却下）

#### メリット

- 中断を減らしつつ、指定した操作だけは確認できる。

#### デメリット

- destructive-guard が検知しない操作は、コマンドの形から網羅的に列挙できない（変数展開・`eval`・cwd 依存など）。ask の一覧では前提を置き換えきれない。

## 関連リンク

- Related: [ADR-0004 Opus 5.5 向けにプロンプト文面を監査し、規則の食い違いを揃える](0004-audit-prompts-for-opus-5-5.md)
