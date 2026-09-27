# settings.json はリポ版と settings.machine.json をマージして生成する

## ステータス

Accepted — 2026-09-27

## 背景と課題

PR #14（Issue #12）で、`~/.claude/settings.json` の同期方式を symlink からコピーに変え、マシン固有の hook（Orca 等）は `~/.claude/settings.local.json` に置く運用にした。

しかし 2026-09-27 に Claude Code v2.1.282 で実測したところ、user レベルの `~/.claude/settings.local.json` は読み込まれていなかった。

- SessionStart hook: `~/.claude/settings.json` に置くと発火し、`~/.claude/settings.local.json` に置くと発火しなかった（`claude -p` で確認）。
- `permissions.allow`: `Bash(touch ...)` を `~/.claude/settings.json` に置くと許可され、`~/.claude/settings.local.json` に置くと拒否された（`--permission-mode default` の `claude -p` で確認）。
- 公式ドキュメント（https://code.claude.com/docs/en/settings 、2026-09-27 確認）でも、`settings.local.json` は project レベル（`.claude/settings.local.json`）だけが挙がっている。

さらにコピー方式では、`sync-dotclaude.sh` を実行するたびに `~/.claude/settings.json` がリポ版で上書きされる。外部ツールが直書きした hook は同期のたびに消えるため、Issue #12 の成功条件「Orca 等のマシン固有 hook が有効なまま」を満たしていなかった。

## 意思決定の要因

- マシン固有の設定は、Claude Code が実際に読むファイル（user レベルでは `~/.claude/settings.json` だけ）に入っていなければ効かない。
- リポの `settings.json` の作業ツリーを、マシン固有の変更で dirty にしない（Issue #12 の要件）。
- 同じキーが複数のファイルにあるとき、Claude Code はリストを結合し、片方で他方を消さない（公式ドキュメント「Lists merge instead of overriding」）。

## 検討した選択肢

- sync がリポ版と `~/.claude/settings.machine.json` をマージし、`~/.claude/settings.json` を生成する
- sync が、配置済みの `~/.claude/settings.json` にあってリポ版に無い hook を、マシン固有とみなして残す
- コピー方式のまま、マシン固有の設定は `~/.claude/settings.local.json` に置く（PR #14 の方式）

## 決定内容

選択した選択肢: **sync がリポ版と `~/.claude/settings.machine.json` をマージし、`~/.claude/settings.json` を生成する**。

- マージ規則は Claude Code の設定結合に揃える: dict は再帰マージ、list はリポ版に無い要素を追記、スカラーは `settings.machine.json` 優先。リポ版の dict / list を別の型で上書きすること（例 `"hooks": null`）は、リポ版の hook や permissions を丸ごと消すため FATAL にする。
- 配置した生成版を `~/.claude/.settings.generated.json` に記録する。次の同期で `~/.claude/settings.json` がこの記録と違えば、外部ツールや UI による直接編集とみなす。キーの種類を問わず `settings.json.bak-<日時>`（パーミッション 600）に退避し、変更されたトップレベルキーを WARN に出す（終了コード 2）。直前の退避と同じ内容なら、退避を重ねない。リポや `settings.machine.json` から設定を消した結果の差分は、直接編集とみなさない。
- `settings.machine.json` が不正（JSON 不正・トップレベルが object でない・型の上書き）または `python3` が無いなら、`~/.claude/settings.json` を変えずに FATAL にする（終了コード 1）。symlink の同期と検査は続ける。
- 直接編集の判定は JSON の値で比較し、書式やキー順だけの違いは直接編集とみなさない。
- hook の実在検査は生成版に対して行い、リポ版と `settings.machine.json` の両方にある `.claude/hooks/` を含む参照を検査する。`~/.claude/hooks/` 直下（`~` / `$HOME` / `${HOME}` / `"$HOME"` / 展開済みの絶対パスのいずれの書き方も）は配置先の `hooks/` に同名の実体があるかで、それ以外の絶対パスは参照先そのものが実在するかで判定する。`$CLAUDE_PROJECT_DIR` など sync が解決できない変数で始まるパスと相対パスは検査しない。検査を通ったときだけ配置する（欠落があれば既存の `settings.json` を変えない）。それ以外の場所を指す hook（外部ツールの hook 等）の実在は検査しない。
- user レベルの `~/.claude/settings.local.json` に `hooks` / `permissions` が残っていれば、読まれない旨を WARN に出す（終了コード 2）。

### 結果（Consequences）

- 良い結果: マシン固有の hook・permissions が実際に効く。リポの作業ツリーは dirty にならない。リポから消した設定は次の同期で配置先からも消える。
- 悪い結果: 外部ツールや Claude Code の UI（`/plugin` 等）が `~/.claude/settings.json` に直接書いた設定は、`settings.machine.json` へ手で移すまで同期のたびに退避され、生成版で上書きされる。`settings.machine.json` はリポ版に追加・上書きしかできず、リポ版の hook や allow を特定のマシンだけで外すことはできない。退避ファイルは自動では消えない。直接編集の判定から上書きまでの間に外部ツールが書き込んだ内容は、退避されずに消える（ロックはしない）。`sync-dotclaude.sh` が `python3` に依存する。

## 選択肢の評価（Pros and Cons）

### リポ版と settings.machine.json をマージして生成する（採用）

#### メリット

- マシン固有の設定の置き場所が明示的で、リポ版との差分が追える。
- リポから消した設定が配置先に残らない。

#### デメリット

- 外部ツールの直書きを、ユーザーが `settings.machine.json` へ移す手間がある（退避と WARN で気づける）。

### 配置済み settings.json のリポ版に無い hook を残す（却下）

#### メリット

- 外部ツールの直書きがそのまま残り、手作業が要らない。

#### デメリット

- リポから消した hook も「リポ版に無い hook」に見えるため、配置先に残り続ける。削除した hook の実体が無ければ、その hook が発火する全 tool がブロックされる。

### コピー方式のまま settings.local.json に置く（却下）

#### メリット

- 変更が無い。

#### デメリット

- user レベルの `settings.local.json` は Claude Code に読まれず、置いた hook・permissions が効かない（上記の実測）。

## 関連リンク

- Related: [ADR-0002 dotclaude-public を hve-playbook に統合する](0002-integrate-dotclaude-public-into-hve-playbook.md)
- Issue #12 / PR #14
