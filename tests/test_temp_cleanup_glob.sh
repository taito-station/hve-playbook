#!/bin/bash
# create-pr・review-pr の docs/temp の片付けが、review-*.diff の有無に関わらず動くことの検査（Issue #108）
#
# 実行: bash tests/test_temp_cleanup_glob.sh
# 前提: zsh（無ければ動作の検査だけ SKIP）
#
# 背景: Claude Code の Bash ツールのシェルは zsh のことがあり、zsh は一致しない glob の行を
# 「no matches found」で実行しない。review-*.diff を同じ rm -f に並べると、diff が無いときに
# ほかのファイル（pr-body.md・sidecar など）が巻き添えで残る。
#
# 検査すること:
#   - create-pr（Step 4 項目 6・Step 9）と review-pr（Step 8）で、review-*.diff の glob を
#     rm -f に直接並べる形が残っていない（glob は bash -c に渡す。SKILL.md の本文では位置引数の記法が
#     skill の引数に置き換えられるので、ディレクトリは "$1" でなく環境変数 REPO_ROOT で渡す）
#   - 3 か所とも、片付けの前に REPO_ROOT が空でないことを確かめる（Bash ツールの呼び出しをまたぐと
#     シェルの変数は消え、空のまま進むと /docs/temp/... を消そうとする）
#   - 新しい片付けの行を zsh で実行すると、review-*.diff の有無に関わらず rc=0 で、
#     並べたファイルと review-*.diff が消え、ほかのファイルは残る。REPO_ROOT が空なら rm を 1 つも実行しない
#
# zsh は -f で起動し、利用者の ~/.zshenv（setopt NULL_GLOB など）に左右されない既定の設定（NOMATCH が有効）で検査する。
# ROOT はこのファイルからの相対で決める（worktree から実行したときはブランチの手順書を検査する）

set -u
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
CREATE="$ROOT/skills/global/create-pr/SKILL.md"
REVIEW="$ROOT/skills/global/review-pr/SKILL.md"
pass=0
fail=0
check() {
    local name="$1"; shift
    if "$@"; then echo "[PASS] $name"; pass=$((pass + 1)); else echo "[FAIL] $name"; fail=$((fail + 1)); fi
}

GLOB_LINE="REPO_ROOT=\"\$REPO_ROOT\" bash -c 'rm -f \"\$REPO_ROOT\"/docs/temp/review-*.diff'"
STEP9_RM='rm -f "$REPO_ROOT/docs/temp/pr-body.md" "$REPO_ROOT/docs/temp/.pr-body.owner" "$REPO_ROOT/docs/temp/.cost-snapshot" "$REPO_ROOT/docs/temp/.follow.log" "$REPO_ROOT/docs/temp/squash-msg.txt"'
STEP4_RM='rm -f "$REPO_ROOT/docs/temp/pr-body.md" "$REPO_ROOT/docs/temp/.pr-body.owner" "$REPO_ROOT/docs/temp/.cost-snapshot"'
GUARD_CREATE=': "${REPO_ROOT:?REPO_ROOT が空。Step 1 と同じく解決し直してから実行する}"'
GUARD_REVIEW=': "${REPO_ROOT:?REPO_ROOT が空。Step 0.2 と同じく解決し直してから実行する}"'

# rm -f のあとに review-*.diff の glob が来る形が、正しい形（GLOB_LINE）の外に残っていないこと。
# 行を丸ごと除外すると、正しい形と同じ行に並んだ素の glob を見逃すので、行から正しい形を取り除いてから照合する
# （「review-*.diff は … rm -f に並べず」のような説明の行は、glob が rm -f より前なので対象外）
no_bare_glob() {
    ! awk -v g="$GLOB_LINE" '{ while ((i = index($0, g)) > 0) $0 = substr($0, 1, i - 1) substr($0, i + length(g)); print }' "$1" \
        | grep -qE 'rm -f.*review-"?\*\.diff'
}

# 1) 手順書の記述
check "create-pr: review-*.diff の glob を rm -f に直接並べない" no_bare_glob "$CREATE"
check "review-pr: review-*.diff の glob を rm -f に直接並べない" no_bare_glob "$REVIEW"
check "create-pr Step 9: REPO_ROOT が空なら止める（行全体で照合）" grep -qxF -- "$GUARD_CREATE" "$CREATE"
check "create-pr Step 9: glob を含まないファイルを rm -f に並べる（行全体で照合）" grep -qxF -- "$STEP9_RM" "$CREATE"
check "create-pr Step 9: review-*.diff は bash -c で消す（行全体で照合）" grep -qxF -- "$GLOB_LINE" "$CREATE"
check "create-pr Step 4 項目 6: REPO_ROOT が空なら止める" grep -qF -- "\`$GUARD_CREATE\`" "$CREATE"
check "create-pr Step 4 項目 6: glob を含まないファイルを rm -f に並べる" grep -qF -- "\`$STEP4_RM\`" "$CREATE"
check "create-pr Step 4 項目 6: review-*.diff は bash -c で消す" grep -qF -- "\`$GLOB_LINE\`" "$CREATE"
check "review-pr Step 8: REPO_ROOT が空なら止める（行全体で照合）" grep -qxF -- "$GUARD_REVIEW" "$REVIEW"
check "review-pr Step 8: review-*.diff は bash -c で消す（行全体で照合）" grep -qxF -- "$GLOB_LINE" "$REVIEW"

