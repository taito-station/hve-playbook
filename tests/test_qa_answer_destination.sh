#!/bin/bash
# 質問の回答の保存先の契約検査（Issue #53・#56、ADR 0017・0019）
#
# 実行: bash tests/test_qa_answer_destination.sh
#
# 検査すること:
#   - resolve-issue の feature 前処理が、HVE 導入先（check-knowledge.py がある）の判定と、
#     回答を knowledge/<domain>/ ではなく qa/ に残す規則を定義する
#   - resolve-issue の項目 1 の 4（PO）、create-issue の質問票ゲートの 4 が、その規則を指す
#   - HVE が無いリポジトリの PO の回答の保存先（knowledge/<domain>/）は残る
#   - qa/ を回答の探索対象に加えない
#   - ADR 0017 と一覧の行がある
#   - Gmail で見つけた回答は、HVE の有無を問わず qa にも knowledge/<domain>/ にも保存せず、質問票の
#     既定値候補として PO に確定してもらう（Issue #56、ADR 0019）。resolve-issue が定義し、create-issue・hve-implement が指す

set -u
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
RI="$ROOT/skills/global/resolve-issue/SKILL.md"
CI="$ROOT/skills/global/create-issue/SKILL.md"
HI="$ROOT/skills/hve-implement/SKILL.md"
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
# ファイル $1 の、$2 を含む行から $3 を含む行の手前までに $4 があるか（字下げした手順番号で範囲を切るとき用）
range_has() { awk -v s="$2" -v e="$3" 'index($0,s){on=1} on&&index($0,e){on=0} on' "$1" 2>/dev/null | grep -qF -- "$4"; }
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

# 2) resolve-issue: 項目 1 の 4（PO）が規則を指す
check "resolve-issue: PO の回答の永続化が HVE 導入先では qa/*.md を指す" item_has "$RI" "**PO 回答の永続化**" "HVE 導入先では書かず、questionnaire skill の \`qa/*.md\` を正とする"

# 3) create-issue: 4 が resolve-issue の定義を指す
check "create-issue: PO の回答の永続化が HVE 導入先では qa/*.md を指す" item_has "$CI" "PO 回答を" "HVE 導入先では書かず、questionnaire skill の \`qa/*.md\` を正とする"
check "create-issue: 判定と保存先は resolve-issue の定義に従う" item_has "$CI" "PO 回答を" "判定と保存先は resolve-issue skill Step 2 [feature] 項目 1 に定義"

# 4) HVE が無いリポジトリの PO の回答の保存先は残る
check "resolve-issue: HVE が無いリポジトリでは knowledge/<domain>/ に PO の回答を書く" line_has "$RI" "**PO 回答の永続化**" "\`knowledge/<domain>/\` にナレッジファイルとして"
check "create-issue: HVE が無いリポジトリでは knowledge/<domain>/ に PO の回答を書く" line_has "$CI" "PO 回答を" "\`knowledge/<domain>/\` に永続化する"

# 5) qa/ を探索対象に加えない（knowledge 検索の手順に qa/ を書かない）
check "resolve-issue: knowledge 検索の手順に qa/ を加えない" range_lacks "$RI" "1. **knowledge/ 検索**" "2. **Gmail 検索**" "qa/"
check "create-issue: knowledge 検索の手順に qa/ を加えない" range_lacks "$CI" "を検索（利用リポにある場合。domain は Issue の業務領域から判定）" "2. Gmail MCP で未解決の質問を検索" "qa/"

# 6) 決定ログ
ADR="$(ls "$ROOT"/knowledge/adr/0017-*.md 2>/dev/null | head -1)"
check "ADR 0017 がある" [ -n "$ADR" ]
check "ADR 一覧に 0017 の行がある" grep -qF "0017" "$ROOT/knowledge/adr/README.md"

