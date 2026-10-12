#!/bin/bash
# 質問の回答の保存先の契約検査（Issue #53、ADR 0017）
#
# 実行: bash tests/test_qa_answer_destination.sh
#
# 検査すること:
#   - resolve-issue の feature 前処理が、HVE 導入先（check-knowledge.py がある）の判定と、
#     回答を knowledge/<domain>/ ではなく qa/ に残す規則を定義する
#   - resolve-issue の項目 1 の 2（Gmail）と 4（PO）、create-issue の質問票ゲートの 2 と 4 が、その規則を指す
#   - HVE が無いリポジトリの保存先（knowledge/<domain>/）は残る
#   - qa/ を回答の探索対象に加えない
#   - ADR 0017 と一覧の行がある

set -u
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
RI="$ROOT/skills/global/resolve-issue/SKILL.md"
CI="$ROOT/skills/global/create-issue/SKILL.md"
pass=0
fail=0
check() {
    local name="$1"; shift
    if "$@"; then echo "[PASS] $name"; pass=$((pass + 1)); else echo "[FAIL] $name"; fail=$((fail + 1)); fi
}
# 見出し $2 から次の見出し $3 の手前までに $4 があるか
section_has() { awk -v s="$2" -v e="$3" 'index($0,s)==1{on=1;next} on&&index($0,e)==1{on=0} on' "$1" 2>/dev/null | grep -qF -- "$4"; }
# ファイル $1 の、$2 を含む行と、その次の行（折り返し）までに $3 があるか
item_has() { awk -v k="$2" 'index($0,k){print; getline; print}' "$1" 2>/dev/null | grep -qF -- "$3"; }
# ファイル $1 の、$2 を含む行そのものに $3 があるか
line_has() { awk -v k="$2" 'index($0,k)' "$1" 2>/dev/null | grep -qF -- "$3"; }
# ファイル $1 の、$2 を含む行から $3 を含む行の手前までに $4 が無いか（範囲が空なら失敗）
range_lacks() { local out; out="$(awk -v s="$2" -v e="$3" 'index($0,s){on=1} on&&index($0,e){on=0} on' "$1" 2>/dev/null)"; [ -n "$out" ] && ! printf '%s\n' "$out" | grep -qF -- "$4"; }

FEATURE_START="#### [feature]"
FEATURE_END="#### [ops]"

# 1) resolve-issue: 判定と規則の定義
check "resolve-issue: HVE 導入先の判定に導入先の検査スクリプトを使う" section_has "$RI" "$FEATURE_START" "$FEATURE_END" ".claude/scripts/hve/check-knowledge.py"
check "resolve-issue: HVE 導入先の判定に hve-playbook 自身の検査スクリプトを使う" section_has "$RI" "$FEATURE_START" "$FEATURE_END" "hve-scripts/check-knowledge.py"
check "resolve-issue: HVE 導入先では knowledge/<domain>/ に書かない" item_has "$RI" "**HVE 導入先**" "\`knowledge/<domain>/\` に書かず"
check "resolve-issue: HVE 導入先では qa/ に残す" item_has "$RI" "**HVE 導入先**" "\`qa/\` に残す"
check "resolve-issue: HVE 導入先では knowledge/ の有無に関わらず qa/ に残す" item_has "$RI" "**HVE 導入先**" "\`knowledge/\` の有無に関わらず"
check "resolve-issue: 保存先の正本（前段の規則）に docs/qa/ の但し書きがある" section_has "$RI" "$FEATURE_START" "$FEATURE_END" "（\`docs/qa/\` があればそこ）"

# 2) resolve-issue: 項目 1 の 2（Gmail）と 4（PO）が規則を指す
check "resolve-issue: Gmail の回答の永続化が HVE 導入先では qa ディレクトリを指す" item_has "$RI" "にナレッジファイルとして永続化（Q&A 形式 + frontmatter）" "HVE 導入先では \`knowledge/<domain>/\` ではなく前段の規則の qa ディレクトリに置く"
check "resolve-issue: PO の回答の永続化が HVE 導入先では qa/*.md を指す" item_has "$RI" "**PO 回答の永続化**" "HVE 導入先では書かず、questionnaire skill の \`qa/*.md\` を正とする"
check "resolve-issue: Gmail の回答の Issue コメントが HVE 導入先では qa への記録を示す" item_has "$RI" "Gmail から回答を発見・ナレッジ化" "Gmail から回答を発見・qa に記録"

# 3) create-issue: 2 と 4 が resolve-issue の定義を指す
check "create-issue: Gmail の回答の永続化が HVE 導入先では qa ディレクトリを指す" item_has "$CI" "発見した回答は" "HVE 導入先では qa ディレクトリに置く"
check "create-issue: PO の回答の永続化が HVE 導入先では qa/*.md を指す" item_has "$CI" "PO 回答を" "HVE 導入先では書かず、questionnaire skill の \`qa/*.md\` を正とする"
check "create-issue: 判定と保存先は resolve-issue の定義に従う" item_has "$CI" "PO 回答を" "判定と保存先は resolve-issue skill Step 2 [feature] 項目 1 に定義"

# 4) HVE が無いリポジトリの保存先は残る
check "resolve-issue: HVE が無いリポジトリでは knowledge/<domain>/ に Gmail の回答を書く" line_has "$RI" "にナレッジファイルとして永続化（Q&A 形式 + frontmatter）" "\`knowledge/<domain>/\` にナレッジファイルとして永続化"
check "resolve-issue: HVE が無いリポジトリでは knowledge/<domain>/ に PO の回答を書く" line_has "$RI" "**PO 回答の永続化**" "\`knowledge/<domain>/\` にナレッジファイルとして"
check "create-issue: HVE が無いリポジトリでは knowledge/<domain>/ に Gmail の回答を書く" line_has "$CI" "発見した回答は" "\`knowledge/<domain>/\` に永続化する"
check "create-issue: HVE が無いリポジトリでは knowledge/<domain>/ に PO の回答を書く" line_has "$CI" "PO 回答を" "\`knowledge/<domain>/\` に永続化する"

# 5) qa/ を探索対象に加えない（knowledge 検索の手順に qa/ を書かない）
check "resolve-issue: knowledge 検索の手順に qa/ を加えない" range_lacks "$RI" "1. **knowledge/ 検索**" "2. **Gmail 検索**" "qa/"
check "create-issue: knowledge 検索の手順に qa/ を加えない" range_lacks "$CI" "を検索（利用リポにある場合。domain は Issue の業務領域から判定）" "2. Gmail MCP で未解決の質問を検索" "qa/"

# 6) 決定ログ
ADR="$(ls "$ROOT"/knowledge/adr/0017-*.md 2>/dev/null | head -1)"
check "ADR 0017 がある" [ -n "$ADR" ]
check "ADR 一覧に 0017 の行がある" grep -qF "0017" "$ROOT/knowledge/adr/README.md"

echo
echo "passed: $pass, failed: $fail"
[ "$fail" -eq 0 ]
