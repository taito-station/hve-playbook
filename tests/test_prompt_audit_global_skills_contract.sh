#!/bin/bash
# prompt audit（2026-11、対象モデル Claude Opus 5.5）の Medium のうち、global skill 7 件（Issue #91 の C 節）の契約検査
#
# 実行: bash tests/test_prompt_audit_global_skills_contract.sh
#
# 検査すること:
#   - 外した文言（外部規則の参照、種別を判定する語の一覧、理由の無い禁則、description の工程の列挙、
#     基準の無いチェック項目、激励）が、対象のファイルに残っていない
#   - 外すときに落としやすい規則が残っている（tdd の RED の観測、debug-bar-investigation の修正後のログの
#     取り直し、create-issue の種別の定義、learn の description のトリガー語、systematic-debugging の
#     データに戻る規則）

set -u
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SG="$ROOT/skills/global"
CI="$SG/create-issue/SKILL.md"
TDD="$SG/tdd/SKILL.md"
PIR="$SG/pre-implementation-research/SKILL.md"
DBI="$SG/debug-bar-investigation/SKILL.md"
LRN="$SG/learn/SKILL.md"
CW="$SG/commit-workflow/SKILL.md"
SD="$SG/systematic-debugging/SKILL.md"
for f in "$CI" "$TDD" "$PIR" "$DBI" "$LRN" "$CW" "$SD"; do
    [ -f "$f" ] || { echo "[FAIL] 対象のファイルが無い: $f"; exit 1; }
done
pass=0
fail=0
check() {
    local name="$1"; shift
    if "$@"; then echo "[PASS] $name"; pass=$((pass + 1)); else echo "[FAIL] $name"; fail=$((fail + 1)); fi
}
has() { grep -qF -- "$2" "$1"; }
lacks() { ! grep -qF -- "$2" "$1"; }
# frontmatter（先頭の --- から次の --- まで）に $2 があるか
fm() { awk 'NR==1&&/^---$/{on=1;next} on&&/^---$/{exit} on' "$1"; }
fm_has() { fm "$1" | grep -qF -- "$2"; }
fm_lacks() { local out; out="$(fm "$1")"; [ -n "$out" ] && ! printf '%s\n' "$out" | grep -qF -- "$2"; }

# C1) create-issue: 種別は語の一覧ではなく定義で判定する
check "C1: create-issue に bug を判定する語の一覧が無い" lacks "$CI" "「動かない」「エラー」"
check "C1: create-issue に feature を判定する語の一覧が無い" lacks "$CI" "「してほしい」「追加」"
check "C1: bug は現象の報告" has "$CI" "\`bug\`: 現象の報告"
check "C1: feature は要望" has "$CI" "\`feature\`: 要望"
check "C1: ops は運用作業の依頼（コードの変更は無いか軽微）" has "$CI" "\`ops\`: 運用作業の依頼。データの更新・移行・一括処理など（コードの変更は無いか軽微）"
check "C1: またがる語は直す対象で分け、データなら ops" has "$CI" "データを直す・入れ替える依頼なら \`ops\`"
check "C1: またがる語がコードに向くなら bug・feature の定義に戻す" has "$CI" "コードなら上の \`bug\`・\`feature\` の定義で分ける"
check "C1: 直す対象か種別が決まらなければ判定不能に回す" has "$CI" "直す対象か種別が決まらなければ 4 へ"
check "C1: データの誤りが既存の機能の不具合で生じているときは bug" has "$CI" "データの誤りが既存の機能の不具合で生じているときは \`bug\`"
check "C1: 参照先の resolve-issue の「何が起きているか」が実在する" has "$SG/resolve-issue/SKILL.md" "**何が起きているか**"
check "C1: 判定不能は、現象・要望・運用作業のどれかが決まらないとき" has "$CI" "現象・要望・運用作業のどれかが決まらない"

# C2) tdd: 外部規則を否定する書き方をやめ、採る行動と RED の観測を残す
check "C2: tdd に外部 skill（superpowers）への参照が無い" lacks "$TDD" "superpowers"
check "C2: tdd に圧力語（死守）が無い" lacks "$TDD" "死守"
check "C2: 後からテストで固めるときも RED を一度は観測する" has "$TDD" "失敗（RED 相当）を一度は観測"
check "C2: RED の観測方法（実装を一時的に壊す）が残っている" has "$TDD" "実装を一時的に壊す"

# C3) pre-implementation-research: C2 に合わせた参照
check "C3: pre-implementation-research に「全削除」への参照が無い" lacks "$PIR" "全削除"
check "C3: 手順は tdd skill に従う" has "$PIR" "\`tdd\` skill に従う"

# C4) debug-bar-investigation: 禁則を肯定形の進め方にする
check "C4: 「調査時の禁則」の見出しが無い" lacks "$DBI" "調査時の禁則"
check "C4: 「動いてるから OK」が無い" lacks "$DBI" "動いてるから"
check "C4: 調査の進め方の見出しがある" has "$DBI" "## 調査の進め方"
check "C4: 修正後は同じ手順でログを取り直して比べる" has "$DBI" "同じ手順でログを取り直し"

# C5) learn: description から工程の列挙を外し、トリガー語は残す
check "C5: learn の description に工程の列挙が無い" fm_lacks "$LRN" "ワークドエグザンプル"
check "C5: learn の description にトリガー語が残っている" fm_has "$LRN" "「学習したい」"

# C6) commit-workflow: 基準の無い項目を消す
check "C6: 「コミットメッセージが適切」が無い" lacks "$CW" "コミットメッセージが適切"
check "C6: 「エラーが発生していない」が無い" lacks "$CW" "エラーが発生していない"

# C7) systematic-debugging: 激励を消し、前半の規則を残す
check "C7: 「仮説を捨てる勇気」が無い" lacks "$SD" "捨てる勇気"
check "C7: 仮説が外れたらフェーズ 1 のデータに戻る" has "$SD" "フェーズ 1 のデータに戻る"

echo
echo "passed: $pass, failed: $fail"
[ "$fail" -eq 0 ]
