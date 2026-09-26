#!/bin/bash
# skills/global/review-pr/scripts/sweep-orphan-worktrees.sh の動作検査
#
# 実行: bash tests/test_sweep_orphan_worktrees.sh
#
# 一時リポジトリに 3 つの worktree を作り、sweep 後に次を確認する:
#   - .claude/worktrees 配下 + lock の pid が死んでいる → 削除される
#   - .claude/worktrees 配下 + lock の pid が生存している → 残る
#   - .claude/worktrees 配下でない (pid は死んでいる) → 残る
#   - lock に pid が無い (手動 lock) → 残る
#   - パスにスペースを含む + pid が死んでいる → 削除される
#   - 未マージのコミットがある残骸ブランチ → worktree は削除、ブランチは残る

set -u
SWEEP="$(cd "$(dirname "$0")/.." && pwd)/skills/global/review-pr/scripts/sweep-orphan-worktrees.sh"
TMP="$(cd "$(mktemp -d)" && pwd -P)"   # macOS の /var → /private/var を git の表示に揃える
trap 'rm -rf "${TMP:?}"' EXIT

REPO="$TMP/repo"
git init -q "$REPO"
git -C "$REPO" -c user.name=t -c user.email=t@example.com commit -q --allow-empty -m init

# 存在しない pid を得る (起動して終了したプロセスの pid)
sleep 0 & DEAD_PID=$!; wait "$DEAD_PID"
LIVE_PID=$$

git -C "$REPO" worktree add -q -b worktree-agent-dead "$REPO/.claude/worktrees/agent-dead"
git -C "$REPO" worktree lock --reason "claude agent agent-dead (pid $DEAD_PID)" "$REPO/.claude/worktrees/agent-dead"
git -C "$REPO" worktree add -q -b worktree-agent-live "$REPO/.claude/worktrees/agent-live"
git -C "$REPO" worktree lock --reason "claude agent agent-live (pid $LIVE_PID)" "$REPO/.claude/worktrees/agent-live"
git -C "$REPO" worktree add -q -b worktree-agent-manual "$REPO/.claude/worktrees/agent-manual"
git -C "$REPO" worktree lock --reason "manual" "$REPO/.claude/worktrees/agent-manual"
git -C "$REPO" worktree add -q -b worktree-space "$REPO/.claude/worktrees/with space"
git -C "$REPO" worktree lock --reason "pid $DEAD_PID" "$REPO/.claude/worktrees/with space"
git -C "$REPO" worktree add -q -b worktree-agent-unmerged "$REPO/.claude/worktrees/agent-unmerged"
git -C "$REPO/.claude/worktrees/agent-unmerged" -c user.name=t -c user.email=t@example.com commit -q --allow-empty -m work
git -C "$REPO" worktree lock --reason "pid $DEAD_PID" "$REPO/.claude/worktrees/agent-unmerged"
git -C "$REPO" worktree add -q -b other "$TMP/other"
# 前提の確認: 以降の expect が「作れなかったから無い」で PASS しないようにする
for w in agent-dead agent-live agent-manual "with space" agent-unmerged; do
    git -C "$REPO" worktree list --porcelain | grep -qxF "worktree $REPO/.claude/worktrees/$w" \
        || { echo "[FAIL] 前提: worktree $w を作成できていない"; exit 1; }
done
git -C "$REPO" worktree lock --reason "pid $DEAD_PID" "$TMP/other"

(cd "$REPO" && bash "$SWEEP")

FAIL=0
LIST="$(git -C "$REPO" worktree list --porcelain)"
expect() {  # $1=present|absent $2=パス $3=説明
    if printf '%s\n' "$LIST" | grep -qxF "worktree $2"; then got=present; else got=absent; fi
    if [ "$got" = "$1" ]; then echo "[PASS] $3"; else echo "[FAIL] $3 (期待 $1 / 実際 $got)"; FAIL=1; fi
}
expect absent "$REPO/.claude/worktrees/agent-dead" "pid が死んだ .claude/worktrees 配下は削除"
expect present "$REPO/.claude/worktrees/agent-live" "pid が生存している worktree は残す"
expect present "$TMP/other" ".claude/worktrees 配下でない worktree は残す"
expect present "$REPO/.claude/worktrees/agent-manual" "pid の無い手動 lock は残す"
expect absent "$REPO/.claude/worktrees/with space" "スペースを含むパスも削除"
expect absent "$REPO/.claude/worktrees/agent-unmerged" "未マージのブランチを持つ worktree も削除"
if git -C "$REPO" rev-parse -q --verify worktree-agent-unmerged >/dev/null; then
    echo "[PASS] 未マージのコミットがある残骸ブランチは残す"
else
    echo "[FAIL] 未マージのコミットがある残骸ブランチが削除された"; FAIL=1
fi
if git -C "$REPO" rev-parse -q --verify worktree-agent-dead >/dev/null; then
    echo "[FAIL] 削除した worktree の残骸ブランチが残っている"; FAIL=1
else
    echo "[PASS] 残骸ブランチも削除"
fi

echo "==================================="
if [ "$FAIL" -eq 0 ]; then echo "ALL TESTS PASSED"; exit 0; else echo "SOME TESTS FAILED"; exit 1; fi
