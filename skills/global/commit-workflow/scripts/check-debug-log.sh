#!/bin/bash
# check-debug-log.sh — ステージした差分に混入したデバッグ出力を、ファイル名（+++ 行）付きで出す。
#
# 使い方: bash check-debug-log.sh ['<パターン>']
#   パターン（第 1 引数）は awk の POSIX 拡張正規表現（\b \s \d は使えない）。既定を置き換える。
#   省略時は console.log / console.debug / Log::info / Log::debug / print( を探す。
#   終了コード 0 で出力が空なら混入なし。終了コードが 0 以外なら検査失敗（パターンや git の状態を確認）。
#
# SKILL.md 本文に置かず別ファイルにしている理由: Claude Code は skill 本文中の
# `$0` / `$1` 等を skill 引数で置換するため、awk の `$0` が壊れる。
set -euo pipefail
PATTERN="${1:-console\.(log|debug)|Log::(info|debug)|print\(}"
# パターンは追加行が無くても先に検証する（awk は正規表現を初めて評価するときにコンパイルするため）
PATTERN="$PATTERN" awk 'BEGIN { if ("" ~ ENVIRON["PATTERN"]) {} }' </dev/null
# 色付け・外部 diff ツール・相対パス表示・textconv の設定に左右されないようにする。
# ファイルヘッダの +++ 行は diff --git 行の後だけで扱う（本文が "++ " で始まる追加行を誤認しない）。
# awk -v はバックスラッシュをエスケープとして解釈するので、パターンは環境変数で渡す。
git diff --cached -U0 --no-color --no-ext-diff --no-relative --no-textconv \
  | PATTERN="$PATTERN" awk '
      /^diff --git / { header = 1; next }
      header && /^\+\+\+ / { f = $0; shown = 0; next }
      /^@@/ { header = 0; next }
      !header && /^\+/ && $0 ~ ENVIRON["PATTERN"] { if (!shown) { print f; shown = 1 } print }'
