#!/usr/bin/env python3
"""
Pre-Tool-Use hook for Bash that blocks code-discovery commands which
should be done via Serena's symbolic tools (mcp__serena__*) instead.

Reads tool input from stdin (JSON) and:
- Returns exit 0 (allow) when the command does not look like code discovery.
- Returns exit 2 (block) with stderr message naming the right Serena tool
  when the command pattern matches code discovery on code paths/files.

Triggered by Claude Code's PreToolUse hook with matcher="Bash".

Patterns are intentionally narrow: we only flag commands that operate on
code (paths under app/, src/, tests/, database/, routes/, lib/, config/,
bootstrap/ or files with code extensions). Non-code targets (logs, JSON,
YAML, markdown, etc.) are not blocked.

Before matching, the command is normalized to remove three sources of
false positives observed in practice (see _strip_for_match):

- heredoc bodies — `git commit -m "$(cat <<'EOF' ... EOF)"` mentioning
  code filenames in the message is not code discovery.
- grep pattern operands — `grep -e '{detect}.ts' notes.md` searches a
  markdown file; the extension is in the pattern, not the target.
- build artifacts — `wc -l lib/index.js` inspects compiled output.
  Serena reads source, so it cannot answer questions about build results.

Command names are matched as standalone tokens (see _cmd): a name embedded
in a filename or option (`session-cost-head.py`, `--tail`) does not trigger
a rule, while a path-qualified one (`/usr/bin/grep`) still does. A name
right after `:` does not match (`lint:grep`). Additionally, the matched
name must be in command position — i.e. part of the first token in a shell
segment (after `|`, `&&`, `||`, `;`, `(`, `` ` ``, or at the start). This
prevents arguments like `python3 tools/grep src/a.py` from triggering.
A newline or `&` (background operator) also starts a new segment.

Bypass: append `# via:bash-discovery: <reason>` to the command if you
have a justified reason to use bash for discovery anyway (e.g., a quick
sanity check that serena cannot do, or running tests via grep on test
names). The bypass REQUIRES a non-empty reason after the colon so it
is a conscious, documented choice rather than a habit. A bare
`# via:bash-discovery` (no colon or empty reason) does not bypass.
"""

import json
import re
import sys


CODE_PATH_PATTERN = (
    r"(?:\bapp/|\bsrc/|\btests?/|\bdatabase/|\broutes/|\blib/|\bconfig/|\bbootstrap/)"
)
CODE_EXT_PATTERN = (
    r"\.(?:php|ts|tsx|js|jsx|py|rb|go|java|kt|rs|cpp|cc|c|h|hpp|cs|swift|scala|vue)\b"
)
BLADE_EXT_PATTERN = r"\.blade\.php\b"


# コマンド名を独立したトークンとして現れたときだけ一致させる。`\bhead\b` だと `-` も単語境界になり、
# `session-cost-head.py` のようなファイル名の一部に誤爆していた。
# 直前の `/` は許す（`/usr/bin/grep` のようなパス付き起動を拾う）。直後の `/` は
# 許さない（`scripts/cat/run.py` のようなディレクトリ名は拾わない）。
def _cmd(names: str) -> str:
    return r"(?<![\w.:-])(?:" + names + r")(?![\w./-])"


# ---- 判定前に落とすノイズ（誤爆の実例に基づく） ---------------------------

# ビルド生成物・依存物のディレクトリ配下のトークン。
# Serena はソースを読むので、生成結果の確認（`wc -l lib/index.js` で関数が
# エクスポートされたか見る等）は代替できない。コード探索ではないため対象外にする。
ARTIFACT_TOKEN = re.compile(
    r"(?<!\S)\S*\b(?:lib|dist|build|out|target|node_modules|coverage|vendor)/\S*"
)

# heredoc の本体。`git commit -F -` や `cat <<'EOF'` の本文に code ファイル名が
# 出るだけで cat ルールに掛かっていた（コミットメッセージが最多の誤爆源）。
HEREDOC_BODY = re.compile(r"<<-?\s*(['\"]?)(\w+)\1.*?^\s*\2\s*$", re.S | re.M)
HEREDOC_OPEN = re.compile(r"<<-?\s*(['\"]?)\w+\1")

