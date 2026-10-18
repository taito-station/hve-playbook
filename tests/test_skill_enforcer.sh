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
run "E4: gh pr new (create のエイリアス) も止める" blocked "gh pr new --title x --body-file b.md"
run "E5: gh pr new も # via:create-pr で通す" allowed "gh pr new --title x --body-file b.md # via:create-pr"
run "E6: gh pr newer のような別の語には当たらない" allowed "gh pr newer"

# ---------- グローバルフラグ -R / --repo を挟んだ PR 作成 (Issue #76) ----------
repo_flag_blocked() {
    blocked "gh -R o/r pr new --title x" \
        && blocked "gh -R o/r pr create --title x" \
        && blocked "gh --repo o/r pr create --title x" \
        && blocked "gh --repo=o/r pr create --title x" \
        && blocked "gh -Ro/r pr new --title x" \
        && blocked "gh pr -R o/r create --title x" \
        && blocked "gh pr --repo=o/r new --title x"
}
run "E7: pr の前後に -R / --repo を置いた PR 作成も止める" repo_flag_blocked
repo_flag_via_allowed() {
    allowed "gh -R o/r pr new --title x # via:create-pr" \
        && allowed "gh --repo=o/r pr create --title x # via:create-pr" \
        && allowed "gh pr -R o/r create --title x # via:create-pr"
}
run "E8: -R / --repo を置いた形も # via:create-pr で通す" repo_flag_via_allowed
repo_flag_other_allowed() {
    allowed "gh -R o/r pr list" \
        && allowed "gh --repo o/r pr view 1" \
        && allowed "gh pr -R o/r list" \
        && allowed "gh -R o/r issue create --title x" \
        && allowed "gh -R o/r pr newer"
}
run "E9: -R / --repo を置いても PR 作成でないコマンドは通す" repo_flag_other_allowed

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
run "M5: gh pr new も # via:create-pr を案内する" blocked_with "gh pr new --title x" create-pr
run "M6: -R / --repo を置いた形も # via:create-pr を案内する" blocked_with "gh --repo o/r pr create --title x" create-pr

# ---------- create-pr の手順との契約 (Issue #71) ----------
# 正規の経路である create-pr の PR 作成コマンドが、skill-enforcer に止められないこと
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
CREATE_PR="$ROOT/skills/global/create-pr/SKILL.md"
create_pr_lines_allowed() {
    local line n=0
    while IFS= read -r line; do
        n=$((n + 1))
        allowed "$line" || return 1
    done < <(grep -E '^[[:space:]]*gh pr (create|new) ' "$CREATE_PR")
    [ "$n" -gt 0 ]
}
run "C1: create-pr の PR 作成コマンドは 1 行ずつ skill-enforcer を通る" create_pr_lines_allowed
# Step 6 の squash は、本文をコマンドに入れず -F でファイルから渡す (本文中の PR 作成コマンドの文字列で止められないため)
squash_uses_file() {
    grep -qE '^[[:space:]]*git commit -F "\$REPO_ROOT/docs/temp/squash-msg\.txt"' "$CREATE_PR" \
        && ! grep -qE '^[[:space:]]*git commit -m "<タイトル>' "$CREATE_PR"
}
run "C2: create-pr Step 6 の squash は git commit -F でメッセージを渡す" squash_uses_file
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
