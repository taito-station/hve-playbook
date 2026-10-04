#!/bin/bash
# SessionStart hook: knowledge の stale 状態を報告する（#27 タスク 4）。
#
# `bump-distilled-sha.py --all-stale --dry-run` を実行し、STALE が 0 件なら何も出さない
# （ノイズにしない）。1 件以上あれば件数と bump の使い方を短く出す（SessionStart の標準出力は
# Claude の文脈に入る）。bump が判定不能（exit 2）のときはその旨を 1 行だけ出す。
#
# python3 が無い・git リポジトリでない・bump 自体が無い／失敗した場合は、何も壊さず exit 0
# にする（セッション開始を妨げない）。
#
# bump のパスは**このスクリプト自身の位置から**解決する。導入先では
# `.claude/scripts/hve/hooks/session-stale-check.sh` に配置され、bump は 1 階層上の
# `.claude/scripts/hve/bump-distilled-sha.py` に同居する前提。
#
# settings.json への配線例（導入先が手で追加する。timeout は 30 秒程度を目安にする。履歴を遡るので大きなリポジトリでは時間がかかる）:
#   {
#     "hooks": {
#       "SessionStart": [
#         {
#           "hooks": [
#             {
#               "type": "command",
#               "command": "bash \"$CLAUDE_PROJECT_DIR\"/.claude/scripts/hve/hooks/session-stale-check.sh",
#               "timeout": 30
#             }
#           ]
#         }
#       ]
#     }
#   }
set -uo pipefail

HOOK_DIR="$(cd "$(dirname "$0")" && pwd)"
BUMP="$HOOK_DIR/../bump-distilled-sha.py"

REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null)" || exit 0
command -v python3 >/dev/null 2>&1 || exit 0
[ -f "$BUMP" ] || exit 0

output="$(cd "$REPO_ROOT" && python3 "$BUMP" --all-stale --dry-run 2>&1)"
rc=$?

if [ "$rc" -eq 2 ]; then
  echo "⚠ knowledge の stale 判定が完了できない（判定不能）。bump-distilled-sha.py の出力を確認する"
  exit 0
fi

if echo "$output" | grep -q "STALE な文書は無い"; then
  exit 0
fi

stale_count=$(echo "$output" | grep -c "^（dry-run）" || true)
if [ "$stale_count" -gt 0 ]; then
  echo "⚠ 蒸留が必要な knowledge: ${stale_count} 件"
  echo "  python3 .claude/scripts/hve/bump-distilled-sha.py --all-stale で追従する"
fi

exit 0
