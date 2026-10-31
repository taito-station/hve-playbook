#!/bin/bash
# 質問の回答の保存先の契約検査（Issue #53・#56・#63・#64、ADR 0017・0019・0029・0030）
#
# 実行: bash tests/test_qa_answer_destination.sh
#
# 検査すること:
#   - resolve-issue の feature 前処理が、HVE 導入先（check-knowledge.py がある）の判定と、
#     回答を knowledge/<domain>/ ではなく qa/ に残す規則を定義する
#   - resolve-issue の項目 1 の 3（PO）、create-issue の質問票ゲートの 3 が、その規則を指す
#   - HVE が無いリポジトリの PO の回答の保存先（knowledge/<domain>/）は残る
#   - qa/ を回答の探索対象に加えない
#   - ADR 0017 と一覧の行がある
#   - 不確定点チェックで Gmail を検索しない。探索は knowledge → PO の質問票の 2 段（Issue #64、ADR 0029）
#   - 過去に保存した source: gmail の Q&A の特例規定（既定値候補化・PII の除外・ガードレール・置き換え・既定値候補が
#     複数のときの規定）は持たない（Issue #63、ADR 0030。ADR 0019 の規定を外した）

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

# 2) resolve-issue: 項目 1 の 3（PO）が規則を指す
check "resolve-issue: PO の回答の永続化が HVE 導入先では qa/*.md を指す" item_has "$RI" "**PO 回答の永続化**" "HVE 導入先では書かず、questionnaire skill の \`qa/*.md\` を正とする"

# 3) create-issue: 3 が resolve-issue の定義を指す
check "create-issue: PO の回答の永続化が HVE 導入先では qa/*.md を指す" item_has "$CI" "PO 回答を" "HVE 導入先では書かず、questionnaire skill の \`qa/*.md\` を正とする"
check "create-issue: 判定と保存先は resolve-issue の定義に従う" item_has "$CI" "PO 回答を" "判定と保存先は resolve-issue skill Step 2 [feature] 項目 1 に定義"

# 4) HVE が無いリポジトリの PO の回答の保存先は残る
check "resolve-issue: HVE が無いリポジトリでは knowledge/<domain>/ に PO の回答を書く" line_has "$RI" "**PO 回答の永続化**" "\`knowledge/<domain>/\` にナレッジファイルとして"
check "create-issue: HVE が無いリポジトリでは knowledge/<domain>/ に PO の回答を書く" line_has "$CI" "PO 回答を" "\`knowledge/<domain>/\` に永続化する"

# 5) qa/ を探索対象に加えない（knowledge 検索の手順に qa/ を書かない）
check "resolve-issue: knowledge 検索の手順に qa/ を加えない" range_lacks "$RI" "1. **knowledge/ 検索**" "2. **PO への質問票**" "qa/"
check "create-issue: knowledge 検索の手順に qa/ を加えない" range_lacks "$CI" "を検索（利用リポにある場合。domain は Issue の業務領域から判定）" "2. 残った未解決の質問を" "qa/"

# 6) 決定ログ
ADR="$(ls "$ROOT"/knowledge/adr/0017-*.md 2>/dev/null | head -1)"
check "ADR 0017 がある" [ -n "$ADR" ]
check "ADR 一覧に 0017 の行がある" grep -qF "0017" "$ROOT/knowledge/adr/README.md"

# 7) 不確定点チェックで Gmail を検索しない（Issue #64、ADR 0029）
check "resolve-issue: allowed-tools に Gmail の MCP が無い" bash -c '! grep -qF "mcp__claude_ai_Gmail" "$1"' _ "$RI"
check "create-issue: allowed-tools に Gmail の MCP が無い" bash -c '! grep -qF "mcp__claude_ai_Gmail" "$1"' _ "$CI"
check "resolve-issue: Gmail 検索の手順が無い" bash -c '! grep -qF "**Gmail 検索**" "$1"' _ "$RI"
check "create-issue: Gmail 検索の手順が無い" bash -c '! grep -qF "Gmail MCP" "$1"' _ "$CI"
check "resolve-issue: 前段の規則に Gmail で見つけた回答の扱いが残っていない" bash -c '! grep -qF "Gmail で見つけた回答" "$1"' _ "$RI"
check "resolve-issue: 手順 2 が PO への質問票" grep -qF "2. **PO への質問票**" "$RI"
check "resolve-issue: 手順 3 が PO 回答の永続化" grep -qF "3. **PO 回答の永続化**" "$RI"
check "create-issue: 手順 3 が PO 回答の永続化" grep -qF "3. PO 回答を \`knowledge/<domain>/\` に永続化する" "$CI"
check "resolve-issue: 手順 2・3 に Gmail が出てこない" range_lacks "$RI" "2. **PO への質問票**" "2. **実装計画 (Plan)**" "Gmail"
check "create-issue: 手順 2・3 に Gmail が出てこない" range_lacks "$CI" "2. 残った未解決の質問を" "4. 「スキップ」" "Gmail"
check "resolve-issue: HVE 導入先で knowledge に書かない回答は手順 3（PO の回答）" item_has "$RI" "**HVE 導入先**" "手順 3 の回答を"
check "resolve-issue: 手順 2 で回答候補が見つかった質問を質問票に含める指示が残っていない" bash -c '! grep -qF "手順 2 で回答候補が見つかった質問" "$1"' _ "$RI"
check "create-issue: 手順 2 で回答候補が見つかった質問を質問票に含める指示が残っていない" bash -c '! grep -qF "手順 2 で回答候補が見つかった質問" "$1"' _ "$CI"
check "resolve-issue: 件数に関わらず /questionnaire を使う" item_has "$RI" "2. **PO への質問票**" "件数に関わらず \`/questionnaire\` で質問票にし"
check "create-issue: 件数に関わらず /questionnaire を使う" line_has "$CI" "2. 残った未解決の質問を" "件数に関わらず \`/questionnaire\` スキルで PO に質問する"

