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
    case "$rc" in 2) got=block ;; 0) got=allow ;; *) got="異常終了(rc=$rc)" ;; esac
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
check block "絶対パスで起動した head" "/usr/bin/head -20 src/app.py"
check block "絶対パスで起動した cat" "/bin/cat src/index.ts"
check block "絶対パスで起動した grep" "/usr/bin/grep -rn foo src/"
check block "相対パスで起動した find" "./find src/ -name '*.py'"
check block "引数パスの後パイプで grep" "python3 tools/grep src/app.py | grep -rn bar tests/"
check block "サブシェル内の grep" 'echo $(grep -rn foo src/app.py)'
check block "バッククォート内の grep" 'echo `grep -rn foo src/app.py`'

# ファイル名・オプションの一部なら allow
check allow "ファイル名に head を含む .py を実行" "python3 /tmp/session-cost-head.py"
check allow "ファイル名に tail を含む .py を環境変数で渡す" "SCRIPT=/tmp/detail-tail.py bash run.sh"
check allow "ファイル名に cat を含む .py を実行" "python3 scripts/cat-notes.py"
check allow "ファイル名に grep を含む .py を実行" "python3 /tmp/grep-helper.py"
check allow "ファイル名に find を含む .py を実行" "python3 /tmp/find-dupes.py"
check allow "オプション名に tail を含む" "docker compose logs --tail 5 app.py"
check allow "ディレクトリ名が cat" "python3 scripts/cat/run.py"
check allow "git log --grep のクォート内のコード名" "git log --grep \"cat src/a.py\""

# 引数・クォート内のコマンド名は allow (Issue #10)
check allow "引数パスに grep を含む" "python3 tools/grep src/app.py"
check allow "npm script 名に grep を含む" "npm run lint:grep src/"
check allow "コミットメッセージ内の head と .py" 'git commit -m "fix head handling in cost-head.py"'

# bypass
check allow "理由付き bypass" "head -20 src/app.py # via:bash-discovery: 行数確認"

echo "==================================="
if [ "$FAIL" -eq 0 ]; then echo "ALL TESTS PASSED"; exit 0; else echo "SOME TESTS FAILED"; exit 1; fi