# 7) Gmail で見つけた回答は保存せず、質問票の既定値候補にする（Issue #56、ADR 0019）
check "resolve-issue: 前段の規則で Gmail の回答を保存しない" section_has "$RI" "$FEATURE_START" "$FEATURE_END" "Gmail で見つけた回答: Q&A 書式の回答としては保存しない（qa にも \`knowledge/\` にも書かない）"
check "resolve-issue: Gmail の手順で回答を保存しない" range_has "$RI" "2. **Gmail 検索**" "3. **PO への質問票**" "Q&A 書式の回答としては保存しない（\`knowledge/<domain>/\` にも qa にも書かない）"
check "resolve-issue: Gmail の手順で回答を質問票の既定値候補にする" range_has "$RI" "2. **Gmail 検索**" "3. **PO への質問票**" "手順 3 の質問票で、抽出した回答をその質問の既定値候補（選択肢）にする"
check "resolve-issue: 既定値候補の理由にも PII の除外を適用する" range_has "$RI" "2. **Gmail 検索**" "3. **PO への質問票**" "選択肢・理由を含む質問票に載せる全フィールドに上記の PII の除外を適用する"
check "resolve-issue: Gmail の回答の Issue コメントは既定値候補への設定を示す" range_has "$RI" "2. **Gmail 検索**" "3. **PO への質問票**" "Gmail から回答候補を発見・質問票の既定値候補に設定"
check "resolve-issue: Gmail の手順にナレッジ化が残っていない" range_lacks "$RI" "2. **Gmail 検索**" "3. **PO への質問票**" "ナレッジ化"
check "resolve-issue: Gmail の手順に qa への記録が残っていない" range_lacks "$RI" "2. **Gmail 検索**" "3. **PO への質問票**" "qa に記録"
check "resolve-issue: HVE 導入先で knowledge に書かない回答は手順 4 だけ（Gmail の手順 2 を含めない）" bash -c '! awk -v k="**HVE 導入先**" "index(\$0,k){print; getline; print}" "$1" | grep -qF "手順 2・4"' _ "$RI"
check "resolve-issue: 過去分の source: gmail の Q&A にも PII の除外とガードレールを適用する" range_has "$RI" "1. **knowledge/ 検索**" "2. **Gmail 検索**" "手順 2 の PII の除外とガードレールを適用する"
check "resolve-issue: 質問票に Gmail の回答候補のある質問を含める" item_has "$RI" "3. **PO への質問票**" "手順 2 で回答候補が見つかった質問"
check "resolve-issue: 既存の source: gmail の Q&A を既知の回答として除外に使わない" range_has "$RI" "1. **knowledge/ 検索**" "2. **Gmail 検索**" "\`source: gmail\` の Q&A は既知の回答として除外に使わず"
check "resolve-issue: 件数に関わらず /questionnaire を使う" item_has "$RI" "3. **PO への質問票**" "件数に関わらず \`/questionnaire\` で質問票にし"
check "create-issue: 同じ質問の source: gmail の Q&A の置き換えを HVE の有無に関わらず resolve-issue の手順 4 に従わせる" line_has "$CI" "同じ質問の \`source: gmail\` の Q&A は" "手順 4 のとおり置き換える"
check "create-issue: 件数に関わらず /questionnaire を使う" line_has "$CI" "手順 2 で回答候補が見つかった質問を" "件数に関わらず \`/questionnaire\` スキルで PO に質問する"
check "resolve-issue: PO が確定したら同じ質問の source: gmail の Q&A を置き換える" range_has "$RI" "**PO 回答の永続化**" "2. **実装計画 (Plan)**" "同じ質問の \`source: gmail\` の Q&A が \`knowledge/<domain>/\` にあれば、PO の回答で置き換える"
check "resolve-issue: 写しの hve-implement と食い違うときは本 skill を優先する" section_has "$RI" "$FEATURE_START" "$FEATURE_END" "本 skill の定義を優先する"
check "create-issue: Gmail の回答を保存せず既定値候補にする" item_has "$CI" "2. Gmail MCP で未解決の質問を検索" "発見した回答は保存せず"
check "create-issue: Gmail の回答の扱いは resolve-issue の定義に従う" range_has "$CI" "2. Gmail MCP で未解決の質問を検索" "4. PO 回答を" "扱いは resolve-issue skill Step 2 [feature] 項目 1 の手順 2 に定義"
check "create-issue: 既存の source: gmail の Q&A を既知の回答として除外に使わない" item_has "$CI" "既知の Q&A で回答できる質問は質問票から除外する" "\`source: gmail\` の Q&A は除外に使わず、既定値候補として質問票に含める"
check "hve-implement: Gmail の回答は保存せず質問票の既定値候補にする" line_has "$HI" "resolve-issue の前段（feature）" "Gmail の回答は保存せず、質問票の既定値候補にする"
check "hve-implement: Gmail の回答を qa に置く指示が残っていない" bash -c '! awk -v k="resolve-issue の前段（feature）" "index(\$0,k)" "$1" | grep -qF "Gmail の回答も"' _ "$HI"
ADR56="$(ls "$ROOT"/knowledge/adr/[0-9][0-9][0-9][0-9]-gmail-answers-*.md 2>/dev/null | head -1)"
check "Issue #56 の ADR がある（番号でなく slug で探す）" [ -n "$ADR56" ]
check "ADR 一覧に Issue #56 の ADR の行がある" grep -qF -- "-gmail-answers-" "$ROOT/knowledge/adr/README.md"
check "ADR 0017 が Partially superseded になっている" section_has "$ADR" "## ステータス" "## 背景と課題" "Partially superseded by"
check "ADR 一覧で 0017 が Partially superseded になっている" line_has "$ROOT/knowledge/adr/README.md" "[0017]" "Partially superseded by"

echo
echo "passed: $pass, failed: $fail"
[ "$fail" -eq 0 ]
