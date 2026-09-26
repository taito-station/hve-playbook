# 既定の権限モードを auto にし、既定モデルを opus エイリアスにする

## ステータス

Accepted — 2026-09-26

## 背景と課題

`settings.json` は `sync-dotclaude.sh` によって `~/.claude/settings.json` に symlink され、このリポジトリを同期している全環境の user-level 設定になる。

従来の既定は次のとおりだった。

- `permissions.defaultMode: acceptEdits`: ファイル編集だけを自動承認し、それ以外は都度確認する。
- `model: claude-opus-4-6[1m]`: 特定の版に固定していた。

作者は実際には auto モードで作業しており、`/model` で既定を `opus` に保存していた。この実態と、リポジトリの既定値が食い違っていた。

## 意思決定の要因

- 実際の運用（auto モード、最新の Opus）と、リポジトリの既定を一致させたい。
- auto モードでは、ファイル編集以外（Bash・WebFetch・MCP ツール）も、auto モードの安全判定だけで実行される。
- PreToolUse hook（destructive-guard / serena-enforcer / skill-enforcer / git-push-merged-pr-check / sail-env-inline-block / sql-schema-check）が止めるのは、Bash と Write に限られる。
- `permissions.deny` は未設定。

## 検討した選択肢

- auto を既定にし、残るリスクを記録する。
- 外部送信・削除系の MCP ツールを `permissions.ask` に入れたうえで auto にする。
- acceptEdits を維持する。

## 決定内容

- **権限モード**: auto を既定にし、残るリスクをこの ADR に記録する。
  - 採用理由: 作者の実運用がすでに auto で、確認の頻度より作業の連続性を優先している。Bash の破壊的操作は、従来どおり PreToolUse hook が止める。
- **モデル**: `opus` エイリアスを既定にする。
  - 採用理由: 最新の Opus に追従できる。特定の版に固定したい環境では `ANTHROPIC_MODEL` で固定する（`ANTHROPIC_MODEL` は settings の `model` より優先される）。
  - 実機確認（2026-09-26、`ANTHROPIC_MODEL` を外して `claude -p` で起動）: `opus` は `claude-opus-5-5` に解決され、コンテキストは 1,000,000 だった。そのため `[1m]` の指定は外してよい。

### 結果（Consequences）

- **良い結果**
  - リポジトリの既定が実際の運用と一致する。
  - 確認プロンプトによる中断が減る。
- **悪い結果**
  - Bash 以外（WebFetch・MCP ツール）は、auto モードの安全判定だけで実行される。MCP ツールには、Gmail の送信・転送・削除のような外部に影響する操作も含まれる。これらを止める hook や deny は無い。
  - 確認プロンプトが減るため、PermissionRequest 由来の情報が減る。具体的には次の 3 つ。
    - `hooks/permission-request-logger.py` のログ（`~/.claude/logs/permission-requests.jsonl`）
    - それを入力にする `review-permissions` skill
    - `tmux-pane-awaiting.sh` の input（赤）表示
  - `opus` は、モデルのリリースに応じて解決先が変わる。

## 選択肢の評価（Pros and Cons）

### 外部送信・削除系の MCP ツールを ask にしたうえで auto にする（却下）

#### メリット

- 外部に影響する操作だけは、毎回確認できる。

#### デメリット

- 接続される MCP サーバーは環境ごとに違うので、ツール名の一覧を共有設定で保守し続ける必要がある。
- 現時点の運用で必要としていない。必要になった時点で追加する。

### acceptEdits を維持する（却下）

#### メリット

- ファイル編集以外は、従来どおり毎回確認できる。

#### デメリット

- 作者の実運用（auto）とリポジトリの既定が食い違ったままになる。

## 関連リンク

- Related: [ADR-0004 Opus 5.5 向けにプロンプト文面を監査し、規則の食い違いを揃える](0004-audit-prompts-for-opus-5-5.md)
