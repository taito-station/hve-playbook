#!/bin/bash
# hve-implement skill の契約検査（Issue #45、ADR 0016）
#
# 実行: bash tests/test_hve_implement_contract.sh
#
# 検査すること:
#   - skills/hve-implement/SKILL.md が implement-flow の Step 0〜8 と STOP 報告を持ち、規約の正本を参照する
#   - 導入先で解決できない参照（paddock 固有の値・作者の ~/.claude）を含まない
#   - skill 単位の hve-local と、hve-local/implement-flow.md の検証コマンドを突き合わせる
#   - 検査スクリプトを導入先（.claude/scripts/hve/）と hve-playbook 自身（hve-scripts/）の両方で探す
#   - 単独モードは Step 4 の後に承認を得る。resolve-issue からは Step 2〜4 と Step 5〜7 の 2 段で呼ばれる
#   - resolve-issue の bug / feature パスが、skill があるときだけ 2 段で呼ぶ
#   - create-pr / review-pr が hve-implement を --depth の決定者として認める
#   - 導線（hve 版 implement-flow・usage-prompts・README）と ADR 0016 がある

set -u
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SKILL="$ROOT/skills/hve-implement/SKILL.md"
RI="$ROOT/skills/global/resolve-issue/SKILL.md"
pass=0
fail=0
check() {
    local name="$1"; shift
    if "$@"; then echo "[PASS] $name"; pass=$((pass + 1)); else echo "[FAIL] $name"; fail=$((fail + 1)); fi
}
has() { grep -qF -- "$2" "$1" 2>/dev/null; }
lacks() { [ -f "$1" ] && ! grep -qF -- "$2" "$1"; }
# 見出し $2 から次の見出し $3 の手前までに $4 があるか
section_has() { awk -v s="$2" -v e="$3" 'index($0,s)==1{on=1;next} on&&index($0,e)==1{on=0} on' "$1" 2>/dev/null | grep -qF -- "$4"; }
frontmatter_name() { [ "$(awk 'NR==1&&$0!="---"{exit} NR>1&&$0=="---"{exit} NR>1&&sub(/^name: */,""){print}' "$SKILL" 2>/dev/null)" = "hve-implement" ]; }
has_all_steps() { local n; for n in 0 1 2 3 4 5 6 7 8; do grep -q "^### Step $n:" "$SKILL" 2>/dev/null || return 1; done; }

# 1) skill 本体
check "skill: SKILL.md がある" [ -f "$SKILL" ]
check "skill: frontmatter の name が hve-implement" frontmatter_name
check "skill: frontmatter に description がある" has "$SKILL" "description:"
check "skill: Step 0〜8 の見出しがある" has_all_steps
for w in "■ 停止ゲート:" "■ 理由:" "■ 試みたこと:" "■ 推奨アクション:"; do
    check "skill: STOP 報告の節に「${w}」の行がある" section_has "$SKILL" "## STOP 時の報告" "## 注意事項" "$w"
done
check "skill: 規約の正本として implement-flow を参照する" has "$SKILL" ".claude/rules/hve/implement-flow.md"

# 2) 導入先で解決できない参照を含まない
for w in "scripts/mdq" "scripts/cq" "D24" "check-doc-classes" "~/.claude" "impl-sonnet"; do
    check "skill: 「${w}」を含まない" lacks "$SKILL" "$w"
done

# 3) hve-local と検査スクリプト
check "skill: skill 単位の hve-local を突き合わせる" has "$SKILL" ".claude/rules/hve-local/hve-implement.md"
check "skill: hve-local/implement-flow.md の検証コマンドを優先する" has "$SKILL" ".claude/rules/hve-local/implement-flow.md"
check "skill: 導入先の検査スクリプトを探す" has "$SKILL" ".claude/scripts/hve/"
check "skill: hve-playbook 自身の検査スクリプトを探す" has "$SKILL" "hve-scripts/"
check "skill: 検査スクリプトが無いときは手で検査して報告に残す（黙って飛ばさない）" has "$SKILL" "手順を手で行い、結果を報告"
check "skill: 決定ログの置き場所は artifact-management に従う" has "$SKILL" "artifact-management"