# no_bare_glob が、正しい形と同じ行に並んだ素の glob を見逃さないこと（検査自体の確認）
W0="$(mktemp -d)"
printf '%s\n' "\`rm -f \"\$REPO_ROOT/docs/temp/review-\"*.diff\` と \`$GLOB_LINE\`" > "$W0/mixed.md"
if no_bare_glob "$W0/mixed.md"; then
    echo "[FAIL] 検査の確認: 正しい形と同じ行の素の glob を検出する"; fail=$((fail + 1))
else
    echo "[PASS] 検査の確認: 正しい形と同じ行の素の glob を検出する"; pass=$((pass + 1))
fi
rm -r "$W0"

# 2) 新しい行の zsh での動作
if ! command -v zsh >/dev/null 2>&1; then
    echo "SKIP: zsh が無いので片付けの行の動作の検査を飛ばす"
else
    W="$(mktemp -d)"
    trap 'rm -rf "$W"' EXIT
    T="$W/docs/temp"
    mkdir -p "$T" "$W/bin"
    # rm の呼び出しを記録してから本物の rm に渡す（REPO_ROOT が空のとき rm を 1 つも実行しないことを確かめるため）
    REAL_RM="$(command -v rm)"
    printf '#!/bin/sh\necho "$*" >> "%s"\nexec "%s" "$@"\n' "$W/rm.log" "$REAL_RM" > "$W/bin/rm"
    chmod +x "$W/bin/rm"
    run_cleanup() { REPO_ROOT="$1" PATH="$W/bin:$PATH" zsh -f -c "$2" 2>"$W/err"; }
    listed() { for f in pr-body.md .pr-body.owner .cost-snapshot .follow.log squash-msg.txt; do : > "$T/$f"; done; : > "$T/keep.md"; }
    none_left() { for f in pr-body.md .pr-body.owner .cost-snapshot .follow.log squash-msg.txt review-1.diff review-browser.diff; do [ ! -e "$T/$f" ] || return 1; done; }
    STEP9="$GUARD_CREATE
$STEP9_RM
$GLOB_LINE"

    # (a) review-*.diff が無いとき
    listed
    run_cleanup "$W" "$STEP9"
    rc=$?
    check "zsh・diff なし: 終了コード 0" test "$rc" -eq 0
    check "zsh・diff なし: no matches found を出さない" bash -c '! grep -q "no matches found" "$1"' _ "$W/err"
    check "zsh・diff なし: 並べたファイルがすべて消える" none_left
    check "zsh・diff なし: ほかのファイルは残る" test -e "$T/keep.md"

    # (b) review-*.diff があるとき
    listed
    : > "$T/review-1.diff"; : > "$T/review-browser.diff"
    run_cleanup "$W" "$STEP9"
    rc=$?
    check "zsh・diff あり: 終了コード 0" test "$rc" -eq 0
    check "zsh・diff あり: 並べたファイルと review-*.diff が消える" none_left
    check "zsh・diff あり: ほかのファイルは残る" test -e "$T/keep.md"

    # (c) 修正前の書き方は zsh・diff なしで巻き添えを出す（この検査が問題を捉えていることの確認）
    listed
    run_cleanup "$W" 'rm -f "$REPO_ROOT/docs/temp/pr-body.md" "$REPO_ROOT/docs/temp/.pr-body.owner" "$REPO_ROOT/docs/temp/review-"*.diff'
    check "対照: 修正前の書き方は zsh・diff なしで pr-body.md を残す" test -e "$T/pr-body.md"

    # (d) REPO_ROOT が空のとき（Bash ツールの呼び出しをまたいだ場合）
    : > "$W/rm.log"
    run_cleanup "" "$STEP9"
    rc=$?
    check "zsh・REPO_ROOT が空: 終了コードが 0 でない" test "$rc" -ne 0
    check "zsh・REPO_ROOT が空: 解決し直す案内を出す" grep -qF 'REPO_ROOT が空' "$W/err"
    check "zsh・REPO_ROOT が空: rm を 1 つも実行しない" test ! -s "$W/rm.log"
fi

echo
echo "passed: $pass, failed: $fail"
[ "$fail" -eq 0 ]
