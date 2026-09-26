#!/bin/bash
# sweep-orphan-worktrees.sh — review-pr Step 8 の孤児 worktree の防御的 sweep。
#
# カレントディレクトリの git リポジトリで、.claude/worktrees 配下にあり、
# lock の pid が死んでいる worktree だけを unlock + remove する。
# lock の pid が生存している worktree（実行中の自セッション / 他の並走セッション）は触らない。
# pid が抽出できない lock（手動 lock 等）は安全側に倒して対象外。
# 残骸ブランチはマージ済みのときだけ消す（未マージのコミットは異常終了したセッションの作業なので残す）。
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
    git worktree remove --force "$wt" 2>/dev/null || continue
    br="worktree-$(basename "$wt")"
    git rev-parse -q --verify "refs/heads/$br" >/dev/null || continue
    git branch -d "$br" >/dev/null 2>&1 \
      || echo "[sweep] 未マージのコミットがあるため残したブランチ: $br"
done
git worktree prune
