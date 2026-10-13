#!/bin/bash
# Regression tests for hooks/plan-gate-check.py
#
# 実行: bash tests/test_plan_gate_check.sh
#
# plan-gate-check は PermissionRequest (matcher: ExitPlanMode) の hook。
# 計画本文に「ゲートの確認結果」「ルール準拠表」の見出しが揃っていなければ、
# stdout に decision.behavior=deny の JSON を出す (exit 0)。
# 通すときは何も出さずに exit 0 (承認画面へ進む)。
#
# 各テストは run で包み、PASS / FAIL を数えて最後に終了コードを決める。

HOOK="$(cd "$(dirname "$0")/.." && pwd)/hooks/plan-gate-check.py"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
FAIL=0

run() {
    local name="$1"; shift
    if "$@"; then
        echo "[PASS] $name"
    else
        echo "[FAIL] $name"
        FAIL=$((FAIL + 1))
    fi
}

# ExitPlanMode の PermissionRequest payload を組み立てて hook に流し、stdout を返す。
# 引数: 計画本文 (空文字なら plan キーを入れない) / planFilePath (空文字なら入れない)
_out() {
    python3 -c '
import json, sys
ti = {}
if sys.argv[1]:
    ti["plan"] = sys.argv[1]
if sys.argv[2]:
    ti["planFilePath"] = sys.argv[2]
print(json.dumps({"hook_event_name": "PermissionRequest", "tool_name": "ExitPlanMode",
                  "permission_mode": "plan", "tool_input": ti}))
' "$1" "${2:-}" | python3 "$HOOK" 2>/dev/null
}

# deny の JSON が出ていて、message に $2 (省略可) を含み、exit 0
# (PermissionRequest の decision は exit 0 のときだけ解釈される)
denied() {
    local out rc
    out="$(_out "$1" "${3:-}")"; rc=$?
    [ "$rc" = "0" ] || return 1
    python3 -c '
import json, sys
d = json.loads(sys.argv[1])
h = d["hookSpecificOutput"]
assert h["hookEventName"] == "PermissionRequest"
assert h["decision"]["behavior"] == "deny"
assert sys.argv[2] in h["decision"]["message"]
' "$out" "${2:-}" 2>/dev/null
}

# 何も出さない (= 承認画面へ進む) かつ exit 0
allowed() {
    local out rc
    out="$(_out "$1" "${2:-}")"; rc=$?
    [ "$rc" = "0" ] && [ -z "$out" ]
}

GATE='## ゲートの確認結果
- Step 2: ADR 0003 を確認した'
TABLE='## ルール準拠表
| ルール | 状態 | 対応 |
|---|---|---|
| implement-flow | 準拠 | Step 2〜4 済み |'

# ---------- 通す ----------
run "A1: 2 見出しと表の行が揃えば通す" \
    allowed "# 計画
$GATE

$TABLE"

run "A5: 見出しの前後の語・括弧書きと #### を許容" \
    allowed "## implement-flow ゲートの確認結果（Step 1〜4）
- 済み
#### ルール準拠表（自己監査）
| a | b | c |"

run "A8: 対象外の計画は『対象外: 理由』で通す" \
    allowed "## ゲートの確認結果
対象外: ドキュメントのみの変更
$TABLE"

run "A17: 準拠表の下位見出しの中の表も数える" \
    allowed "$GATE
## ルール準拠表
### 規則
| a | b | c |"

run "A18: 長いフェンスの中の短いフェンスで状態を反転させない" \
    allowed "$GATE
\`\`\`\`markdown
\`\`\`
\`\`\`\`
$TABLE"

run "A19: ~~~ のフェンスの中の \`\`\` で状態を反転させない" \
    allowed "$GATE
~~~
\`\`\`
~~~
$TABLE"

run "A20: 行頭に 3 つまでの空白がある見出しも数える" \
    allowed "   ## ゲートの確認結果
- 済み
  ## ルール準拠表
| a | b | c |"

PLANFILE="$TMP/plan.md"
printf '%s\n\n%s\n' "$GATE" "$TABLE" > "$PLANFILE"
run "A10: plan が無くても planFilePath の中身で判定して通す" \
    allowed "" "$PLANFILE"

# ---------- 止める ----------
run "A2: ゲートの確認結果が無ければ deny" \
    denied "$TABLE" "「ゲートの確認結果」の見出し:"

run "A3: ルール準拠表が無ければ deny" \
    denied "$GATE" "「ルール準拠表」の見出し:"

run "A4: ルール準拠表に表の行が無ければ deny" \
    denied "$GATE
## ルール準拠表
すべて準拠" "1 行も無い"

run "A15: 表の行が別の節にしか無ければ deny" \
    denied "$GATE
## ルール準拠表
すべて準拠
## リスク
| a | b |" "1 行も無い"

run "A6: ##### の見出しは数えない" \
    denied "##### ゲートの確認結果
$TABLE" "ゲートの確認結果"

run "A16: 見出しでない行の語は数えない" \
    denied "ゲートの確認結果: 済み
$TABLE" "ゲートの確認結果"

run "A7: コードフェンスの中の見出しは数えない" \
    denied '```markdown
## ゲートの確認結果
## ルール準拠表
| a | b | c |
```' "ゲートの確認結果"

run "A9: plan も planFilePath も無い ({}) なら deny" \
    denied "" "計画本文"

run "A11: planFilePath のファイルが無ければ deny" \
    denied "" "計画本文" "$TMP/missing.md"

printf '## 計画\n\xff\xfe 不正なバイト\n' > "$TMP/bad-utf8.md"
run "A22: planFilePath が不正な UTF-8 でも読んで見出しを検査する" \
    denied "" "ゲートの確認結果" "$TMP/bad-utf8.md"

mkfifo "$TMP/fifo"
run "A21: planFilePath が通常のファイルでなければ読まずに deny (FIFO で待たない)" \
    denied "" "計画本文" "$TMP/fifo"

# ---------- 対象外・fail-open ----------
other_tool_allowed() {
    local out
    out="$(echo '{"hook_event_name":"PermissionRequest","tool_name":"Bash","tool_input":{"command":"ls"}}' \
        | python3 "$HOOK" 2>/dev/null)"
    [ "$?" = "0" ] && [ -z "$out" ]
}
run "A12: ExitPlanMode 以外の tool は対象外" other_tool_allowed

other_event_allowed() {
    local out
    out="$(echo '{"hook_event_name":"PreToolUse","tool_name":"ExitPlanMode","tool_input":{}}' \
        | python3 "$HOOK" 2>/dev/null)"
    [ "$?" = "0" ] && [ -z "$out" ]
}
run "A14: PermissionRequest 以外の event は対象外" other_event_allowed

broken_json_allowed() {
    local out
    out="$(echo 'not json' | python3 "$HOOK" 2>/dev/null)"
    [ "$?" = "0" ] && [ -z "$out" ]
}
run "A13: 壊れた JSON は通す (fail-open)" broken_json_allowed

if [ "$FAIL" -gt 0 ]; then
    echo "=== $FAIL test(s) FAILED ==="
    exit 1
fi
echo "=== ALL TESTS PASSED ==="
