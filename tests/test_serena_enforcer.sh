#!/bin/bash
# hooks/serena-enforcer.py の block / allow 判定を固定する検査
#
# 実行: bash tests/test_serena_enforcer.sh
#
# コマンド名 (grep / find / cat / head / tail / wc / less / more / ls) は、ファイル名や
# オプションの一部 (例: session-cost-head.py / --tail / cat-notes.py) ではなく、
# コマンドとして現れたときだけ判定対象にする。

set -u
HOOK="${SERENA_ENFORCER:-$(cd "$(dirname "$0")/.." && pwd)/hooks/serena-enforcer.py}"

FAIL=0
check() {  # $1=期待 (block|allow) $2=説明 $3=コマンド
    local json rc got
    json=$(python3 -c 'import json,sys; print(json.dumps({"tool_name":"Bash","tool_input":{"command":sys.argv[1]}}))' "$3")
    printf '%s' "$json" | python3 "$HOOK" >/dev/null 2>&1
    rc=$?
    if [ "$rc" -eq 2 ]; then got=block; else got=allow; fi
    if [ "$got" = "$1" ]; then
        echo "[PASS] $2"
    else
        echo "[FAIL] $2 (期待 $1 / 実際 $got): $3"
        FAIL=1
    fi
}

# コマンドとして現れたら block
check block "head でコードファイルを読む" "head -20 src/app.py"
check block "パイプ後の tail でコードファイル" "echo x | tail -5 src/app.py"
check block "wc でコードファイル" "wc -l app/Models/User.php"
check block "cat でコードファイル" "cat src/index.ts"
check block "grep でコード配下" "grep -rn foo src/"
check block "find でコード配下" "find app/ -name '*.php'"
check block "ls -R でコード配下" "ls -R src/"
check block "&& の後の head" "cd /tmp && head -3 main.go"

# ファイル名・オプションの一部なら allow
check allow "ファイル名に head を含む .py を実行" "python3 /tmp/session-cost-head.py"
check allow "ファイル名に tail を含む .py を引数に渡す" "SCRIPT=/tmp/detail-tail.py bash run.sh"
check allow "ファイル名に cat を含む .py を実行" "python3 scripts/cat-notes.py"
check allow "ファイル名に grep を含む .py を実行" "python3 /tmp/grep-helper.py"
check allow "ファイル名に find を含む .py を実行" "python3 /tmp/find-dupes.py"
check allow "git の --stat (wc 等を含まない)" "git show --stat HEAD"
check allow "ログの tail" "tail -f storage/logs/laravel.log"

# bypass
check allow "理由付き bypass" "head -20 src/app.py # via:bash-discovery: 行数確認"

echo "==================================="
if [ "$FAIL" -eq 0 ]; then echo "ALL TESTS PASSED"; exit 0; else echo "SOME TESTS FAILED"; exit 1; fi
