#!/bin/bash
# prompt audit（2026-11、対象モデル Claude Opus 5.5）で直した箇所の契約検査（Issue #90・#91）
#
# 実行: bash tests/test_prompt_audit_contract.sh
#
# 検査すること:
#   - create-pr の最終報告の巡数が、--depth で決まる上限（ITER_MAX）と食い違わない
#   - resolve-issue が独自の ADR テンプレートを持たず、様式を documentation-standards に任せる
#   - CLAUDE.md が今のツール一覧に無いツール名（view）を挙げない
#   - design pipeline の成果物の有無を確かめるだけの agent() は effort を low にする
#   - CLAUDE.md の委譲の規則に条件（複数ファイルにまたがる調査）があり、Bash の規則から消した経緯の行（許可要求ログの件数）が戻らず、`cd` を使ってよい例外は残る

set -u
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
CP="$ROOT/skills/global/create-pr/SKILL.md"
RI="$ROOT/skills/global/resolve-issue/SKILL.md"
CM="$ROOT/CLAUDE.md"
WF="$ROOT/workflows/hve-design-pipeline.js"
pass=0
fail=0
check() {
    local name="$1"; shift
    if "$@"; then echo "[PASS] $name"; pass=$((pass + 1)); else echo "[FAIL] $name"; fail=$((fail + 1)); fi
}
has() { grep -qF -- "$2" "$1" 2>/dev/null; }
lacks() { [ -f "$1" ] && ! grep -qF -- "$2" "$1"; }
# verify 用の agent() の opts の行（label が '<名前>:verify'）に effort: 'low' がある
# （opts を 1 行で書いている前提。複数行に分けたら、この検査も合わせて直す）
verify_low() { grep -F "label: '$1:verify'" "$WF" 2>/dev/null | grep -qF "effort: 'low'"; }

# 1) create-pr の最終報告
check "create-pr: 巡数の上限を 1-5 に固定しない" lacks "$CP" "(1-5)"
check "create-pr: 最終報告の巡数は ITER_MAX を上限にする" has "$CP" "セルフレビュー巡数 (1〜ITER_MAX)"

# 2) resolve-issue の ADR
check "resolve-issue: 独自の ADR テンプレートを持たない" lacks "$RI" "ADRテンプレート"
check "resolve-issue: ADR の見出しを Issue 番号で採番しない" lacks "$RI" "# <Issue番号>. タイトル"
check "resolve-issue: ADR のステータスに独自の語（承認済み）を使わない" lacks "$RI" "承認済み"
check "resolve-issue: ADR に独自の章（## コンテキスト）を持たない" lacks "$RI" "## コンテキスト"
check "resolve-issue: ADR の様式を documentation-standards に任せる" has "$RI" "様式（章立て・採番・ステータス値）も利用リポの \`documentation-standards\` skill に従う"

# 3) CLAUDE.md のツール名
check "CLAUDE.md: 無いツール名 view を挙げない" lacks "$CM" "\`view\` / \`Read\`"
check "CLAUDE.md: 既知のファイルは直接 Read してよい" has "$CM" "既知のファイル名や行番号がわかっているときは、直接 \`Read\` してよい"

# 4) design pipeline の verify
for s in ARD AAS AAD-WEB; do
    check "pipeline: ${s}:verify の effort が low" verify_low "$s"
done

# 5) CLAUDE.md の委譲の規則と経緯の記述（Issue #91 の A）
check "CLAUDE.md: 調査の委譲に条件の無い既定を置かない" lacks "$CM" "- リサーチ・調査はサブエージェントに任せる"
check "CLAUDE.md: 複数ファイルにまたがる調査を委譲し、単発の確認は自分で読む" has "$CM" "- 複数ファイルにまたがる調査は、サブエージェントに任せてメインのコンテキストを節約する（ファイル・シンボルが分かっている単発の確認は自分で読む）"
check "CLAUDE.md: Bash の規則から消した経緯の行（許可要求ログの件数）が戻っていない" lacks "$CM" "許可要求ログ 257 件"
check "CLAUDE.md: cd を使ってよい例外は残す" has "$CM" "どうしても作業ディレクトリを移す必要がある場合（\`npm ci\` など cwd 依存のもの）だけ \`cd\` を使う。"

echo
echo "結果: PASS=$pass FAIL=$fail"
[ "$fail" -eq 0 ]
