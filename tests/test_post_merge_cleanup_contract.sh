#!/bin/bash
# post-merge-cleanup / next-issue skill の契約検査
#
# 実行: bash tests/test_post_merge_cleanup_contract.sh
#
# 検査すること:
#   - post-merge-cleanup が、他セッションの worktree・ブランチを消さないための条件と禁止事項を保っている
#     （マージしない・worktree remove --force を使わない・リモートブランチを消さない・
#       マージ済みの PR の判定は headRefOid まで見る・自分の worktree は HEAD を切り離してから抜ける）
#   - next-issue が、open の Issue だけを候補にし、読み取りだけで完結する
#   - 2 本が README と settings.json に登録されている

set -u
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PMC="$ROOT/skills/global/post-merge-cleanup/SKILL.md"
NI="$ROOT/skills/global/next-issue/SKILL.md"
pass=0
fail=0
check() {
    local name="$1"; shift
    if "$@"; then echo "[PASS] $name"; pass=$((pass + 1)); else echo "[FAIL] $name"; fail=$((fail + 1)); fi
}
has() { grep -qF -- "$2" "$1" 2>/dev/null; }
frontmatter_name() { [ "$(awk 'NR==1&&$0!="---"{exit} NR>1&&$0=="---"{exit} NR>1&&sub(/^name: */,""){print}' "$1" 2>/dev/null)" = "$2" ]; }
# コードブロックの中のコマンド行だけを見る
code_lacks() { [ -f "$1" ] && ! awk '/^ *```/{on=!on; next} on' "$1" | grep -qF -- "$2"; }
# 制約の節（禁止事項として文字列を挙げる）を除いた本文の、コードブロックの行とインラインコードを見る
cmd_text() {
    awk '/^## 制約/{skip=1} /^## 手順/{skip=0} !skip' "$1" \
        | awk '/^ *```/{on=!on; next} on{print; next} {while (match($0, /`[^`]+`/)) {print substr($0, RSTART, RLENGTH); $0 = substr($0, RSTART + RLENGTH)}}'
}
cmd_lacks() { [ -f "$1" ] && ! cmd_text "$1" | grep -qF -- "$2"; }

# 1) post-merge-cleanup
check "PMC: frontmatter の name が post-merge-cleanup" frontmatter_name "$PMC" post-merge-cleanup
check "PMC: マージはこの skill で行わない" has "$PMC" "マージはこの skill で行わない"
check "PMC: コマンドに worktree remove --force が無い" cmd_lacks "$PMC" "remove --force"
check "PMC: コマンドに worktree remove -f が無い" cmd_lacks "$PMC" "remove -f"
check "PMC: コードブロックに gh pr merge が無い" code_lacks "$PMC" "gh pr merge"
check "PMC: コマンドにリモートブランチの削除（--delete）が無い" cmd_lacks "$PMC" "push origin --delete"
check "PMC: コマンドにリモートブランチの削除（-d）が無い" cmd_lacks "$PMC" "push -d"
check "PMC: コマンドにリモートブランチの削除（:branch）が無い" cmd_lacks "$PMC" "push origin :"
check "PMC: リモートブランチを消さない" has "$PMC" "リモートブランチを消さない"
check "PMC: 対象の PR が MERGED でなければ止まる" has "$PMC" '`MERGED` でなければ'
check "PMC: マージ済みの PR の判定は headRefOid の祖先まで見る" has "$PMC" "--is-ancestor <tip> <headRefOid>"
check "PMC: ブランチ名の一致だけで判定しない理由を書く" has "$PMC" "ブランチ名の一致だけで判定しない"
check "PMC: 表に lock の条件がある" has "$PMC" '| lock されていない | porcelain に `locked` の行が無い |'
check "PMC: 表にマージ済みの PR の条件がある" has "$PMC" "| マージ済みの PR に対応する | 手順 2 の定義 |"
check "PMC: 表に未コミットの変更の条件がある" has "$PMC" '| 未コミットの変更が無い | `git -C <wt> status --porcelain` が空 |'
check "PMC: 表に HEAD がデフォルトブランチに入っている条件がある" has "$PMC" '| HEAD がデフォルトブランチに入っている | `git -C <wt> merge-base --is-ancestor HEAD origin/<default>` が真 |'
check "PMC: ignored のファイルは確かめてから消す" has "$PMC" '`git -C <wt> status --porcelain --ignored` で `!!` の行があれば、一覧で示し、消してよいかを確かめてから消す'
check "PMC: ブランチは git branch --merged だけで選ばない" has "$PMC" '`git branch --merged` だけでは選ばない'
check "PMC: branch -D の前に origin/<default> に入っていることを確かめる" has "$PMC" "merge-base --is-ancestor <branch> origin/<default>"
check "PMC: 自分の worktree は HEAD を切り離してから抜ける" has "$PMC" "git switch --detach"
check "PMC: デフォルトブランチを決め打ちしない" has "$PMC" "defaultBranchRef"
check "PMC: 孤児の掃除は review-pr のスクリプトを使う" has "$PMC" "review-pr/scripts/sweep-orphan-worktrees.sh"
check "PMC: [sweep] 行を報告する" has "$PMC" "[sweep]"
check "PMC: 参照するスクリプトが実在する" [ -f "$ROOT/skills/global/review-pr/scripts/sweep-orphan-worktrees.sh" ]
check "PMC: 最後に next-issue へつなぐ" has "$PMC" "next-issue"

# 2) next-issue
check "NI: frontmatter の name が next-issue" frontmatter_name "$NI" next-issue
check "NI: 候補は open の Issue だけ" has "$NI" "open の Issue だけ"
check "NI: 新規起票の候補を出さない" has "$NI" "新しく起票する Issue の候補は出さない"
check "NI: 読み取りだけで完結する" has "$NI" "読み取りだけで完結させる"
check "NI: 他セッションを ListAgents で確かめる" has "$NI" "ListAgents"
check "NI: クローズ対象は closingIssuesReferences で取る" has "$NI" "closingIssuesReferences"
check "NI: 着手は resolve-issue に渡す" has "$NI" "/resolve-issue"

# 3) 登録
check "README: /next-issue がある" has "$ROOT/README.md" "/next-issue"
check "README: /post-merge-cleanup がある" has "$ROOT/README.md" "/post-merge-cleanup"
check "settings.json: Skill(next-issue) がある" has "$ROOT/settings.json" "Skill(next-issue)"
check "settings.json: Skill(post-merge-cleanup) がある" has "$ROOT/settings.json" "Skill(post-merge-cleanup)"

echo
echo "結果: PASS=$pass FAIL=$fail"
[ "$fail" -eq 0 ]
