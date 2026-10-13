#!/bin/bash
# Regression tests for hooks/skill-enforcer.py
#
# 実行: bash tests/test_skill_enforcer.sh
#
# skill-enforcer は stateless (stdin の JSON コマンド文字列のみ判定する) なので
# HOME 隔離は不要。リポ実体の hook を直接叩く。exit 2 = block / exit 0 = allow を検証する。
# bypass は、当たったルールのルート名と完全に一致する `# via:<ルート名>` だけ (Issue #62)。

HOOK="$(cd "$(dirname "$0")/.." && pwd)/hooks/skill-enforcer.py"
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

# Bash payload を生成して hook に流し、exit code を返す
_rc() {
    python3 -c 'import json,sys; print(json.dumps({"tool_name":"Bash","tool_input":{"command":sys.argv[1]}}))' "$1" \
        | python3 "$HOOK" >/dev/null 2>&1
    echo $?
}

blocked() { [ "$(_rc "$1")" = "2" ]; }
allowed() { [ "$(_rc "$1")" = "0" ]; }

# 止めたうえで、stderr の案内が指定ルートの via を示すか
blocked_with() {
    local err
    err="$(python3 -c 'import json,sys; print(json.dumps({"tool_name":"Bash","tool_input":{"command":sys.argv[1]}}))' "$1" \
        | python3 "$HOOK" 2>&1 >/dev/null)"
    [ "$?" = "2" ] && printf '%s' "$err" | grep -qF -- "append \`# via:$2\`"
}

PR="gh pr create --title x --body-file b.md"
DRAWIO="drawio --export -f svg -o a.svg a.drawio"

# ---------- block / allow ----------
run "E1: gh pr create は止める" blocked "$PR"
run "E2: drawio --export は止める" blocked "$DRAWIO"
run "E3: ルールに当たらないコマンドは通す" allowed "git status"

# ---------- bypass: ルート名の完全一致 ----------
run "E10: # via:create-pr で gh pr create を通す" allowed "$PR # via:create-pr"
run "E11: # via:run-drawio-export で drawio を通す" allowed "$DRAWIO # via:run-drawio-export"
run "E12: 別の hook の via (main-commit-ok) では通さない" blocked "git commit -m x # via:main-commit-ok: 理由
$PR"
run "E13: 別の hook の via (destructive-ok) では通さない" blocked "$PR # via:destructive-ok: x"
run "E14: ルート名の前方一致 (create-prx) では通さない" blocked "$PR # via:create-prx"
run "E15: 別ルートの via (drawio に create-pr) では通さない" blocked "$DRAWIO # via:create-pr"
run "E16: 2 ルールに当たるとき、片方の via だけでは通さない" blocked "$DRAWIO && $PR # via:create-pr"
run "E17: 2 ルールに当たるとき、両方の via があれば通す" allowed "$DRAWIO && $PR # via:create-pr # via:run-drawio-export"
suffix_blocked() { blocked "$PR # via:create-prX" && blocked "$PR # via:create-pr.x" && blocked "$PR # via:create-pr:x"; }
run "E18: ルート名に大文字・記号が続く via (create-prX / create-pr.x / create-pr:x) では通さない" suffix_blocked
quoted_blocked() {
    blocked "gh pr create --title 'x # via:create-pr' --body-file b.md" \
        && blocked "gh pr create --title \"x # via:create-pr\" --body-file b.md"
}
run "E19: クォート内の via では通さない" quoted_blocked
adjacent_blocked() {
    blocked "gh pr create --title 'x'# via:create-pr --body-file b.md" \
        && blocked "gh pr create --title \"a\"# via:create-pr --body-file b.md" \
        && blocked "gh pr create --title x\\ # via:create-pr"
}
run "E19c: クォート直後・エスケープした空白の後の # (シェルではコメントにならない) では通さない" adjacent_blocked
run "E22: 理由付きの via (# via:create-pr: 理由) は通す" allowed "$PR # via:create-pr: create-pr skill の Step 7"
unpaired_allowed() {
    allowed "cat > b.md <<EOF
It's fine
EOF
$PR # via:create-pr
echo 'done'"
}
run "E23: 別の行の対にならない ' があっても、正しい via は通す" unpaired_allowed
run "E19b: 単語の途中の # に続く via では通さない" blocked "$PR#via:create-pr"

# ---------- message の案内 ----------
run "M1: gh pr create は # via:create-pr を案内する" blocked_with "$PR" create-pr
run "M2: drawio は # via:run-drawio-export を案内する" blocked_with "$DRAWIO" run-drawio-export
run "M3: 別の hook の via が付いていても # via:create-pr を案内する" blocked_with "$PR # via:main-commit-ok: x" create-pr
run "M4: 2 ルールで片方の via だけなら、足りない側の via を案内する" blocked_with "$DRAWIO && $PR # via:create-pr" run-drawio-export

# ---------- 対象外・fail-open ----------
other_tool_allowed() {
    echo '{"tool_name":"Read","tool_input":{"file_path":"x"}}' | python3 "$HOOK" >/dev/null 2>&1
}
run "E20: Bash 以外の tool は対象外" other_tool_allowed

broken_json_allowed() {
    echo 'not json' | python3 "$HOOK" >/dev/null 2>&1
}
run "E21: 壊れた JSON は通す (fail-open)" broken_json_allowed

if [ "$FAIL" -gt 0 ]; then
    echo "=== $FAIL test(s) FAILED ==="
    exit 1
fi
echo "=== ALL TESTS PASSED ==="
