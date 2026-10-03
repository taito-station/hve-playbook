# serena MCP と serena-enforcer を撤廃し、組み込みの LSP ツールと grep に寄せる

## ステータス

Accepted — 2026-10-03

## 背景と課題

これまでコード探索は「serena MCP 優先」とし、PreToolUse hook の `hooks/serena-enforcer.py` が、コードを対象にした grep・find・cat などを block して serena に誘導していた（ADR-0005 では「探索手段への誘導が目的の hook」と分類している）。

2026-10-03 のセッションで、Claude Code に組み込みの `LSP` ツールがあることを確認した。このツールは `goToDefinition`・`findReferences`・`workspaceSymbol`・`incomingCalls` などを持ち、serena の `find_symbol` / `find_referencing_symbols` と役割が重なる。ただし、その言語の LSP server が設定されている必要がある（言語ごとに LSP plugin を有効化する）。導入先で主に使う言語（PHP など）で LSP plugin が使えるかは未確認。

一方、serena を残すことには次のコストがあった。

- MCP ツール定義（約 25 個）が毎セッションのコンテキストを使う。プロジェクトごとの activate も必要
- `.claude/worktrees/` が index 対象に入るとメモリが膨らみ、OOM を起こす（worktree 7 個で serena 単体 6.6GB を観測した。対策の節が `skills/global/parallel-setup/SKILL.md` にあった）
- enforcer の block を `# via:bash-discovery: <理由>` で回避する作法が必要。今回の調査中にもサブエージェントの Bash が 2 回 block された

問い: serena と enforcer を維持する価値はまだあるか。

## 意思決定の要因

- 会話中のシンボル探索（定義・参照）ができること
- 常駐コスト（コンテキスト・メモリ）と運用の摩擦を減らす
- 要件にない仕組みを足さない（no-overengineering）

## 検討した選択肢

- serena MCP と serena-enforcer を維持する
- CodeQL に置き換える
- 組み込みの LSP ツールと grep / Read に寄せ、serena と enforcer を撤廃する

## 決定内容

選択した選択肢: **組み込みの LSP ツールと grep / Read に寄せ、serena と enforcer を撤廃する**。

組み込みの LSP ツールで serena の主な用途（定義・参照の検索）を賄え、追加の MCP サーバーや hook が要らないため。

- `hooks/serena-enforcer.py` と `tests/test_serena_enforcer.sh` を削除し、`settings.json` から hook 行を外す
- `CLAUDE.md`・`rules/hve/tool-usage.md`・各 skill の探索方針を「LSP ツール（plugin がある言語）→ grep で絞って Read」に書き換える
- HVE プロジェクトでの cq/mdq の優先順位は変えない
- LSP を強制する hook は新設しない
- 1 つの PR で hook 行と実体ファイルを同時に削除する。各マシンでは次の手順で移行する
  1. `git -C <clone> pull --ff-only && bash <clone>/sync-dotclaude.sh --prune` を 1 回の Bash で実行する。pull に限らず、配備元の clone で作業ツリーの hook ファイルを消しうる git 操作（switch / checkout / rebase / merge）も、同じように `&& bash <clone>/sync-dotclaude.sh --prune` と続けて実行する。git 操作と sync を分けると、その間は配置済みの `~/.claude/settings.json` に残った hook 行が消えたファイルを呼び、Bash が全面ブロックされる
  2. 全面ブロックされたら、Claude Code の外のターミナルで `bash <clone>/sync-dotclaude.sh --prune` を実行して復旧する
  3. `claude mcp remove serena -s user` で MCP の登録を外す
  4. `~/.claude/settings.machine.json` に `mcp__serena__*` の allow があれば削除し、sync を再実行する
  5. 導入先の HVE プロジェクトでは、`setup.sh` を再実行して `rules/hve/tool-usage.md` を更新する（コピーで配っているため、再実行するまで旧版が残る）

### 結果（Consequences）

- 良い結果: serena のツール定義と常駐プロセスが無くなり、serena の worktree による OOM 対策も不要になる。grep に bypass マーカーを付ける作法が無くなる
- 悪い結果: LSP plugin が無い言語では、シンボル単位の参照検索ができず grep に頼る。探索の規律は hook による強制から CLAUDE.md の方針に戻るため、無計画な全文検索を機械的には止められない

## 選択肢の評価（Pros and Cons）

### serena MCP と serena-enforcer を維持する（却下）

#### メリット

- LSP plugin の有無に関係なく、serena が対応する言語でシンボル探索ができる
- hook により探索の規律を機械的に強制できる

#### デメリット

- 「背景と課題」に挙げたコスト（コンテキスト、OOM、bypass 作法）が続く
- 組み込みの LSP ツールと機能が重複する

### CodeQL に置き換える（却下）

#### メリット

- データフローやセキュリティの解析ができる

#### デメリット

- 解析用データベースの構築が前提のバッチ解析で、編集のたびの会話中の探索には向かない（一般的な性質に基づく判断で、このリポジトリでは実測していない）
- 用途が静的解析（CI 向け）で、serena の代わりにはならない

### 組み込みの LSP ツールと grep / Read に寄せる（採用）

#### メリット

- Claude Code の標準機能だけで済み、MCP サーバーや hook の保守が要らない
- 定義・参照・呼び出し階層まで扱える

#### デメリット

- 言語ごとに LSP plugin を有効化する必要がある
- 探索の規律は方針の記述に頼る

## 関連リンク

- Related: [0005-default-model-opus-alias](0005-default-model-opus-alias.md)（「意思決定の要因」の hook の分類で serena-enforcer を挙げている。この hook は本 ADR で撤廃したので、その記述は現状を表さない。0005 の決定内容（既定モデル・権限モード）は変わらない）
- Related: [0006-generate-settings-json-with-machine-overlay](0006-generate-settings-json-with-machine-overlay.md)（hook 実体の欠落による全 tool ブロックを防ぐ sync の検査）
