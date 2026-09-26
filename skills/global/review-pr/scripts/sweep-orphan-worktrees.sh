#!/bin/bash
# sweep-orphan-worktrees.sh — review-pr Step 8 の孤児 worktree の防御的 sweep。
#
# カレントディレクトリの git リポジトリで、.claude/worktrees 配下にあり、
# lock の pid が死んでいる worktree だけを unlock + remove する。
# lock の pid が生存している worktree（実行中の自セッション / 他の並走セッション）は触らない。
# pid が抽出できない lock（手動 lock 等）は安全側に倒して対象外。
# 異常終了したセッションの作業は消さない:
#   - 未コミットの変更がある worktree は削除せず、lock を戻して通知する（次回も通知される）
#   - 残骸ブランチは、他のどの ref にも含まれない独自コミットが無いときだけ削除する
#     （実行時にどのブランチを checkout していても判定が変わらない）
# 残したものは `[sweep]` で始まる行で出力する。
#
# SKILL.md 本文に置かず別ファイルにしている理由: Claude Code は skill 本文中の
# `$0` / `$1` 等を skill 引数で置換するため、awk の `$0` が壊れる。

set -u

# wt は substr で行末まで取る（パスにスペースが含まれても切れないように）
git worktree list --porcelain | awk '
  /^worktree /{wt=substr($0,10)}
  /^locked/{ if (match($0,/pid [0-9]+/)) print wt"\t"substr($0,RSTART+4,RLENGTH-4) }
' | while IFS=$'\t' read -r wt pid; do
    case "$wt" in */.claude/worktrees/*) ;; *) continue ;; esac   # 対象限定
    # 稼働中は触らない。kill -0 は他ユーザーの生存プロセスで失敗するため ps で判定する
    ps -p "$pid" >/dev/null 2>&1 && continue
    git worktree unlock "$wt" 2>/dev/null
    if ! git worktree remove "$wt" 2>/dev/null; then
        git worktree lock --reason "pid $pid" "$wt" 2>/dev/null
        echo "[sweep] 未コミットの変更があるため残した worktree: $wt"
        continue
    fi
    br="worktree-$(basename "$wt")"
    git rev-parse -q --verify "refs/heads/$br" >/dev/null || continue
    own=$(git rev-list --count "refs/heads/$br" --not --exclude="refs/heads/$br" --all)
    if [ "$own" -eq 0 ]; then
        git branch -D "$br" >/dev/null 2>&1
    else
        echo "[sweep] 独自コミットがあるため残したブランチ: $br ($own 件)"
    fi
done
git worktree prune