# クォート文字列。コミットメッセージ等の引用符内にコマンド名やコード拡張子が
# 出現する誤爆を防ぐ。パスをクォートするケース（`head "src/app.py"`）は
# 検出されなくなるが、実用上は裸パスが大半であり誤 block の方が影響が大きい。
QUOTED = re.compile(r"'[^']*'|\"[^\"]*\"")


def _strip_for_match(command: str) -> str:
    """RULES 判定用にコマンドを正規化する（bypass 判定には使わない）。"""
    c = HEREDOC_BODY.sub(" ", command)
    c = HEREDOC_OPEN.sub(" ", c)
    c = ARTIFACT_TOKEN.sub(" ", c)
    c = QUOTED.sub(" ", c)
    return c


def _in_command_position(haystack: str, match: re.Match) -> bool:
    """マッチしたコマンド名がシェルセグメントの先頭トークン内にあるか判定する。

    ``/usr/bin/grep`` のようなパス付き起動は先頭トークンなので True。
    ``python3 tools/grep`` の ``tools/grep`` は第 2 トークンなので False。
    """
    pos = match.start()
    token_start = pos
    while token_start > 0 and haystack[token_start - 1] not in (" ", "\t", "\n", "|", ";", "(", "`", "{", "&"):
        token_start -= 1
    before = haystack[:token_start].rstrip(" \t")
    if not before:
        return True
    if before[-1] in ("|", ";", "(", "`", "{", "\n", "&"):
        return True
    if len(before) >= 2 and before[-2:] in ("&&", "||"):
        return True
    return False


# Each rule: (compiled regex, reason, tool_label)
# tool_label は BYPASS_WARNINGS と結合して bypass 多用警告に使う。
# cat と head/tail/wc/less/more は同根 (read-only コード閲覧) だが、cat だけ
# bypass で Read tool 強推奨警告を出すため別ラベルに分けている。
RULES = [
    (
        re.compile(
            _cmd("grep") + r"[^|;&]*?(?:" + CODE_PATH_PATTERN + r"|"
            + CODE_EXT_PATTERN + r"|" + BLADE_EXT_PATTERN + r")"
        ),
        "コードを対象にした grep は禁止。Serena の "
        "シンボル名が分かるなら mcp__serena__find_symbol / mcp__serena__find_referencing_symbols を使う。"
        "純粋なテキスト検索はプロジェクトの検索ツール規約（HVE なら cq）に従い、無ければ理由付きで bypass を付ける。",
        "grep",
    ),
    (
        re.compile(
            _cmd("find") + r"[^|;&]*?(?:" + CODE_PATH_PATTERN + r"|-name\s+['\"][^'\"]*?(?:"
            + CODE_EXT_PATTERN + r"|" + BLADE_EXT_PATTERN + r"))"
        ),
        "コードを対象にした find は禁止。Serena の "
        "mcp__serena__find_symbol でシンボルを探す。ファイル名での検索はシンボル検索で代替できないため、必要なら bypass を付ける。",
        "find",
    ),
    (
        re.compile(
            _cmd("cat") + r"[^|;&]*?(?:"
            + CODE_EXT_PATTERN + r"|" + BLADE_EXT_PATTERN + r")"
        ),
        "コードファイルの cat は禁止。Read tool または Serena の "
        "mcp__serena__get_symbols_overview / mcp__serena__find_symbol(include_body=true) を使う。",
        "cat",
    ),
    (
        re.compile(
            _cmd("head|tail|wc|less|more") + r"[^|;&]*?(?:"
            + CODE_EXT_PATTERN + r"|" + BLADE_EXT_PATTERN + r")"
        ),
        "コードファイルの head/tail/wc/less/more は禁止。Serena の "
        "mcp__serena__get_symbols_overview / mcp__serena__find_symbol(include_body=true) を使う。",
        "read-family",
    ),
    (
        re.compile(
            _cmd("ls") + r"[^|;&]*?-[a-zA-Z]*R[a-zA-Z]*\b[^|;&]*?(?:" + CODE_PATH_PATTERN + r")"
        ),
        "コード配下の再帰 ls は禁止。Serena の "
        "mcp__serena__get_symbols_overview でファイル内の構造を見る。ディレクトリ一覧はシンボル検索で代替できないため、必要なら bypass を付ける。",
        "ls-R",
    ),
]