# 8) 過去に保存した source: gmail の Q&A の特例規定を持たない（Issue #63、ADR 0030）
for f in "$RI" "$CI" "$HI"; do
    n="${f#"$ROOT"/}"
    check "$n: source: gmail の Q&A の特例規定が無い" bash -c '! grep -qF "source: gmail" "$1"' _ "$f"
done
check "resolve-issue: feature 前処理（不確定点チェックまで）に source: gmail 向けのガードレールが無い" range_lacks "$RI" "$FEATURE_START" "2. **実装計画 (Plan)**" "ガードレール"
check "create-issue: 質問票ゲートの既知回答の探索に source: gmail 向けのガードレールが無い" range_lacks "$CI" "3. 「質問票を実施」" "4. 「スキップ」" "ガードレール"
check "hve-implement: 前段（feature）に source: gmail 向けのガードレールが無い" bash -c '! awk -v k="resolve-issue の前段（feature）" "index(\$0,k)" "$1" | grep -qF "ガードレール"' _ "$HI"
check "resolve-issue: 既定値候補が複数のときの規定（Gmail 対応で入ったもの）が無い" bash -c '! grep -qF "既定値候補が複数" "$1"' _ "$RI"
check "resolve-issue: 写しの hve-implement と食い違うときは本 skill を優先する" section_has "$RI" "$FEATURE_START" "$FEATURE_END" "本 skill の定義を優先する"
check "hve-implement: 前段（feature）の探索順は knowledge → PO の質問票" line_has "$HI" "resolve-issue の前段（feature）" "探索順（knowledge → PO の質問票）"
check "hve-implement: 前段（feature）に Gmail 検索が残っていない" bash -c '! awk -v k="resolve-issue の前段（feature）" "index(\$0,k)" "$1" | grep -qF "→ Gmail →"' _ "$HI"

# 9) 決定ログ（Issue #56・#63・#64）
ADR56="$(ls "$ROOT"/knowledge/adr/[0-9][0-9][0-9][0-9]-gmail-answers-*.md 2>/dev/null | head -1)"
check "Issue #56 の ADR がある（番号でなく slug で探す）" [ -n "$ADR56" ]
check "ADR 一覧に Issue #56 の ADR の行がある" grep -qF -- "-gmail-answers-" "$ROOT/knowledge/adr/README.md"
check "ADR 0017 が Partially superseded になっている" section_has "$ADR" "## ステータス" "## 背景と課題" "Partially superseded by"
check "ADR 一覧で 0017 が Partially superseded になっている" line_has "$ROOT/knowledge/adr/README.md" "[0017]" "Partially superseded by"
ADR64="$(ls "$ROOT"/knowledge/adr/[0-9][0-9][0-9][0-9]-remove-gmail-search-*.md 2>/dev/null | head -1)"
check "Issue #64 の ADR がある（番号でなく slug で探す）" [ -n "$ADR64" ]
check "ADR 一覧に Issue #64 の ADR の行がある" grep -qF -- "-remove-gmail-search-" "$ROOT/knowledge/adr/README.md"
check "Issue #56 の ADR が Partially superseded になっている" section_has "$ADR56" "## ステータス" "## 背景と課題" "Partially superseded by"
check "ADR 一覧で Issue #56 の ADR が Partially superseded になっている" line_has "$ROOT/knowledge/adr/README.md" "-gmail-answers-as-questionnaire-defaults.md)" "Partially superseded by"
check "Issue #56 の ADR のステータスが Issue #63 の ADR を指す" section_has "$ADR56" "## ステータス" "## 背景と課題" "Partially superseded by 0030-drop-past-gmail-qa-"
ADR63="$(ls "$ROOT"/knowledge/adr/[0-9][0-9][0-9][0-9]-drop-past-gmail-qa-*.md 2>/dev/null | head -1)"
check "Issue #63 の ADR がある（番号でなく slug で探す）" [ -n "$ADR63" ]
check "ADR 一覧に Issue #63 の ADR の行がある" grep -qF -- "-drop-past-gmail-qa-" "$ROOT/knowledge/adr/README.md"
check "Issue #64 の ADR が Partially superseded になっている" section_has "$ADR64" "## ステータス" "## 背景と課題" "Partially superseded by"
check "ADR 一覧で Issue #64 の ADR が Partially superseded になっている" line_has "$ROOT/knowledge/adr/README.md" "-remove-gmail-search-from-uncertainty-check.md)" "Partially superseded by 0030-drop-past-gmail-qa-"
check "Issue #64 の ADR のステータスが Issue #63 の ADR を指す" section_has "$ADR64" "## ステータス" "## 背景と課題" "Partially superseded by 0030-drop-past-gmail-qa-"

echo
echo "passed: $pass, failed: $fail"
[ "$fail" -eq 0 ]
