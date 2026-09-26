#!/bin/bash
# SKILL.md 本文に位置引数記法（ドル記号 + 数字）が無いことを検査する
#
# 実行: bash tests/test_skill_positional_args.sh
#
# Claude Code は skill 起動時に SKILL.md 本文中の位置引数記法を skill 引数で置換する。
# awk の $0 などが引数に化けて手順が壊れるため、SKILL.md には書かない
# (必要なシェル・awk は skill 同梱のスクリプトに置く)。
# references/ や scripts/ は Read / 実行されるだけで置換されないため対象外。

set -u
ROOT="${SKILLS_ROOT:-$(cd "$(dirname "$0")/.." && pwd)/skills}"

FAIL=0
while IFS= read -r f; do
    hits=$(grep -nE '\$\{?[0-9]' "$f" || true)
    if [ -n "$hits" ]; then
        echo "[FAIL] $f (シェル・awk は skill 同梱の scripts/ に切り出す)"
        echo "$hits" | sed 's/^/    /'
        FAIL=1
    fi
done < <(find "$ROOT" -name SKILL.md)

echo "==================================="
if [ "$FAIL" -eq 0 ]; then echo "ALL TESTS PASSED"; exit 0; else echo "SOME TESTS FAILED"; exit 1; fi