# tool_label 別の bypass 多用警告。
# bypass マッチ時 (= block しない経路) に該当ラベルの警告を stderr に出すことで、
# 真に必要な bypass (例: find -path / ls / git ls-tree) は妨げず、serena で
# 代替可能な tool (grep / cat) の習慣的多用を抑制する。
# 警告は出すが block はしない (= bypass の意図は尊重)。
BYPASS_WARNINGS = {
    "grep": (
        "[serena-enforcer] WARN: grep の bash-discovery bypass を使用。"
        "シンボル名が分かる探索なら mcp__serena__find_symbol (定義) / "
        "mcp__serena__find_referencing_symbols (参照) を検討してください。"
    ),
    "cat": (
        "[serena-enforcer] WARN: cat の bash-discovery bypass は Read tool 代替推奨。"
        "既知パスは Read tool の方が安全 (line range / offset 制御 / 大ファイル truncation)。"
    ),
    # find / read-family (head/tail/wc/less/more) / ls-R は WARN なし (現状維持)。
    # find はパスベース検索で serena 代替が薄く、ls-R / read-family は頻度低く
    # 観察上も多用傾向が見られなかったため。
}


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except Exception as e:
        print(f"[serena-enforcer] failed to parse payload: {e}", file=sys.stderr)
        return 0

    tool_name = payload.get("tool_name") or payload.get("toolName")
    tool_input = payload.get("tool_input") or payload.get("toolInput") or {}

    if tool_name != "Bash":
        return 0

    command = tool_input.get("command", "") or ""
    if not isinstance(command, str):
        return 0

    # まず RULES に対してマッチ判定 (どの tool 系のコード探索コマンドか特定)。
    # マッチしなければ何もせず exit 0 (= block 対象外コマンドはそのまま通す)。
    # 判定は正規化後の文字列に対して行う（heredoc 本体 / grep のパターン /
    # ビルド生成物は「コード探索」ではないため）。bypass 判定は原文に対して行う。
    haystack = _strip_for_match(command)
    matched_reason = None
    matched_tool_label = None
    for pattern, reason, tool_label in RULES:
        for m in pattern.finditer(haystack):
            if _in_command_position(haystack, m):
                matched_reason = reason
                matched_tool_label = tool_label
                break
        if matched_reason:
            break

    if matched_reason is None:
        return 0

    # Bypass requires a non-empty reason after the colon:
    #   `# via:bash-discovery: <reason>`
    # A bare `# via:bash-discovery` (no colon or empty/whitespace-only reason)
    # is not enough — this makes the bypass a deliberate, documented choice.
    if re.search(r"#\s*via:bash-discovery\s*:\s*\S+", command):
        # bypass あり → block しないが、tool_label 別の警告があれば出す
        # (grep / cat の習慣的多用を stderr 痕跡で抑制)。
        warning = BYPASS_WARNINGS.get(matched_tool_label)
        if warning:
            print(warning, file=sys.stderr)
        return 0

    # bypass なし → 既存の block 挙動
    print(
        "BLOCKED by serena-enforcer hook.\n"
        f"reason: {matched_reason}\n"
        "Use Serena's symbolic tools (mcp__serena__*) instead.\n"
        "Bypass (only with conscious justification): append "
        "`# via:bash-discovery: <reason>` to the command.\n"
        "The reason after the colon must be non-empty so each bypass "
        "is a documented choice, not a habit.",
        file=sys.stderr,
    )
    return 2


if __name__ == "__main__":
    sys.exit(main())
