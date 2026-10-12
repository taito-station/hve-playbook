#!/bin/bash
# Regression tests for hooks/main-commit-guard.py
#
# 実行: bash tests/test_main_commit_guard.sh
#
# main-commit-guard は PreToolUse (matcher: Bash) の hook。main / master 上の
# `git commit` を exit 2 で止める。ブランチは一時ディレクトリに作った実リポジトリで判定する。
# exit 2 = block / exit 0 = allow を検証する。
#
# 各テストは run で包み、PASS / FAIL を数えて最後に終了コードを決める。

HOOK="$(cd "$(dirname "$0")/.." && pwd)/hooks/main-commit-guard.py"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
FAIL=0

run() {
    local name="$1"; shift
    if "$@"; then
        echo "[PASS] $name"
    else
        echo "[FAIL] $name"
        FAIL=$((FAIL + 1))
    fi
}

# 一時リポジトリ。user 設定や init.defaultBranch に左右されないよう -b と -c で固定する
_repo() {
    local dir="$1" branch="$2"
    git init -q -b "$branch" "$dir"
    git -C "$dir" -c user.name=t -c user.email=t@example.com commit -q --allow-empty -m init
}
_repo "$TMP/main" main
_repo "$TMP/master" master
_repo "$TMP/feature" main && git -C "$TMP/feature" switch -q -c feat/x
_repo "$TMP/detached" main && git -C "$TMP/detached" switch -q --detach
git init -q -b main "$TMP/unborn"
_repo "$TMP/with space" main
mkdir -p "$TMP/norepo"

# Bash payload (cwd 付き) を hook に流し、exit code を返す
_rc() {
    local cmd="$1" cwd="$2"
    python3 -c 'import json,sys; print(json.dumps({"hook_event_name":"PreToolUse","tool_name":"Bash","tool_input":{"command":sys.argv[1]},"cwd":sys.argv[2]}))' "$cmd" "$cwd" \
        | python3 "$HOOK" >/dev/null 2>&1
    echo $?
}

blocked() { [ "$(_rc "$1" "$2")" = "2" ]; }
allowed() { [ "$(_rc "$1" "$2")" = "0" ]; }

# ---------- 止める ----------
run "B1: main 上の git commit" blocked 'git commit -m x' "$TMP/main"
run "B2: master 上の git commit" blocked 'git commit -m x' "$TMP/master"
run "B3: unborn の main 上の初回 commit" blocked 'git commit -m init' "$TMP/unborn"
run "B7: git -C で main のリポジトリを指す" blocked "git -C $TMP/main commit -m x" "$TMP/norepo"
run "B9: git -C の空白を含むパス" blocked "git -C \"$TMP/with space\" commit -m x" "$TMP/norepo"
run "B10: git -C の相対パスは cwd 基準" blocked 'git -C main commit -m x' "$TMP"
run "B11: && で連結した commit" blocked 'git add . && git commit -m x' "$TMP/main"
run "B21: 改行で区切った commit" blocked 'git add .
git commit -m x' "$TMP/main"
run "B22: -c のグローバルオプション付き" blocked 'git -c user.name=x commit -m y' "$TMP/main"
run "B23: cd で main のリポジトリに移ってから commit" blocked "cd $TMP/main && git commit -m x" "$TMP/norepo"
run "B24: 環境変数の前置" blocked 'GIT_AUTHOR_NAME=x git commit -m y' "$TMP/main"
run "B27: 行末コメントの次の行の commit" blocked 'git add . # stage
git commit -m x' "$TMP/main"
run "B28: 値を別トークンで取るグローバルオプション" blocked 'git --git-dir .git commit -m x' "$TMP/main"
run "B29: サブシェルの中の commit" blocked '(git commit -m x)' "$TMP/main"
run "B30: then の後の commit" blocked 'if true; then git commit -m x; fi' "$TMP/main"
run "B32: メッセージが # で始まる commit" blocked 'git commit -m "#123 fix"' "$TMP/main"
run "B33: heredoc の本文にアポストロフィ" blocked $'git commit -F - <<\'EOF\'\nfix: don\'t break\nEOF' "$TMP/main"
run "B34: heredoc の本文の via は通さない" blocked $'git commit -F - <<EOF\n# via:main-commit-ok: x\nEOF' "$TMP/main"
run "B35: 単語の途中の # に続く via は通さない" blocked 'git commit -m "#1"# via:main-commit-ok: x' "$TMP/main"
run "B36: if の条件の commit" blocked 'if git commit -m x; then echo ok; fi' "$TMP/main"
run "B37: while の条件の commit" blocked 'while git commit -m x; do :; done' "$TMP/main"
run "B38: command の後の commit" blocked 'command git commit -m x' "$TMP/main"
run "B39: env の後の commit" blocked 'env -u X FOO=1 git commit -m x' "$TMP/main"
run "B40: cd -P で main のリポジトリに移ってから commit" blocked "cd -P $TMP/main && git commit -m x" "$TMP/norepo"
run "B41: cd -- で main のリポジトリに移ってから commit" blocked "cd -- $TMP/main && git commit -m x" "$TMP/norepo"
run "B13: 理由の無い via は通さない" blocked 'git commit -m x # via:main-commit-ok:' "$TMP/main"
run "B14: クォート内の via は通さない" blocked "git commit -m '# via:main-commit-ok: x'" "$TMP/main"

# ---------- 通す ----------
run "B42: heredoc の commit も作業ブランチ上なら通す" allowed $'git commit -F - <<\'EOF\'\nfix: don\'t break\nEOF' "$TMP/feature"
run "B4: 作業ブランチ上の commit" allowed 'git commit -m x' "$TMP/feature"
run "B5: detached HEAD の commit" allowed 'git commit -m x' "$TMP/detached"
run "B6: リポジトリ外" allowed 'git commit -m x' "$TMP/norepo"
run "B8: cwd が main でも -C が作業ブランチを指せば通す" allowed "git -C $TMP/feature commit -m x" "$TMP/main"
run "B25: cd で作業ブランチのリポジトリに移ってから commit" allowed "cd $TMP/feature && git commit -m x" "$TMP/main"
run "B12: 理由付きの via" allowed 'git commit -m x # via:main-commit-ok: 初期化のため' "$TMP/main"
run "B31: 同じ行のコメントの中の commit" allowed 'git status # ok; git commit -m x' "$TMP/main"
run "B15: commit 以外の git" allowed 'git status' "$TMP/main"
run "B16: commit が subcommand でない" allowed 'git log --grep commit' "$TMP/main"
run "B17: git が先頭でないコマンドの引数" allowed 'echo git commit' "$TMP/main"
run "B18: メッセージ内の ; や &&" allowed 'git -C feature commit -m "a; git commit && b"' "$TMP"
run "B20: 存在しない cwd (git が失敗) は通す" allowed 'git commit -m x' "$TMP/nonexistent"

non_bash_allowed() {
    echo '{"tool_name":"Write","tool_input":{"file_path":"x"}}' | python3 "$HOOK" >/dev/null 2>&1
    [ "$?" = "0" ]
}
run "B19: Bash 以外の tool は対象外" non_bash_allowed

broken_json_allowed() {
    echo 'not json' | python3 "$HOOK" >/dev/null 2>&1
    [ "$?" = "0" ]
}
run "B26: 壊れた JSON は通す (fail-open)" broken_json_allowed

if [ "$FAIL" -gt 0 ]; then
    echo "=== $FAIL test(s) FAILED ==="
    exit 1
fi
echo "=== ALL TESTS PASSED ==="
