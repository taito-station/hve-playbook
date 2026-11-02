#!/bin/bash
# prompt audit（2026-11、対象モデル Claude Opus 5.5）で直した review-pr・create-pr の文面の契約検査（Issue #91 の B 節）
#
# 実行: bash tests/test_prompt_audit_pr_skills_contract.sh
#
# 検査すること:
#   - 規則の根拠に、事故の実例・実証例の括弧書きを書かない
#   - 実行手順に、却下した代替案（「採らない案」）や存在しない静的検査の保守メモを書かない
#   - 「迷ったら実施してよい」のような後押しを書かない
#   - ブラウザテストの網羅の範囲は残し、叱咤の言い回しを書かない
#   - Blade の表示変数の検査は diff で変えた変数に絞り、重大度を目的との関係で分ける
#   - 同じ禁止（depth の独自付与・レビュー skill の直接呼び出し）を重ねて書かない
#   - 対応履歴の要約に行数・件数の上限を付けない
#   - 前の版との差分の言い回し（従来・現行）を書かない

set -u
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
RP="$ROOT/skills/global/review-pr/SKILL.md"
RPP="$ROOT/skills/global/review-pr/references/reviewer-prompts.md"
FIX="$ROOT/skills/global/review-pr/references/fix-steps.md"
CP="$ROOT/skills/global/create-pr/SKILL.md"
pass=0
fail=0
check() {
    local name="$1"; shift
    if "$@"; then echo "[PASS] $name"; pass=$((pass + 1)); else echo "[FAIL] $name"; fail=$((fail + 1)); fi
}
has() { grep -qF -- "$2" "$1" 2>/dev/null; }
lacks() { [ -f "$1" ] && ! grep -qF -- "$2" "$1"; }
count_is() { [ "$(grep -cF -- "$2" "$1" 2>/dev/null)" = "$3" ]; }

# B1: 事故の実例の括弧書き
check "review-pr: 短縮禁止の理由に事故の実例を書かない" lacks "$RP" "inode race"
check "review-pr: 短縮禁止の理由に実証例を書かない" lacks "$RP" "実証例"
check "review-pr: 短縮禁止の一般則は残す" has "$RP" "修正のコード量と影響範囲は比例しない。"
check "create-pr: 短縮禁止の参照先に実例を挙げない" has "$CP" "短縮禁止の **正本・理由・具体的に禁止される行動** は"

# B2・B3・B4: 採らない案・存在しない静的検査・迷ったら実施
check "create-pr: 却下した代替案を手順に書かない" lacks "$CP" "**採らない案**"
check "create-pr: 存在しない静的検査の保守メモを書かない" lacks "$CP" "静的検査を置く場合に"
check "review-pr: 他のレビュー skill を Skill ツールで呼んでレビュアーの代わりにしない（重要原則 1）" has "$RP" "他のレビュー skill を呼ぶと同一コンテキストで走るので、レビュアーの代わりにしない。"
check "create-pr: 完了報告で未実行のパスが無いことを確かめる" has "$CP" "完了報告では未実行のパスが無いことを確かめ、"
check "create-pr: 経路 A は force を使わないことは残す" has "$CP" "経路 A の通常 push（7-1）と PR 作成（7-2）では force を使わない"
check "create-pr: ブラウザテストを条件外でも実施してよいと後押ししない" lacks "$CP" "実施したほうが安心な場合は実施して構わない"

# B5: ブラウザテストの叱咤
check "create-pr: 「理由にならない」と叱咤しない" lacks "$CP" "は理由にならない"
check "create-pr: 「やらなかった」ではなく、と叱咤しない" lacks "$CP" "「やらなかった」ではなく"
check "create-pr: 網羅の範囲（状態遷移の全パス）は残す" has "$CP" "**状態遷移の全パス**"
check "create-pr: 実行できないパスは理由と共に明示する" has "$CP" "実行できないパスがある場合は、そのパスと実行できない理由を明示する"

# B6: Blade の表示変数
check "reviewer-prompts: Blade の全変数に Must-fix を求めない" lacks "$RPP" "Blade 内の全 \`{{ \$変数名 }}\`"
check "reviewer-prompts: diff で変えた表示変数に絞る" has "$RPP" "diff で追加・変更した \`{{ \$変数名 }}\` / \`wire:model\` 参照"

# B7・B8: 同じ禁止の重複
check "create-pr: depth 独自付与の禁止は Step 0 の 1 か所だけ" count_is "$CP" "**depth 独自付与の禁止**" 1
check "review-pr: レビュー skill を Skill ツールで呼ばない旨を Step 2 で重ねない" lacks "$RP" "**重要**: Skill ツールで他のレビュー skill を直接呼び出すと"

# B9: 対応履歴の行数・件数の上限
check "fix-steps: 対応履歴の要約に行数の上限を付けない" lacks "$FIX" "3-5 行で要約"
check "fix-steps: 主な auto-fix に件数の上限を付けない" lacks "$FIX" "<短い箇条書き 2-3 件>"

# B10: 前の版との差分の言い回し
check "review-pr: 深度の表に「従来方式」と書かない" lacks "$RP" "従来方式"
check "create-pr: マニュアルの画像を「従来どおり」と書かない" lacks "$CP" "従来どおりコミットする"
check "create-pr: depth なしを「現行動作」と書かない" lacks "$CP" "現行動作"

echo
echo "結果: PASS=$pass FAIL=$fail"
[ "$fail" -eq 0 ]
