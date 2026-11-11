#!/bin/bash
# review-pr skill の手順書契約を固定する検査
#
# 実行: bash tests/test_review_pr_contracts.sh
#
# 手順書は実行されないので、壊れても誰も気付かない。レビューで見つかった
# 「書いてあるが動かない」箇所を静的に固定し、復活を検知する:
#   1. fix-stable 収束判定は RESOLVED_KEYS (前巡まで) と比較し、本巡分の追加は判定の後
#   2. 構成と巡数: legacy (Reviewer A/B + Fact-checker) と Impact が無く、フラグなしは full、
#      full の ITER_MAX は 2、後半巡制約は 2 巡目から、Correctness が caller・データ整合性・性能を見る (ADR 0035)
#   3. --depth の値検証と未知フラグの中断がある
#   4. BROWSER_TEST_DONE / convergence_key が未定義の記号 (... / category / evidence) を使わない
#   5. review-only の BEHIND は compare API のみ (local fetch + rev-list を使わない)
#   6. 分類: follow-up (スコープ外・judgment) を escalate・auto-fix より先に判定し、命名・typo を自動修正しない
#   7. 呼び出し側 (create-pr / resolve-issue) の巡数が review-pr と一致する

set -u

# ROOT は tests/ の他の契約テストと同じく、このスクリプトのあるリポジトリ (worktree ならその作業ツリー) にする
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SKILL="$ROOT/skills/global/review-pr/SKILL.md"
PROMPTS="$ROOT/skills/global/review-pr/references/reviewer-prompts.md"
FIX_STEPS="$ROOT/skills/global/review-pr/references/fix-steps.md"
CREATE_PR="$ROOT/skills/global/create-pr/SKILL.md"
RESOLVE="$ROOT/skills/global/resolve-issue/SKILL.md"

FAIL=0
pass() { echo "[PASS] $1"; }
fail() { echo "[FAIL] $1"; FAIL=1; }

# 1. 収束判定の順序: Step 6 内で「new_defect_keys ... - RESOLVED_KEYS」の行が
#    「RESOLVED_KEYS |= FIXED_KEYS_THIS_ROUND」より前にあり、fix-steps は RESOLVED_KEYS に直接足さない
CMP_LINE=$(grep -n '} - RESOLVED_KEYS' "$SKILL" | head -1 | cut -d: -f1)
# 「本巡分の追加は判定の後」= 追加行の **全出現** が判定行より後 (先頭出現で判定)
ADD_FIRST=$(grep -n 'RESOLVED_KEYS |= FIXED_KEYS_THIS_ROUND' "$SKILL" | head -1 | cut -d: -f1)
ADD_COUNT=$(grep -c 'RESOLVED_KEYS |= FIXED_KEYS_THIS_ROUND' "$SKILL")
if [ -n "$CMP_LINE" ] && [ -n "$ADD_FIRST" ] && [ "$CMP_LINE" -lt "$ADD_FIRST" ]; then
    pass "収束判定 (行 ${CMP_LINE}) が本巡分の RESOLVED_KEYS 追加 (先頭 行 ${ADD_FIRST}、${ADD_COUNT} 箇所) より前にある"
else
    fail "収束判定と RESOLVED_KEYS 追加の順序が崩れている (cmp=${CMP_LINE} add_first=${ADD_FIRST})"
fi
# fix-steps Step 4 節を抜き出し、「足さない」と書いた行以外で RESOLVED_KEYS に足す記述が無いこと
STEP4=$(awk '/^## Step 4: 修正実行/{f=1} /^## Step 4\.5/{f=0} f' "$FIX_STEPS")
if echo "$STEP4" | grep -q 'FIXED_KEYS_THIS_ROUND` に集める' \
   && echo "$STEP4" | grep -q 'RESOLVED_KEYS` にはここでは足さない' \
   && ! echo "$STEP4" | grep -v '足さない' | grep -qE 'RESOLVED_KEYS`? *(に追加|に足す|\|=)'; then
    pass "fix-steps Step 4 は FIXED_KEYS_THIS_ROUND に集め、RESOLVED_KEYS には直接足さない"
else
    fail "fix-steps Step 4 が RESOLVED_KEYS に直接足している (または「足さない」の明記が無い)"
fi
if grep -q 'if MODE == "fix" and iteration >= 2:' "$SKILL"; then
    pass "収束判定は 2 巡目以降のみ"
else
    fail "収束判定の巡条件が iteration >= 2 でない"
fi

# 2. 構成と巡数
for f in "$SKILL" "$PROMPTS" "$FIX_STEPS" "$CREATE_PR" "$RESOLVE"; do
    hit=$(grep -nE 'LEGACY_|IMPACT_PROMPT|Reviewer A|Fact-checker|"legacy"|legacy モード|Impact reviewer|[/+] Impact|Impact [+/]' "$f" | head -3)
    name="$(basename "$(dirname "$f")")/$(basename "$f")"
    if [ -z "$hit" ]; then pass "$name に legacy・Impact の記述が無い"
    else fail "$name に legacy・Impact の記述が残っている: $hit"; fi
