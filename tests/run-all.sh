#!/bin/bash
# tests/test_*.sh を全件実行する（ローカルで実行する規律。.claude/rules/testing.md・ADR 0025）
#
# 実行: bash tests/run-all.sh
#
# HOME を一時ディレクトリに向けて 1 本ずつ実行し、本ごとに PASS / FAIL と SKIP の有無を出す。
# 各テストのログは一時ディレクトリに残し、FAIL のときはそのパスを出す。
# FAIL が 1 本でもあれば exit 1。

set -u

TESTS_DIR="$(cd "$(dirname "$0")" && pwd)"
WORK="$(mktemp -d)"
mkdir -p "$WORK/home" "$WORK/logs"

pass=0
fail=0
for t in "$TESTS_DIR"/test_*.sh; do
    name="$(basename "$t")"
    log="$WORK/logs/$name.log"
    start=$(date +%s)
    if HOME="$WORK/home" bash "$t" > "$log" 2>&1; then
        result=PASS
        pass=$((pass + 1))
    else
        result=FAIL
        fail=$((fail + 1))
    fi
    line="$result $name ($(( $(date +%s) - start ))s)"
    if grep -q SKIP "$log"; then line="$line SKIP あり"; fi
    if [ "$result" = FAIL ]; then line="$line ログ: $log"; fi
    echo "$line"
done

echo "結果: PASS=${pass} FAIL=${fail}（ログ: ${WORK}/logs）"
[ "$fail" -eq 0 ]
