#!/bin/bash
# implement-flow の global 版と hve 版のずれ検査
#
# 実行: bash tests/test_implement_flow_drift.sh
#
# 両方とも自己完結で残す（ADR-0007）。hve 版は導入先プロジェクトにコピーされ、
# 作者の ~/.claude/rules に依存しない（ADR-0002）。そのうえで食い違いを防ぐため、
# global 版（汎用）の空行以外の全行が、hve 版にそのまま含まれることを検査する。
# hve 版だけにある行（HVE 固有の置き場所・結果表・frontmatter）は許す。
# 検査するのは行の包含だけで、順序やセクションの所属は見ない。

set -u
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
# IMPLEMENT_FLOW_GLOBAL / IMPLEMENT_FLOW_HVE は、検査がずれを検出できるかを変異で確かめるときにだけ使う
GLOBAL="${IMPLEMENT_FLOW_GLOBAL:-$ROOT/rules/global/workflow/implement-flow.md}"
HVE="${IMPLEMENT_FLOW_HVE:-$ROOT/rules/hve/implement-flow.md}"

for f in "$GLOBAL" "$HVE"; do
    [ -f "$f" ] || { echo "[FAIL] ファイルがありません: $f"; exit 1; }
done

missing=0
checked=0
while IFS= read -r line; do
    [ -n "${line//[[:space:]]/}" ] || continue
    checked=$((checked + 1))
    if ! grep -qxF -- "$line" "$HVE"; then
        echo "[FAIL] global 版の行が hve 版に無い: $line"
        missing=$((missing + 1))
    fi
done < <(cat "$GLOBAL"; [ -z "$(tail -c1 "$GLOBAL")" ] || echo)

echo "[INFO] 検査した行: $checked"
if [ "$checked" -eq 0 ]; then echo "[FAIL] global 版が空"; exit 1; fi
if [ "$missing" -eq 0 ]; then echo "ALL TESTS PASSED"; exit 0; else echo "SOME TESTS FAILED ($missing 行)"; exit 1; fi
