#!/bin/bash
# skills/global/review-pr/scripts/sweep-orphan-worktrees.sh の動作検査
#
# 実行: bash tests/test_sweep_orphan_worktrees.sh
#
# 一時リポジトリの main に 2 コミット (init → base) を積み、worktree はすべて base から作る。
# sweep はメイン checkout を base を含まない feature ブランチに移してから実行し、
# 残骸ブランチの削除判定が実行時の HEAD に依存しないことも確かめる。
#
#   - .claude/worktrees 配下 + lock の pid が死んでいる → 削除 (スペースを含むパスも)
#   - lock の pid が生存 (自プロセス / pid 1 = 他ユーザー所有で kill -0 が失敗する) → 残る
#   - .claude/worktrees 配下でない / lock に pid が無い (手動 lock) → 残る
#   - 未コミットの変更がある → 削除せず残し、lock も残して通知する
#   - 残骸ブランチ: 独自コミットが無ければ削除、あれば残して通知する

set -u
SWEEP="$(cd "$(dirname "$0")/.." && pwd)/skills/global/review-pr/scripts/sweep-orphan-worktrees.sh"
TMP="$(cd "$(mktemp -d)" && pwd -P)"   # macOS の /var → /private/var を git の表示に揃える
trap 'rm -rf "${TMP:?}"' EXIT

die() { echo "[FAIL] 前提: $1"; exit 1; }
g() { git -C "$REPO" -c user.name=t -c user.email=t@example.com -c commit.gpgsign=false "$@"; }

REPO="$TMP/repo"
WT="$REPO/.claude/worktrees"
git init -q -b main "$REPO" || die "git init"
g commit -q --allow-empty -m init || die "init コミット"
INIT=$(g rev-parse HEAD)
g commit -q --allow-empty -m base || die "base コミット"

# 存在しない pid を得る (起動して終了したプロセスの pid)
sleep 0 & DEAD_PID=$!; wait "$DEAD_PID"

add_locked() {  # $1=パス $2=ブランチ名 $3=lock 理由
    g worktree add -q -b "$2" "$1" || die "worktree add $1"
    g worktree lock --reason "$3" "$1" || die "worktree lock $1"
}
add_locked "$WT/agent-dead" worktree-agent-dead "claude agent agent-dead (pid $DEAD_PID)"
add_locked "$WT/agent-live" worktree-agent-live "claude agent agent-live (pid $$)"
add_locked "$WT/agent-pid1" worktree-agent-pid1 "claude agent agent-pid1 (pid 1)"
add_locked "$WT/agent-manual" worktree-agent-manual "manual"
add_locked "$WT/with space" worktree-space "pid $DEAD_PID"
add_locked "$WT/agent-unmerged" worktree-agent-unmerged "pid $DEAD_PID"
git -C "$WT/agent-unmerged" -c user.name=t -c user.email=t@example.com -c commit.gpgsign=false \
    commit -q --allow-empty -m work || die "未マージ用のコミット"
add_locked "$WT/agent-dirty" worktree-agent-dirty "pid $DEAD_PID"
echo "未コミット" > "$WT/agent-dirty/wip.txt"
add_locked "$TMP/other" other "pid $DEAD_PID"

# メイン checkout を base を含まない feature に移す
g switch -q -c feature "$INIT" || die "feature ブランチ"

# 前提の確認: worktree が作られ lock されていること (「作れなかったから無い」で PASS させない)
PORC="$(git -C "$REPO" worktree list --porcelain)"
for p in "$WT/agent-dead" "$WT/agent-live" "$WT/agent-pid1" "$WT/agent-manual" \
         "$WT/with space" "$WT/agent-unmerged" "$WT/agent-dirty" "$TMP/other"; do
    printf '%s\n' "$PORC" | awk -v w="worktree $p" '$0==w{f=1; next} /^worktree /{f=0} f && /^locked/{ok=1} END{exit !ok}' \
        || die "$p が作成・lock されていない"
done

OUT="$(cd "$REPO" && bash "$SWEEP" 2>&1)"
echo "$OUT"

FAIL=0
LIST="$(git -C "$REPO" worktree list --porcelain)"
expect() {  # $1=present|absent $2=パス $3=説明
    if printf '%s\n' "$LIST" | grep -qxF "worktree $2"; then got=present; else got=absent; fi
    if [ "$got" = "$1" ]; then echo "[PASS] $3"; else echo "[FAIL] $3 (期待 $1 / 実際 $got)"; FAIL=1; fi
}
branch() {  # $1=present|absent $2=ブランチ名 $3=説明
    if git -C "$REPO" rev-parse -q --verify "refs/heads/$2" >/dev/null; then got=present; else got=absent; fi
    if [ "$got" = "$1" ]; then echo "[PASS] $3"; else echo "[FAIL] $3 (期待 $1 / 実際 $got)"; FAIL=1; fi
}
expect absent "$WT/agent-dead" "pid が死んだ .claude/worktrees 配下は削除"
expect present "$WT/agent-live" "pid が生存している worktree は残す"
expect present "$WT/agent-pid1" "他ユーザー所有の生存 pid (kill -0 が失敗する) は残す"
expect present "$WT/agent-manual" "pid の無い手動 lock は残す"
expect present "$TMP/other" ".claude/worktrees 配下でない worktree は残す"
expect absent "$WT/with space" "スペースを含むパスも削除"
expect absent "$WT/agent-unmerged" "独自コミットのあるブランチを持つ worktree も削除"
expect present "$WT/agent-dirty" "未コミットの変更がある worktree は残す"
if printf '%s\n' "$LIST" | awk -v w="worktree $WT/agent-dirty" '$0==w{f=1; next} /^worktree /{f=0} f && /^locked/{ok=1} END{exit !ok}'; then
    echo "[PASS] 残した worktree は lock を戻す (次回も対象・通知になる)"
else
    echo "[FAIL] 残した worktree の lock が外れている"; FAIL=1
fi
if [ -f "$WT/agent-dirty/wip.txt" ]; then echo "[PASS] 未コミットのファイルは消えない"; else echo "[FAIL] 未コミットのファイルが消えた"; FAIL=1; fi
branch absent worktree-agent-dead "独自コミットの無い残骸ブランチは削除 (HEAD が基点を含まなくても)"
branch present worktree-agent-unmerged "独自コミットのある残骸ブランチは残す"
if printf '%s\n' "$OUT" | grep -q '^\[sweep\] 独自コミットがあるため残したブランチ: worktree-agent-unmerged'; then echo "[PASS] 残したブランチを通知"; else echo "[FAIL] 残したブランチの通知が無い"; FAIL=1; fi
if printf '%s\n' "$OUT" | grep -q '^\[sweep\] 未コミットの変更があるため残した worktree: .*agent-dirty'; then echo "[PASS] 残した worktree を通知"; else echo "[FAIL] 残した worktree の通知が無い"; FAIL=1; fi

echo "==================================="
if [ "$FAIL" -eq 0 ]; then echo "ALL TESTS PASSED"; exit 0; else echo "SOME TESTS FAILED"; exit 1; fi
