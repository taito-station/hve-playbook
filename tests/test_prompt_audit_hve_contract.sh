#!/bin/bash
# prompt audit（2026-11、対象モデル Claude Opus 5.5）で直した HVE の skill・agents の文面の契約検査（Issue #91 の D 節）
#
# 実行: bash tests/test_prompt_audit_hve_contract.sh
#
# 検査すること:
#   - ARD の fan-out が hve-analyst を使い、design pipeline が ARD に attached_docs を渡す
#   - 判断の出力（ブロッカー・受入基準・示唆・課題・推奨戦略）に件数の上限・下限を付けない
#   - アーキテクチャ選定で配点・重み・総合スコアをモデルに計算させない
#   - AKM のカバレッジ集計はコマンドで取る
#   - AAS の実行手順を既定の動作まで振り付けない
#   - hve-reviewer の禁止に理由を添え、hve-review skill と揃える
#   - 理由が添えてある制約に「絶対に」の強調を付けない

set -u
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ARD="$ROOT/skills/hve-ard/SKILL.md"
WF="$ROOT/workflows/hve-design-pipeline.js"
S31="$ROOT/skills/hve-ard/templates/step-3.1-usecase-skeleton.md"
S12="$ROOT/skills/hve-ard/templates/step-1.2-business-join.md"
A21="$ROOT/skills/hve-aad-web/templates/step-2.1-screen-detail.md"
A1="$ROOT/skills/hve-aad-web/templates/step-1-screen-list.md"
ARCH="$ROOT/skills/hve-aas/templates/step-1-arch-selection.md"
AAS="$ROOT/skills/hve-aas/SKILL.md"
AKM="$ROOT/skills/hve-akm/SKILL.md"
REV="$ROOT/agents/hve-reviewer.md"
pass=0
fail=0
check() {
    local name="$1"; shift
    if "$@"; then echo "[PASS] $name"; pass=$((pass + 1)); else echo "[FAIL] $name"; fail=$((fail + 1)); fi
}
has() { grep -qF -- "$2" "$1" 2>/dev/null; }
lacks() { [ -f "$1" ] && ! grep -qF -- "$2" "$1"; }
count_is() { [ "$(grep -cF -- "$2" "$1" 2>/dev/null)" = "$3" ]; }

# D1・D2: hve-analyst と attached_docs
check "ARD: Step 1.1・3.2 の fan-out が hve-analyst を使う" count_is "$ARD" "Agent tool（\`subagent_type: hve-analyst\`）のサブエージェント" 2
check "pipeline: ARD に attached_docs を渡す" has "$WF" "- attached_docs: \${attachedDocs || '未指定'}"
check "pipeline: attached_docs の配列を連結し、空なら未指定にする" has "$WF" "? ardParams.attached_docs.join(', ')"

# D3〜D5: 件数の上限・下限
check "ARD step-3.1: ブロッカーに上限を付けない" lacks "$S31" "最大 10 件"
check "ARD step-3.1: ブロッカーはすべて挙げる" has "$S31" "すべてリストアップする"
check "AAD step-2.1: 受入基準の個数を指定しない" lacks "$A21" "3〜7個"
check "ARD step-1.2: 示唆・課題に件数を指定しない" lacks "$S12" "3〜7 点"
check "ARD step-1.2: 推奨戦略に件数を指定しない" lacks "$S12" "3〜5 個"
check "ARD step-1.2: 件数を水増ししない規則は残す" has "$S12" "件数を水増ししない"

# D6: 配点・重み・総合スコア
check "AAS step-1: 配点をモデルに計算させない" lacks "$ARCH" "◎(3点)"
check "AAS step-1: 総合スコアを出させない" lacks "$ARCH" "総合スコア"
check "AAS step-1: 評価マトリクスに重みの列を置かない" lacks "$ARCH" "| 評価軸 | 重み |"
check "AAS step-1: 決め手の軸と次点を採らなかった理由を書かせる" has "$ARCH" "次点の候補を採らなかった理由"
check "AAS step-1: 選定根拠の雛形に次点を採らなかった理由の欄がある" has "$ARCH" "- 次点（[候補名]）を採らなかった理由:"

# D7: AKM の集計（SKILL.md の python を抜き出し、模擬 knowledge で実行する）
akm_counts_frontmatter_only() {
    command -v python3 >/dev/null 2>&1 || { echo "SKIP: python3 が無い"; return 0; }
    local tmp script out expected
    tmp=$(mktemp -d)
    script="$tmp/akm.py"
    awk 'index($0,"python3 - <<'"'"'PY'"'"'")>0{on=1;next} on&&$0~/^ *PY$/{exit} on{sub(/^   /,"");print}' "$AKM" > "$script"
    mkdir -p "$tmp/knowledge/adr" "$tmp/knowledge/sub/adr"
    # 本文の YAML 例の doc_class は拾わない・クォートと行末コメントを外す
    printf -- '---\ntitle: A\nstatus: "Confirmed"  # 確認済み\n---\n本文\n```yaml\ndoc_class: FAKE\n```\nTBD\n' > "$tmp/knowledge/a.md"
    # CRLF の文書
    printf -- '---\r\ntitle: B\r\ndoc_class: D01\r\nstatus: Tentative\r\n---\r\n本文\r\n' > "$tmp/knowledge/b.md"
    # 最上位の adr/ と README.md は対象外。サブディレクトリの README.md と adr/ は対象
    printf -- '# ADR TBD\n' > "$tmp/knowledge/adr/0001-x.md"
    printf -- 'README TBD\n' > "$tmp/knowledge/README.md"
    printf -- '---\nstatus: Confirmed\ndoc_class: D02\n---\nTBD\n' > "$tmp/knowledge/sub/README.md"
    printf -- '---\nstatus: Tentative\n---\nTBD\n' > "$tmp/knowledge/sub/adr/y.md"
    out=$(cd "$tmp" && python3 "$script")
    expected=$(printf '%s\n' \
        "	Confirmed	knowledge/a.md	TBD:9" \
        "D01	Tentative	knowledge/b.md	TBD:" \
        "D02	Confirmed	knowledge/sub/README.md	TBD:5" \
        "	Tentative	knowledge/sub/adr/y.md	TBD:4")
    rm -rf "$tmp"
    [ "$out" = "$expected" ] || { echo "  期待: $expected"; echo "  実際: $out"; return 1; }
}
check "AKM: 集計は frontmatter だけを読み、値を正規化し、check-knowledge と同じ範囲を対象にする" akm_counts_frontmatter_only

# D8: AAS の実行手順
check "AAS: 実行手順を 5 手に振り付けない" lacks "$AAS" "5. 次のステップに進む"
check "AAS: 必須入力の欠落で止まる規則は残す" has "$AAS" "必須入力の欠落は停止"

# D9: hve-reviewer
check "hve-reviewer: 理由の無い禁止を書かない" lacks "$REV" "存在しない問題を指摘してはいけない"
check "hve-reviewer: 存在しない問題を指摘しない理由を添える" has "$REV" "存在しない問題を指摘しない（誤った指摘に基づく修正は成果物を劣化させる）"
check "hve-reviewer: 指摘に修正案を付ける" has "$REV" "指摘には修正案を付ける"

# D10: 「絶対に」
check "AAD step-1: 理由の添えてある制約に「絶対に」を付けない" lacks "$A1" "絶対に含めない"
check "AAD step-1: 他 APP の画面行を含めない制約は残す" has "$A1" "他 APP の画面行を含めない（並列実行での衝突防止）"

echo
echo "結果: PASS=$pass FAIL=$fail"
[ "$fail" -eq 0 ]
