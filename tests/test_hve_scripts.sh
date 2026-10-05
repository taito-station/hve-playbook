#!/bin/bash
# hve-scripts（knowledge の検査スクリプト）のテストと dogfood
#
# 実行: bash tests/test_hve_scripts.sh
#
# 1) tests/hve_scripts/test_*.py（各スクリプトの自走式テスト）をすべて実行する
# 2) このリポジトリ自身に両検査を流す（dogfood。ADR 0014）
# 3) .githooks/pre-push が、決定ログの違反を含む push を止め、違反の無い push を通すことを一時リポジトリで確かめる

set -u
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
pass=0
fail=0
check() {
    local name="$1"; shift
    if "$@"; then echo "[PASS] $name"; pass=$((pass + 1)); else echo "[FAIL] $name"; fail=$((fail + 1)); fi
}

# 1) 自走式テスト
for t in "$ROOT"/tests/hve_scripts/test_*.py; do
    check "$(basename "$t")" python3 "$t" >/dev/null 2>&1
done

# 2) dogfood
check "dogfood: check-knowledge.py" python3 "$ROOT/hve-scripts/check-knowledge.py" >/dev/null 2>&1
check "dogfood: check-decision-log.py（作業ツリー）" python3 "$ROOT/hve-scripts/check-decision-log.py" >/dev/null 2>&1
check "dogfood: 96f73b1 の正規の supersede が通る" \
    python3 "$ROOT/hve-scripts/check-decision-log.py" --base 96f73b1^ --head 96f73b1 >/dev/null 2>&1

# 3) pre-push
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
R="$TMP/repo"
git init -q -b main "$R"
git -C "$R" config user.name test
git -C "$R" config user.email test@example.invalid
git -C "$R" config commit.gpgsign false
git -C "$R" config core.autocrlf false
cp -r "$ROOT/hve-scripts" "$R/hve-scripts"
mkdir -p "$R/.githooks" "$R/knowledge/adr"
cp "$ROOT/.githooks/pre-push" "$R/.githooks/pre-push" 2>/dev/null
printf '# 0001. a\n\n## ステータス\n\nAccepted — 2026-10-04\n\n## 背景と課題\n\n本文。\n' >"$R/knowledge/adr/0001-a.md"
git -C "$R" add -A
git -C "$R" commit -q -m base
git init -q --bare "$TMP/remote.git"
git -C "$R" remote add origin "$TMP/remote.git"
git -C "$R" push -q origin main 2>/dev/null
git -C "$R" config core.hooksPath .githooks

git -C "$R" switch -q -c ok
printf '# 0002. b\n\n## ステータス\n\nAccepted — 2026-10-04\n' >"$R/knowledge/adr/0002-b.md"
git -C "$R" add -A
git -C "$R" commit -q -m "ADR を追加"
check "pre-push: 追記だけの push は通る" git -C "$R" push -q origin ok

git -C "$R" switch -q -c ng main
git -C "$R" rm -q knowledge/adr/0001-a.md
git -C "$R" commit -q -m "ADR を削除"
denied() { ! git -C "$R" push -q origin ng >"$TMP/ng.log" 2>&1; }
check "pre-push: ADR の削除を含む push は止める" denied
check "pre-push: 止めた理由を表示する" grep -q '0001-a.md' "$TMP/ng.log"

echo
echo "結果: PASS=$pass FAIL=$fail"
[ "$fail" -eq 0 ]
