#!/bin/bash
# skills/global/commit-workflow/scripts/check-debug-log.sh の動作検査
#
# 実行: bash tests/test_check_debug_log.sh
#
#   - 既定パターン: ステージした追加行の console.log を、+++ 行付きで出す（+++ 行はファイルごとに 1 回）
#   - 削除行・未ステージの変更は出さない
#   - 本文が "++ " で始まる追加行もヘッダと誤認せず検査する
#   - color.ui=always でも検知する
#   - 引数でパターンを差し替えられる（バックスラッシュがそのまま正規表現として効く）
#   - デバッグ出力を含まない変更だけなら出力が空
#   - 不正なパターンは終了コード 0 以外
# 各ケースで終了コード 0 を確かめてから出力を評価する（異常終了で「出ない」系が通らないように）。

set -u
# 利用者の global / system の git 設定（diff.mnemonicPrefix・core.hooksPath 等）とフック環境変数から切り離す
export GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_NOSYSTEM=1
unset GIT_DIR GIT_WORK_TREE GIT_INDEX_FILE
SCRIPT="$(cd "$(dirname "$0")/.." && pwd)/skills/global/commit-workflow/scripts/check-debug-log.sh"
TMP="$(mktemp -d)"
trap 'rm -rf "${TMP:?}"' EXIT
g() { git -C "$TMP" -c user.name=t -c user.email=t@example.com -c commit.gpgsign=false "$@"; }
out=""; rc=0
run() { out="$(cd "$TMP" && bash "$SCRIPT" "$@" 2>&1)"; rc=$?; }
has() { grep -qF -- "$1" <<<"$out"; }
lacks() { ! grep -qF -- "$1" <<<"$out"; }

pass=0; fail=0
check() {
    local desc="$1"; shift
    if "$@"; then echo "[PASS] $desc"; pass=$((pass + 1))
    else echo "[FAIL] $desc"; fail=$((fail + 1)); fi
}

git init -q "$TMP"
printf 'keep\nconsole.log("old")\n' >"$TMP/a.js"
g add a.js && g commit -q -m init

# 何もステージしていない状態でも不正なパターンは検査失敗にする
run '('
check "不正なパターン（追加行なし）: 終了コード 0 以外" [ "$rc" -ne 0 ]

# デバッグ出力を含まない変更だけをステージ → 空
printf 'keep\nconsole.log("old")\nfoo()\n' >"$TMP/a.js"
g add a.js
run
check "混入なし: 正常終了" [ "$rc" -eq 0 ]
check "混入なし: 出力が空" [ -z "$out" ]
g reset -q

# 既定パターン
printf 'keep\nconsole.log("new")\nlogging.debug("x")\nconsole.debug("y")\n' >"$TMP/a.js"
printf 'console.log("unstaged")\n' >"$TMP/b.js"
printf '++ console.log("plusplus")\n' >"$TMP/c.md"
g add a.js c.md
run
check "既定パターン: 正常終了" [ "$rc" -eq 0 ]
check "既定パターン: +++ 行が出る" has '+++ b/a.js'
check "既定パターン: 追加行が出る" has '+console.log("new")'
check "既定パターン: 同じファイルの +++ 行は 1 回だけ" [ "$(grep -cF '+++ b/a.js' <<<"$out")" -eq 1 ]
check "既定パターン: 削除行は出ない" lacks 'old'
check "既定パターン: 未ステージは出ない" lacks 'unstaged'
printf 'console.log("tracked-unstaged")\n' >>"$TMP/a.js"
run
check "既定パターン: 追跡済みファイルの未ステージ変更は出ない" lacks 'tracked-unstaged'
check "既定パターン: 対象外の logging.debug は出ない" lacks 'logging.debug'
check "既定パターン: \"++ \" で始まる追加行も検査する" has '+++ console.log("plusplus")'
check "既定パターン: \"++ \" の行のファイル名が正しい" has '+++ b/c.md'

# color.ui=always でも検知する
g config color.ui always
run
check "color.ui=always: 追加行が出る" has '+console.log("new")'
g config --unset color.ui

# 外部 diff ツールの設定でも検知する
g config diff.external false
run
check "diff.external: 追加行が出る" has '+console.log("new")'
g config --unset diff.external

# パターン指定（バックスラッシュが正規表現として効く）
printf 'aXb\n' >"$TMP/d.txt"
g add d.txt
run 'logging\.debug'
check "パターン指定: 正常終了" [ "$rc" -eq 0 ]
check "パターン指定: logging.debug が出る" has '+logging.debug("x")'
check "パターン指定: console.log は出ない" lacks 'console.log'
run 'a\.b'
check "パターン指定 (a\\.b): 正常終了" [ "$rc" -eq 0 ]
check "パターン指定 (a\\.b): aXb に当たらない（\\. がリテラルのドットとして効く）" [ -z "$out" ]

# 不正なパターン → 検査失敗
run '('
check "不正なパターン: 終了コード 0 以外" [ "$rc" -ne 0 ]

echo
echo "結果: PASS=$pass FAIL=$fail"
[ "$fail" -eq 0 ]
