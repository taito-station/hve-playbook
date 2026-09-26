# 既定モデルを opus エイリアスにし、既定の権限モードは acceptEdits を維持する

## ステータス

Accepted — 2026-09-26

## 背景と課題

`settings.json` は `sync-dotclaude.sh` によって `~/.claude/settings.json` に symlink され、このリポジトリを同期している全環境の user-level 設定になる。

従来の既定モデルは `claude-opus-4-6[1m]` で、特定の版に固定されていた。作者は `/model` で既定を `opus` に保存しており、リポジトリの既定と食い違っていた。

あわせて、既定の権限モードを `acceptEdits` から `auto` に変えるかを検討した。公式ドキュメント（https://code.claude.com/docs/en/permission-modes 、2026-09-26 確認）によると、`acceptEdits` で自動承認されるのは次のもの。

- `permissions.allow` に一致するもの
- 読み取り専用コマンドの組み込みセット
- 作業ディレクトリ（と `additionalDirectories`）内のファイル編集
- 同じ範囲での `mkdir` / `touch` / `rm` / `rmdir` / `mv` / `cp` / `sed`。`timeout` / `nice` / `nohup` などの wrapper を付けた形も含む

作業ディレクトリ外のパス、保護パスへの書き込み、重要パスへの `rm` / `rmdir`、それ以外の Bash（`dd` / `truncate` / `sudo` など）は都度確認になる。

## 意思決定の要因

- `ANTHROPIC_MODEL` を設定していない同期先の環境で、プロバイダが推奨する Opus に追従させたい。同期先は Anthropic API を使う前提とする。
- `opus` の解決先はプロバイダで変わる（公式ドキュメント https://code.claude.com/docs/en/model-config 、2026-09-26 確認）。Anthropic API / Claude Platform on AWS / Bedrock / Google Cloud's Agent Platform では Opus 5.5 に解決されるが、Microsoft Foundry では Opus 4.6 に解決される。`[1m]` なしで 1M になるのは、Anthropic API 上の Opus 4.7 以降に限られる。Opus 4.6 の 1M には `[1m]` が必要。
- 特定の版に固定したい環境は `ANTHROPIC_MODEL` で固定できる。`ANTHROPIC_MODEL` は settings の `model` より優先される。作者の環境は `~/.zshrc` で `claude-opus-5-5` に固定している。
- `hooks/destructive-guard.py` は、allowlist 外の mutator（`cp` / `mv` / `dd` / `truncate`）による上書きや、オプション付きの wrapper（`sudo -u root rm` など）を、自分では止めない。これらは都度確認（許可プロンプト）で止める前提で設計されている。
- ただし `acceptEdits` でも、作業ディレクトリ内の `cp` / `mv` / `rm` / `sed` は自動承認されるため、許可プロンプトが止めるのは、作業ディレクトリ外（`~/.claude` / `~/.ssh` / `/etc` など）・保護パス・重要パスへの操作と、`dd` / `truncate` / `sudo` などに限られる。
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
  - 採用理由: Anthropic API を使う同期先で、推奨される Opus に追従できる。版を固定したい環境や、Microsoft Foundry のように `opus` が旧世代に解決される環境は、`ANTHROPIC_MODEL` で版（必要なら `[1m]` 付き）を固定する。
  - 実機確認（2026-09-26、Anthropic API、`ANTHROPIC_MODEL` を外して `claude -p` で起動）: `opus` は `claude-opus-5-5` に解決され、コンテキストは 1,000,000 だった。そのため Anthropic API では `[1m]` の指定は外してよい。
- 権限モード — 選択した選択肢: **`acceptEdits` を維持する**。
  - 採用理由: 作業ディレクトリ外・保護パス・重要パスへの操作と、`dd` / `truncate` / `sudo` などは、`acceptEdits` なら許可プロンプトで止まる。destructive-guard が止めないこれらの操作に対する二段目の防御を、同期先の全環境で保つ。`auto` を使いたいときは、その都度セッション内で切り替える。

### 結果（Consequences）

- 良い結果: Anthropic API を使う同期先の既定モデルが、推奨される Opus に追従する。作業ディレクトリ外などへの破壊的操作に対する二段目の防御（許可プロンプト）が、同期先の全環境で保たれる。
- 悪い結果: `opus` は、モデルのリリースとプロバイダに応じて解決先が変わる。Microsoft Foundry では Opus 4.6 の標準コンテキストになるため、`ANTHROPIC_MODEL` での固定が要る。`auto` を使いたい場合は、セッションごとに切り替える必要がある。作業ディレクトリ内の `cp` / `mv` / `rm` / `sed` は `acceptEdits` でも自動承認されるため、destructive-guard が止めない形（allowlist 外の上書き等）には二段目の防御が無い。Pro / Max / Team プランでは Claude Code が `defaultMode` を auto に変えるかを一度尋ねるので、承諾すると symlink 先のリポジトリの `settings.json` が書き換わる。

## 選択肢の評価（Pros and Cons）

### モデル: `opus` エイリアスにする（採用）

#### メリット

- Anthropic API では、推奨される Opus に自動で追従する（2026-09-26 時点で Opus 5.5、1M）。

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

- 作業ディレクトリ外・保護パス・重要パスへの操作と、`dd` / `truncate` / `sudo` などに対して、許可プロンプトが二段目の防御として残る。

#### デメリット

- 上記の自動承認の範囲外は都度確認になり、作業が中断しやすい。

### 権限モード: `auto` を既定にする（却下）

#### メリット

- 確認による中断が減る。

#### デメリット

- hook で止めない Bash の破壊的操作のうち、`acceptEdits` なら許可プロンプトで止まるもの（作業ディレクトリ外への `cp` / `mv` による上書き、`dd`、オプション付きの `sudo` wrapper など）と、WebFetch・MCP ツール（外部送信・削除を含む）が、auto の安全判定だけで実行される。
- PermissionRequest が減り、permission-request-logger のログ・review-permissions skill・tmux の input 表示の入力が減る。

### 権限モード: `auto` にし、危険な操作を `permissions.ask` に入れる（却下）

#### メリット

- 中断を減らしつつ、指定した操作だけは確認できる。

#### デメリット

- destructive-guard が検知しない操作は、コマンドの形から網羅的に列挙できない（変数展開・`eval`・cwd 依存など）。ask の一覧では前提を置き換えきれない。

## 関連リンク

- Related: [ADR-0004 Opus 5.5 向けにプロンプト文面を監査し、規則の食い違いを揃える](0004-audit-prompts-for-opus-5-5.md)