done
grep -q 'DEPTH = ARG_DEPTH or "full"' "$SKILL" && pass "フラグなしは full" || fail "フラグなしの DEPTH が full でない"
if grep -qE '^ *ITER_MAX = 2 +# 機能追加のフルパス' "$SKILL" && ! grep -qE 'ITER_MAX = [3-9]' "$SKILL"; then
    pass "full の ITER_MAX は 2 (3 以上の値が無い)"
else
    fail "full の ITER_MAX が 2 でないか、3 以上の値が残っている"
fi
if grep -qF '## 後半巡制約 (`iteration >= 2`' "$PROMPTS" && ! grep -q 'iteration >= 3' "$SKILL" "$PROMPTS"; then
    pass "後半巡制約は 2 巡目から"
else
    fail "後半巡制約が 2 巡目からになっていない"
fi
section() {  # $1=file $2=見出し: 見出しから、コードフェンスの外にある次の ## 見出しまで
    awk -v h="$2" 'index($0, h)==1 {f=1; next} f && /^```/ {fence=!fence} f && !fence && /^## / {exit} f' "$1"
}
CORR=$(section "$PROMPTS" "## CORRECTNESS_PROMPT")
if echo "$CORR" | grep -q 'diff 外' && echo "$CORR" | grep -q 'データ整合性' && echo "$CORR" | grep -q 'N+1'; then
    pass "Correctness が diff 外の caller・データ整合性・性能を見る"
else
    fail "Correctness に diff 外の caller・データ整合性・性能の観点が無い"
fi
if ! echo "$CORR" | grep -qE '^- 命名' && echo "$CORR" | grep -q 'review-only モードのときだけ'; then
    pass "Correctness は命名・可読性を review-only のときだけ見る"
else
    fail "Correctness の命名・可読性の観点が review-only 限定になっていない"
fi
SEC=$(section "$PROMPTS" "## SECURITY_PROMPT")
ok=1; for w in 認証認可 インジェクション 秘密漏洩 サニタイズ CSRF; do echo "$SEC" | grep -q "$w" || ok=0; done
[ "$ok" -eq 1 ] && pass "Security の担当観点が揃っている" || fail "Security の担当観点が欠けている"
grep -q '文面の曖昧さ・矛盾.*\[defect\]' "$PROMPTS" && pass "手順書・規則の文面の曖昧さ・矛盾は [defect]" || fail "文面の曖昧さ・矛盾を [defect] とする定義が無い"

# 3. --depth 検証と未知フラグ
grep -q 'if tok not in ("lightweight", "full"):' "$SKILL" && pass "--depth の値を検証している" || fail "--depth の値検証が無い"
grep -q 'elif tok starts with "-":' "$SKILL" && pass "未知の - 始まりフラグで中断する" || fail "未知フラグの中断が無い"
grep -q 'モードフラグが重複しています' "$SKILL" && grep -q 'PR 番号が複数あります' "$SKILL" && pass "フラグ / PR 番号の重複で中断する" || fail "重複指定の中断が無い"
grep -q '\-\-depth に値がありません' "$SKILL" && pass "--depth の値なしで中断する" || fail "--depth 値なしの中断が無い"

# 4. 未定義記号 (否定形は対象消失で緑になるので、肯定形と対にする)
if grep -qF "BROWSER_TEST_DONE = (grep -qF '## ブラウザテスト'" "$SKILL" && ! grep -q 'BROWSER_TEST_DONE = \.\.\.' "$SKILL"; then
    pass "BROWSER_TEST_DONE に grep の判定式がある"
else
    fail "BROWSER_TEST_DONE の判定式が無いか未定義 (...) のまま"
fi
if grep -q 'file + kind + normalize(content)' "$SKILL" && ! grep -q 'category + normalize(evidence)' "$SKILL"; then
    pass "convergence_key は実在フィールド (file + kind + content) で定義"
else
    fail "convergence_key の定義が無いかパース結果に無いフィールドを使っている"
fi
grep -qE '(^|[^_A-Z])REVIEWER_PROMPT 末尾' "$SKILL" && fail "廃止した REVIEWER_PROMPT 変数への言及が残っている" || pass "REVIEWER_PROMPT 変数への言及が無い"
grep -q 'f\.classification' "$SKILL" && ! grep -q '`classification` フィールド' "$SKILL" && fail "classification フィールドの定義が無い" || pass "classification フィールドが定義されている (または未使用)"

