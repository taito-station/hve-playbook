#!/bin/bash
# tests/test_*.sh を全件実行する（ローカルで実行する規律。.claude/rules/testing.md・ADR 0025）
#
# 実行: bash tests/run-all.sh
#
# HOME を全件で共有する一時ディレクトリに向けて順に実行し、本ごとに PASS / FAIL と SKIP の有無を出す。
# SKIP を出したテストは、ログの中で行頭が SKIP（直後が :・空白・行末）か [SKIP] の行を、`結果:` 行の前に
# 「SKIP: <テスト名> — <理由>」でまとめて出す
# （そうした行が無ければ、理由の代わりにログの場所を出す）。
# 各テストのログは一時ディレクトリに残し、FAIL のときはそのパスを出す。
# FAIL が 1 本でもあれば exit 1。

set -u

TESTS_DIR="$(cd "$(dirname "$0")" && pwd)"
WORK="$(mktemp -d)"
mkdir -p "$WORK/home" "$WORK/logs"
# 理由の行は配列でなくファイルに貯める（macOS の bash 3.2 は set -u の下で空の配列を展開すると落ちる）
SKIPS="$WORK/skips.txt"
: > "$SKIPS"

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
    if grep -q SKIP "$log"; then
        line="$line SKIP あり"
        # -a: ログに NUL などがあっても「Binary file ... matches」を出さない。名前は sed に埋め込まない（& や \ で化けるため）
        reasons="$(grep -aE '^(SKIP([:[:space:]]|$)|\[SKIP\])' "$log" | sed -E 's/^\[?SKIP\]?:?[[:space:]]*//')"
        # 行の途中にだけ SKIP がある（理由の行が無い）ときも、SKIP あり の行と数を揃えてログの場所を出す
        if [ -z "$reasons" ]; then reasons="（理由の行なし。ログ: ${log}）"; fi
        printf '%s\n' "$reasons" | while IFS= read -r r; do printf 'SKIP: %s — %s\n' "$name" "$r"; done >> "$SKIPS"
    fi
    if [ "$result" = FAIL ]; then line="$line ログ: $log"; fi
    echo "$line"
done

cat "$SKIPS"
echo "結果: PASS=${pass} FAIL=${fail}（ログ: ${WORK}/logs）"
[ "$fail" -eq 0 ]