# 4) モードと承認
check "skill: 単独モードは ExitPlanMode で承認を得る" has "$SKILL" "ExitPlanMode"
check "skill: Plan モードを使えない環境でも承認前に Step 5 へ進まない" has "$SKILL" "承認を得るまで Step 5 へ進まない"
row_has() { grep -F -- "$2" "$SKILL" 2>/dev/null | grep -qF -- "$3"; }
check "skill: モード表で --phase pre は Step 2〜4" row_has "" "--phase pre" "Step 2〜4"
check "skill: モード表で --phase post は Step 5〜7" row_has "" "--phase post" "Step 5〜7"
check "skill: 単独モードは Issue でなく実装したい内容を受ける" row_has "" "| 単独 |" "<実装したい内容>"
check "skill: depth は Step 1 の分類で決める" has "$SKILL" "承認された計画の分類（Step 1）で決める"
check "skill: バグ修正は --depth lightweight" row_has "" "バグ修正 →" "--depth lightweight"
check "skill: それ以外は --depth full" row_has "" "それ以外 →" "--depth full"
check "skill: depth をブランチの type で決めない" lacks "$SKILL" "ブランチの type"
check "skill: feature の前段の回答は qa/ に保存する" row_has "" "resolve-issue の前段（feature）" "qa/"

# 5) resolve-issue の 2 段呼び出し（skill があるときだけ）
check "resolve-issue: skill の有無で分岐する" has "$RI" ".claude/skills/hve-implement/SKILL.md"
check "resolve-issue: bug パスで前段（--phase pre）を呼ぶ" section_has "$RI" "#### [bug]" "#### [feature]" "--phase pre"
check "resolve-issue: bug パスで後段を呼ばない" bash -c '! awk '"'"'index($0,"#### [bug]")==1{on=1;next} on&&index($0,"#### [feature]")==1{on=0} on'"'"' "$1" | grep -qF -- "--phase post"' _ "$RI"
check "resolve-issue: feature パスで前段（--phase pre）を呼ぶ" section_has "$RI" "#### [feature]" "#### [ops]" "--phase pre"
check "resolve-issue: feature パスで後段を呼ばない" bash -c '! awk '"'"'index($0,"#### [feature]")==1{on=1;next} on&&index($0,"#### [ops]")==1{on=0} on'"'"' "$1" | grep -qF -- "--phase post"' _ "$RI"
check "resolve-issue: feature の前段の回答は qa/ に保存する" section_has "$RI" "#### [feature]" "#### [ops]" "\`qa/\` に保存する"
check "resolve-issue: ops パスでは呼ばない" bash -c '! awk '"'"'index($0,"#### [ops]")==1{on=1;next} on&&index($0,"### Step 3")==1{on=0} on'"'"' "$1" | grep -qF hve-implement' _ "$RI"
nodoc_all() { [ "$(grep -c 'hve-implement/SKILL.md` がある場合' "$RI")" -ge 3 ] && ! grep 'hve-implement/SKILL.md` がある場合' "$RI" | grep -vqF 'ドキュメントのみ・設定変更のみ・依存更新のみの変更を除く'; }
check "resolve-issue: 呼び出し条件の 3 か所すべてで implement-flow の対象外を除く" nodoc_all
step3_post() { awk 'index($0,"### Step 3")==1{on=1;next} on&&index($0,"### Step 4")==1{on=0} on' "$RI" | grep -F -- "--phase post" | grep -qF "[bug / feature]"; }
check "resolve-issue: Step 3 で bug / feature に限って後段（--phase post）を呼ぶ" step3_post

# 6) --depth の決定者
check "create-pr: depth の決定者に hve-implement（計画の分類）を含める" has "$ROOT/skills/global/create-pr/SKILL.md" "hve-implement skill（単独モード）が承認された計画の分類"
check "create-pr: 引数解析の説明も hve-implement に追随する" has "$ROOT/skills/global/create-pr/SKILL.md" "hve-implement skill (単独モード) が承認された計画の分類から決めて渡す"
check "review-pr: depth の決定者に hve-implement（計画の分類）を含める" has "$ROOT/skills/global/review-pr/SKILL.md" "hve-implement skill の単独モードが承認された計画の分類に応じて指定"

# 7) 導線と ADR
check "implement-flow（hve 版）: hve-implement を案内する" has "$ROOT/rules/hve/implement-flow.md" "hve-implement"
check "implement-flow（global 版）: hve-implement に触れない" lacks "$ROOT/rules/global/workflow/implement-flow.md" "hve-implement"
check "usage-prompts: /hve-implement を案内する" has "$ROOT/docs/usage-prompts.md" "/hve-implement"
check "README: 補助スキルに /hve-implement がある" has "$ROOT/README.md" "/hve-implement"
adr_exists() { [ -f "$ROOT/knowledge/adr/0016-hve-implement-skill-and-two-phase-call-from-resolve-issue.md" ]; }
check "ADR 0016 がある" adr_exists

echo
echo "結果: PASS=$pass FAIL=$fail"
[ "$fail" -eq 0 ]