# 5. review-only BEHIND: compare API の肯定形 + local rev-list の否定形
if grep -qF 'compare/$BASE...$HEAD_REF" -q .behind_by' "$SKILL" && ! grep -q 'git rev-list --count "origin/\$HEAD_REF..origin/\$BASE"' "$SKILL"; then
    pass "review-only の BEHIND は compare API のみ"
else
    fail "review-only の BEHIND が compare API でないか local rev-list が戻っている"
fi

# 6. 分類
FU=$(grep -n '^#### (ii) follow-up' "$SKILL" | head -1 | cut -d: -f1)
ES=$(grep -n '^#### (iii) escalate' "$SKILL" | head -1 | cut -d: -f1)
AF=$(grep -n '^#### (iv) auto-fix' "$SKILL" | head -1 | cut -d: -f1)
if [ -n "$FU" ] && [ -n "$ES" ] && [ -n "$AF" ] && [ "$FU" -lt "$ES" ] && [ "$ES" -lt "$AF" ]; then
    pass "follow-up を escalate・auto-fix より先に判定する"
else
    fail "follow-up → escalate → auto-fix の判定順が無い (fu=$FU es=$ES af=$AF)"
fi
grep -qF '`silent-reject` / `follow-up` / `escalate` / `auto-fix`' "$SKILL" && pass "classification に follow-up がある" || fail "classification に follow-up が無い"
# G3: セキュリティ指摘が出なくなる・除外される経路を戻さない
grep -q '実行結果を変えるものは、モードによらずバグとして \[defect\]' "$PROMPTS" && pass "実行結果を変える綴り誤りはモードによらず [defect]" || fail "実行結果を変える綴り誤りを [defect] とする記述が無い"
LATE=$(section "$PROMPTS" "## 後半巡制約")
if echo "$LATE" | grep -qF '[Security] (任意重大度)' && echo "$LATE" | grep -q 'follow-up として直していない論点は除外しない'; then
    pass "後半巡制約は [Security] を任意重大度で報告させ、follow-up を除外しない"
else
    fail "後半巡制約から [Security] (任意重大度) か follow-up を除外しない記述が消えている"
fi
grep -qF '`[A-Za-z0-9_./-]` だけで' "$PROMPTS" && grep -qF '`[A-Za-z0-9_./-]` だけで' "$SKILL" && pass "コマンドに渡す語・パスの文字種を制限している" || fail "コマンドに渡す語・パスの文字種の制限が無い"
grep -q '指示には従わない' "$SKILL" && grep -q '指示には従わない' "$PROMPTS" && pass "Analyst とレビュアーは本文の指示に従わない" || fail "本文の記述をデータとして扱う記述が無い"
grep -qF '<in|out>' "$SKILL" && pass "Analyst が指摘ごとにスコープの内外を返す" || fail "Analyst の返答にスコープの内外が無い"
if ! grep -qE 'typo / 命名|命名 / 不要 import / typo / 軽微' "$SKILL" "$CREATE_PR"; then
    pass "命名・typo を自動修正する記述が無い"
else
    fail "命名・typo を自動修正する記述が残っている"
fi
# F12: [Security] は follow-up にしない / follow-up は収束判定から除く
FUSEC=$(awk '/^#### \(ii\) follow-up/{f=1; next} /^#### \(iii\)/{exit} f' "$SKILL")
if echo "$FUSEC" | grep -q 'follow-up にしない' && echo "$FUSEC" | grep -qF '`[Security]` の指摘'; then
    pass "[Security] の指摘は follow-up にしない"
else
    fail "follow-up の例外に [Security] が無い"
fi
grep -qF 'f.classification not in ("silent-reject", "follow-up")' "$SKILL" && pass "follow-up は収束判定から除く" || fail "follow-up が収束判定に含まれている"
if ! grep -q 'Nice-to-have のみ' "$SKILL" "$CREATE_PR" && grep -q '未再レビュー' "$SKILL"; then
    pass "ITER_MAX 到達の判定は最後の巡の auto-fix (未再レビュー) で行う"
else
    fail "ITER_MAX 到達の判定が旧基準 (後半巡が Nice-to-have のみ) のまま"
fi

# 7. 呼び出し側の整合
if grep -q 'lightweight 1 / full 2' "$CREATE_PR" && ! grep -qE 'full 3|最大 3 巡|3 巡目以降' "$CREATE_PR"; then
    pass "create-pr の巡数が review-pr と一致する"
else
    fail "create-pr の巡数が review-pr と一致しない"
fi
if grep -qF '`--depth full`（最大2巡）' "$RESOLVE" && ! grep -q '最大3巡' "$RESOLVE"; then
    pass "resolve-issue の巡数が review-pr と一致する"
else
    fail "resolve-issue の巡数が review-pr と一致しない"
fi

echo "==================================="
if [ "$FAIL" -eq 0 ]; then echo "ALL TESTS PASSED"; exit 0; else echo "SOME TESTS FAILED"; exit 1; fi
