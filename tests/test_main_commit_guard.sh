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
# 利用者の global / system の git 設定（commit.gpgsign・core.hooksPath 等）とフック環境変数から切り離す（hook の git にも効く）
export GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_NOSYSTEM=1
unset GIT_DIR GIT_WORK_TREE GIT_INDEX_FILE
# 起動したリポジトリの判定（ADR 0033）は CLAUDE_PROJECT_DIR を読む。Claude Code の中で流すと
# hve-playbook を指したままになるので外し、その判定のテスト（下の「起動したリポジトリ以外」）でだけ渡す
unset CLAUDE_PROJECT_DIR
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

# 一時リポジトリ。user 設定や init.defaultBranch に左右されないよう -b と -c で固定する。
# remote の無いリポジトリは判定の対象外なので、origin を設定する（`git remote` は設定を読むだけで通信しない）
_repo() {
    local dir="$1" branch="$2"
    git init -q -b "$branch" "$dir"
    git -C "$dir" remote add origin https://example.invalid/x.git
    git -C "$dir" -c user.name=t -c user.email=t@example.com -c commit.gpgsign=false commit -q --allow-empty -m init
}
_repo "$TMP/main" main
_repo "$TMP/master" master
_repo "$TMP/feature" main && git -C "$TMP/feature" switch -q -c feat/x
_repo "$TMP/detached" main && git -C "$TMP/detached" switch -q --detach
git init -q -b main "$TMP/unborn" && git -C "$TMP/unborn" remote add origin https://example.invalid/x.git
git init -q -b main "$TMP/noremote"
_repo "$TMP/with space" main
_repo "$TMP/tagged" main && git -C "$TMP/tagged" tag main
mkdir -p "$TMP/norepo"

# Bash payload (cwd 付き) を hook に流し、exit code を返す。hook の stderr は $TMP/stderr に残す
_rc() {
    local cmd="$1" cwd="$2"
    python3 -c 'import json,sys; print(json.dumps({"hook_event_name":"PreToolUse","tool_name":"Bash","tool_input":{"command":sys.argv[1]},"cwd":sys.argv[2]}))' "$cmd" "$cwd" \
        | python3 "$HOOK" >/dev/null 2>"$TMP/stderr"
    echo $?
}

blocked() { [ "$(_rc "$1" "$2")" = "2" ]; }
# 通すときは stderr も空（hook が例外で落ちて fail-open した場合は traceback が出るので区別できる）
allowed() { [ "$(_rc "$1" "$2")" = "0" ] && [ ! -s "$TMP/stderr" ]; }

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
run "B43: クォート内の <<EOF の次の行の commit" blocked $'echo "<<EOF"\ngit commit -m x' "$TMP/main"
run "B44: 算術展開の << の次の行の commit" blocked $'echo $((1<<n))\ngit commit -m x' "$TMP/main"
run "B45: <<\\EOF の heredoc の本文にアポストロフィ" blocked $'git commit -F - <<\\EOF\nfix: don\'t break\nEOF' "$TMP/main"
run "B49: env -C で main のリポジトリを指す" blocked "env -C $TMP/main git commit -m x" "$TMP/feature"
run "B51: time -p の後の commit" blocked 'time -p git commit -m x' "$TMP/main"
# 同じコマンド内のブランチの切り替えは追わず、実行前の HEAD で判定する（退避と commit は別の Bash 呼び出しで）
run "B46: git switch -c とつないだ commit も実行前の HEAD (main) で止める" blocked 'git switch -c feat/y && git commit -m x' "$TMP/main"
run "B47: git checkout -b とつないだ commit も実行前の HEAD (main) で止める" blocked 'git checkout -b feat/y && git add . && git commit -m x' "$TMP/main"
run "B52: 同名のタグ main があっても main 上の commit を止める" blocked 'git commit -m x' "$TMP/tagged"
run "B53: 識別子でない終端語の heredoc の本文の via は通さない" blocked $'git commit -F - <<\'END-MSG\'\nfeat: x\n# via:main-commit-ok: x\nEND-MSG' "$TMP/main"
run "B54: ドットを含む終端語の heredoc の本文にアポストロフィ" blocked $'git commit -F - <<EOF.MSG\nfeat: don\'t\nEOF.MSG' "$TMP/main"
run "B55: Claude Code がふだん出す -m \"\$(cat <<'EOF' ...)\" の形（本文に \" を含む）" blocked $'git commit -m "$(cat <<\'EOF\'\nfeat: say "hi\nEOF\n)"' "$TMP/main"
# 分割に失敗した (shlex の例外) ときは、外側の except で traceback を stderr に出して通す (fail-open)
failopen() { [ "$(_rc "$1" "$2")" = "0" ] && grep -q "Traceback" "$TMP/stderr"; }
run "B57: 閉じていないクォートは例外で fail-open（exit 0 と traceback）" failopen 'git commit -m "unterminated' "$TMP/main"
run "B13: 理由の無い via は通さない" blocked 'git commit -m x # via:main-commit-ok:' "$TMP/main"
run "B14: クォート内の via は通さない" blocked "git commit -m '# via:main-commit-ok: x'" "$TMP/main"

# ---------- 通す ----------
run "B42: heredoc の commit も作業ブランチ上なら通す" allowed $'git commit -F - <<\'EOF\'\nfix: don\'t break\nEOF' "$TMP/feature"
run "B56: remote の無いリポジトリ（一時リポジトリ・git init 直後）の main は通す" allowed 'git commit -m init' "$TMP/noremote"
run "B4: 作業ブランチ上の commit" allowed 'git commit -m x' "$TMP/feature"
run "B5: detached HEAD の commit" allowed 'git commit -m x' "$TMP/detached"
run "B6: リポジトリ外" allowed 'git commit -m x' "$TMP/norepo"
run "B8: cwd が main でも -C が作業ブランチを指せば通す" allowed "git -C $TMP/feature commit -m x" "$TMP/main"
run "B25: cd で作業ブランチのリポジトリに移ってから commit" allowed "cd $TMP/feature && git commit -m x" "$TMP/main"
run "B12: 理由付きの via" allowed 'git commit -m x # via:main-commit-ok: 初期化のため' "$TMP/main"
run "B58: 他の via と並べた via" allowed 'git commit -m x # via:create-pr # via:main-commit-ok: 初期化のため' "$TMP/main"
run "B31: 同じ行のコメントの中の commit" allowed 'git status # ok; git commit -m x' "$TMP/main"
run "B15: commit 以外の git" allowed 'git status' "$TMP/main"
run "B16: commit が subcommand でない" allowed 'git log --grep commit' "$TMP/main"
run "B17: git が先頭でないコマンドの引数" allowed 'echo git commit' "$TMP/main"
# cwd は main。クォート内の ; や && で誤って分割すると `git commit` のセグメントが main で判定されて止まる
run "B18: メッセージ内の ; や &&" allowed 'git -C ../feature commit -m "a; git commit && b"' "$TMP/main"
run "B50: env -C で作業ブランチのリポジトリを指す" allowed "env -C $TMP/feature git commit -m x" "$TMP/main"
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

# ---------- 起動したリポジトリ以外への書き込み（ADR 0033） ----------
# 起動したリポジトリ A（origin github.com/me/a）。B は別のリポジトリ（origin github.com/up/b）。
# A の worktree と、ssh 形式の URL で同じ origin を持つ並走 clone は A とみなす。
# main の commit の判定と混ざらないよう、どれも作業ブランチにしておく
_repo_at() {
    local dir="$1" url="$2"
    git init -q -b main "$dir"
    git -C "$dir" remote add origin "$url"
    git -C "$dir" -c user.name=t -c user.email=t@example.com -c commit.gpgsign=false commit -q --allow-empty -m init
    git -C "$dir" switch -q -c feat/x
}
_repo_at "$TMP/ws/a" https://github.com/me/a.git
# a-up: A と同じ origin に、別のリポジトリを指す upstream を足した clone（gh-resolved は無い）
_repo_at "$TMP/ws/a-up" https://github.com/me/a.git
git -C "$TMP/ws/a-up" remote add upstream https://github.com/up/b.git
git -C "$TMP/ws/a" worktree add -q -b feat/wt "$TMP/ws/a-wt"
_repo_at "$TMP/ws/a-clone" git@github.com:Me/A
_repo_at "$TMP/ws/b" https://github.com/up/b.git
git init -q -b main "$TMP/ws/local" && git -C "$TMP/ws/local" switch -q -c feat/x
mkdir -p "$TMP/ws/plain"

# CLAUDE_PROJECT_DIR（起動したディレクトリ）を渡して hook に流す
_rc_in() {
    local cmd="$1" cwd="$2" proj="$3"
    python3 -c 'import json,sys; print(json.dumps({"hook_event_name":"PreToolUse","tool_name":"Bash","tool_input":{"command":sys.argv[1]},"cwd":sys.argv[2]}))' "$cmd" "$cwd" \
        | CLAUDE_PROJECT_DIR="$proj" python3 "$HOOK" >/dev/null 2>"$TMP/stderr"
    echo $?
}
A="$TMP/ws/a"
oblocked() { [ "$(_rc_in "$1" "${2-$A}" "${3-$A}")" = "2" ] && grep -q "other-repo-ok" "$TMP/stderr"; }
oallowed() { [ "$(_rc_in "$1" "${2-$A}" "${3-$A}")" = "0" ] && [ ! -s "$TMP/stderr" ]; }

# 止める
run "R1: cd で別のリポジトリに移って commit" oblocked "cd $TMP/ws/b && git commit -m x"
run "R2: git -C で別のリポジトリに push" oblocked "git -C $TMP/ws/b push -u origin feat/x"
run "R3: gh pr create --repo で別のリポジトリ" oblocked 'gh pr create --repo up/b --title t --body-file f'
run "R4: gh pr create -R（値を別トークン）で別のリポジトリ" oblocked 'gh pr create -R up/b --fill'
run "R5: gh issue create --repo=（= でつなぐ形）で別のリポジトリ" oblocked 'gh issue create --repo=up/b --title t --body x'
run "R6: cd で別のリポジトリに移って gh pr create（--repo なし）" oblocked "cd $TMP/ws/b && gh pr create --fill"
run "R7: gh pr comment に別のリポジトリの URL" oblocked 'gh pr comment https://github.com/up/b/pull/4 --body x'
run "R8: gh api -X POST で別のリポジトリ" oblocked 'gh api -X POST repos/up/b/pulls -f title=t'
run "R9: gh api の -f だけ（POST になる）で別のリポジトリ" oblocked 'gh api repos/up/b/issues/1/comments -f body=x'
run "R10: gh repo fork で別のリポジトリ" oblocked 'gh repo fork up/b --clone=false'
run "R11: gh repo create" oblocked 'gh repo create me/new --private'
run "R12: 起動したリポジトリから別のリポジトリを指す remote へ push" oblocked 'git push upstream feat/x' "$TMP/ws/a-up"
run "R13: 別のリポジトリの URL へ直接 push" oblocked 'git push https://github.com/up/b.git feat/x'
run "R14: 今回の事例（cd で上流の clone に移り、ブランチを切って commit・push・PR）" oblocked "cd $TMP/ws/b && git switch -c fix/y && git commit -m fix && git push -u origin fix/y && gh pr create --fill"
run "R15: 起動したリポジトリの worktree から起動しても別のリポジトリは止める" oblocked "git -C $TMP/ws/b commit -m x" "$TMP/ws/a-wt" "$TMP/ws/a-wt"
run "R16: main-commit-ok の via では通さない" oblocked "git -C $TMP/ws/b commit -m x # via:main-commit-ok: x"
run "R17: 理由の無い via は通さない" oblocked "git -C $TMP/ws/b commit -m x # via:other-repo-ok:"
run "R18: クォート内の via は通さない" oblocked "git -C $TMP/ws/b commit -m '# via:other-repo-ok: x'"

# 通す
run "R30: 起動したリポジトリでの commit・push・gh pr create" oallowed 'git commit -m x && git push -u origin feat/x && gh pr create --fill'
run "R31: --repo が起動したリポジトリ（大文字小文字は無視）" oallowed 'gh pr edit 1 --repo Me/A --body-file f'
run "R32: 起動したリポジトリの worktree での commit・push" oallowed "cd $TMP/ws/a-wt && git commit -m x && git push"
run "R33: 同じ origin（ssh 形式）の並走 clone での commit・push" oallowed "git -C $TMP/ws/a-clone commit -m x && git -C $TMP/ws/a-clone push"
run "R34: 別のリポジトリの読み取り（gh pr view・diff・list・issue view）" oallowed 'gh pr view 4 --repo up/b && gh pr diff 4 -R up/b && gh pr list --repo up/b && gh issue view 1 --repo up/b'
run "R35: gh api の GET（明示・暗黙）" oallowed 'gh api repos/up/b/pulls && gh api -X GET repos/up/b/issues -f state=all'
run "R36: 別のリポジトリでの git の読み取り" oallowed "git -C $TMP/ws/b log -1 && git -C $TMP/ws/b fetch && git -C $TMP/ws/b status"
run "R37: remote の無いリポジトリ（検証用の一時リポジトリ）での commit" oallowed "git -C $TMP/ws/local commit -m x"
run "R38: 理由付きの via" oallowed "git -C $TMP/ws/b commit -m x # via:other-repo-ok: ユーザーが上流への PR を指示"
run "R39: CLAUDE_PROJECT_DIR が無い" oallowed "git -C $TMP/ws/b commit -m x" "$A" ""
run "R40: 起動したディレクトリが git リポジトリでない" oallowed "git -C $TMP/ws/b commit -m x" "$TMP/ws/plain" "$TMP/ws/plain"
run "R41: gh api の {owner}/{repo} は実行するディレクトリで解決（起動したリポジトリ）" oallowed 'gh api -X PATCH repos/{owner}/{repo}/pulls/1 -f body=x'
run "R42: gh の書き込みでないサブコマンド（auth・run view）" oallowed 'gh auth setup-git && gh run view 1 -R up/b'

# エイリアスと書き込みのサブコマンド
run "R60: gh pr new（create のエイリアス）" oblocked 'gh pr new --repo up/b --fill'
run "R61: gh issue new" oblocked 'gh issue new --repo up/b --title t --body x'
run "R62: gh release new" oblocked 'gh release new v1 --repo up/b'
run "R63: gh repo new" oblocked 'gh repo new me/x --private'
run "R64: gh pr lock" oblocked 'gh pr lock 1 --repo up/b'
run "R65: gh issue develop（リモートにブランチを作る）" oblocked 'gh issue develop 1 --repo up/b'
run "R66: gh workflow run" oblocked 'gh workflow run ci.yml --repo up/b'
run "R67: gh secret set" oblocked 'gh secret set X --repo up/b --body y'
run "R68: gh repo deploy-key add" oblocked 'gh repo deploy-key add k.pub --repo up/b'
run "R69: 前置の GH_REPO=" oblocked 'GH_REPO=up/b gh pr create --fill'
run "R70: サブコマンドの前に置いた --repo" oblocked 'gh pr --repo up/b create --fill'
run "R71: gh issue transfer の移す先" oblocked 'gh issue transfer 1 up/b'
run "R72: 引数なしの gh repo fork（新しいリポジトリを作る）" oblocked 'gh repo fork --clone=false'
# git push の宛先（git と同じ決め方）
_repo_at "$TMP/ws/a-pd" https://github.com/me/a.git
git -C "$TMP/ws/a-pd" remote add upstream https://github.com/up/b.git
git -C "$TMP/ws/a-pd" config remote.pushDefault upstream
_repo_at "$TMP/ws/a-trk" https://github.com/me/a.git
git -C "$TMP/ws/a-trk" remote add upstream https://github.com/up/b.git
git -C "$TMP/ws/a-trk" config branch.feat/x.remote upstream
_repo_at "$TMP/ws/a-pu" https://github.com/me/a.git
git -C "$TMP/ws/a-pu" config remote.origin.pushurl https://github.com/up/b.git
run "R73: remote.pushDefault が別のリポジトリを指す素の git push" oblocked 'git push' "$TMP/ws/a-pd"
run "R74: 追跡先が別のリポジトリの素の git push" oblocked 'git push' "$TMP/ws/a-trk"
run "R75: origin の pushurl が別のリポジトリ" oblocked 'git push origin feat/x' "$TMP/ws/a-pu"
run "R76: git push --repo upstream" oblocked 'git push --repo upstream' "$TMP/ws/a-up"
run "R77: git push --repo=upstream" oblocked 'git push --repo=upstream' "$TMP/ws/a-up"
# fork の clone: gh の既定の宛先（gh-resolved=base）は親
_repo_at "$TMP/ws/fork" https://github.com/me/b.git
git -C "$TMP/ws/fork" remote add upstream https://github.com/up/b.git
git -C "$TMP/ws/fork" config remote.upstream.gh-resolved base
run "R78: fork の clone で --repo 無しの gh pr create（親へ向かう）" oblocked 'gh pr create --fill' "$TMP/ws/fork" "$TMP/ws/fork"
# gh api のパス
run "R79: gh api の {owner} だけを置き換えたパス" oblocked 'gh api -X POST repos/{owner}/b/issues -f title=t'
run "R80: gh api の完全な URL" oblocked 'gh api https://api.github.com/repos/up/b/issues -X POST -f title=t'
run "R81: gh api の /user/repos への POST（リポジトリの作成）" oblocked 'gh api -X POST /user/repos -f name=x'
run "R82: gh api の値を詰めた -f（POST になる）" oblocked 'gh api repos/up/b/issues -ftitle=t'

# 通す
run "R90: via を他の via と並べる" oallowed 'gh issue create --repo up/b --title t --body x # via:create-issue # via:other-repo-ok: ユーザーが指示'
run "R91: --help（読み取り）" oallowed 'gh repo create --help && gh pr create -h'
run "R92: 宛先にシェルの変数を含む gh api（値が分からないので判定しない）" oallowed 'gh api -X POST "repos/$OWNER_REPO/issues/1/comments" -f body=x'
run "R93: 宛先にシェルの変数を含む --repo" oallowed 'gh pr edit 1 --repo "$OWNER/$REPO" --body-file f'
run "R94: サブシェルの中の cd はサブシェルの外に効かない" oallowed "(cd $TMP/ws/b && git log -1) && git commit -m x"
run "R95: 書き込みでない gh repo deploy-key list・サブコマンドの前の --repo の読み取り" oallowed 'gh repo deploy-key list --repo up/b && gh pr --repo up/b view 1'
run "R96: 起動したリポジトリに origin が無い" oallowed "git -C $TMP/ws/b commit -m x" "$TMP/ws/local" "$TMP/ws/local"
# ssh の別名ホスト（git@github-work:me/a）の clone: host の無い宛先は起動したリポジトリの host とみなす
_repo_at "$TMP/ws/alias" git@github-work:me/a.git
run "R97: ssh の別名ホストの clone で、自分のリポジトリへの gh の書き込み" oallowed 'gh pr create --repo me/a --fill && gh api -X PATCH repos/me/a/pulls/1 -f body=x' "$TMP/ws/alias" "$TMP/ws/alias"
run "R98: ssh の別名ホストの clone でも、別のリポジトリは止める" oblocked 'gh pr create --repo up/b --fill' "$TMP/ws/alias" "$TMP/ws/alias"
run "R99: fork の clone で --repo に fork 自身を明示" oallowed 'gh pr edit 1 --repo me/b --body-file f' "$TMP/ws/fork" "$TMP/ws/fork"

# 2 巡目の指摘（gh の既定の宛先・位置引数・transfer・help・export・GH_REPO と api・本文の URL・host）
run "R100: upstream を持つ clone（gh-resolved なし）での --repo 無しの gh pr create（gh は upstream へ向かう）" oblocked 'gh pr create --fill' "$TMP/ws/a-up"
run "R101: 別のリポジトリに移って gh repo rename（位置引数は新しい名前）" oblocked "cd $TMP/ws/b && gh repo rename newname --yes"
run "R102: 別のリポジトリに移って gh repo deploy-key add（位置引数は鍵のファイル）" oblocked "cd $TMP/ws/b && gh repo deploy-key add k.pub"
run "R103: gh issue transfer の -R の値を位置引数と数えない" oblocked 'gh issue transfer -R up/b 3 me/a'
run "R104: gh issue transfer の移す元が別のリポジトリ" oblocked "cd $TMP/ws/b && gh issue transfer 3 me/a"
run "R105: 値として書いた --help はヘルプとみなさない" oblocked 'gh pr comment 5 -R up/b --body --help'
run "R106: 同じコマンド内の export GH_REPO" oblocked 'export GH_REPO=up/b; gh pr create --fill'
run "R107: GH_REPO で置き換わる gh api の {owner}/{repo}" oblocked 'GH_REPO=up/b gh api -X POST repos/{owner}/{repo}/issues -f title=t'
git init -q -b main "$TMP/ws/upstream-only" && git -C "$TMP/ws/upstream-only" remote add upstream https://github.com/up/b.git \
    && git -C "$TMP/ws/upstream-only" -c user.name=t -c user.email=t@example.com -c commit.gpgsign=false commit -q --allow-empty -m init \
    && git -C "$TMP/ws/upstream-only" switch -q -c feat/x
run "R108: origin が無く upstream だけを持つリポジトリでの commit" oblocked "git -C $TMP/ws/upstream-only commit -m x"
run "R110: 起動したリポジトリでの gh repo deploy-key add keys/k.pub（位置引数をリポジトリと読まない）" oallowed 'gh repo deploy-key add keys/k.pub'
run "R111: サブシェルの中の export はサブシェルの外に効かない" oallowed '(export GH_REPO=up/b); gh pr create --fill'
run "R112: 本文に書いた URL は宛先と読まない" oallowed 'gh pr comment 1 --body https://github.com/up/b/pull/4'
run "R113: ssh の別名ホストの clone で、github.com の URL を指定した自分のリポジトリへの書き込み" oallowed 'gh pr comment https://github.com/me/a/pull/1 --body x && gh api -X POST https://api.github.com/repos/me/a/issues -f title=t' "$TMP/ws/alias" "$TMP/ws/alias"
run "R114: 別名ホストの並走 clone での commit（起動したリポジトリは github.com）" oallowed "git -C $TMP/ws/alias commit -m x"
# 3 巡目の指摘
# 起動したリポジトリで、作業ブランチの追跡先が upstream（`git switch -c x upstream/main` など）
_repo_at "$TMP/ws/a-trk-up" https://github.com/me/a.git
git -C "$TMP/ws/a-trk-up" remote add upstream https://github.com/up/b.git
git -C "$TMP/ws/a-trk-up" config branch.feat/x.remote upstream
run "R120: 追跡先が upstream でも、起動したリポジトリ（origin が同じ）での commit は通す" oallowed 'git commit -m x' "$TMP/ws/a-trk-up" "$TMP/ws/a-trk-up"
run "R121: 追跡先が upstream の素の git push は止める（外へ出すのは push）" oblocked 'git push' "$TMP/ws/a-trk-up" "$TMP/ws/a-trk-up"
run "R122: 真偽値の短いフラグの後ろの URL（pr merge -d）" oblocked 'gh pr merge -d https://github.com/up/b/pull/3'
run "R123: 真偽値の短いフラグの後ろの URL（pr merge --squash -d）" oblocked 'gh pr merge --squash -d https://github.com/up/b/pull/3'
run "R124: 真偽値の短いフラグの後ろの URL（pr close -d）" oblocked 'gh pr close -d https://github.com/up/b/pull/3'
run "R125: 真偽値の短いフラグの後ろの URL（pr review -a）" oblocked 'gh pr review -a https://github.com/up/b/pull/3'
run "R126: 真偽値の短いフラグの後ろの URL（pr review -c ... -b）" oblocked 'gh pr review -c https://github.com/up/b/pull/3 -b lgtm'
git init -q --bare "$TMP/ws/bare.git"
_repo_at "$TMP/ws/file-remote" "file://$TMP/ws/bare.git"
run "R127: file:// の remote（ローカルの bare リポジトリ）の一時リポジトリでの commit・push" oallowed "git -C $TMP/ws/file-remote commit -m x && git -C $TMP/ws/file-remote push origin feat/x"
run "R128: 引数なしの gh repo sync（親からローカルへ取り込むだけ）" oallowed 'gh repo sync' "$TMP/ws/fork" "$TMP/ws/fork"
run "R129: gh repo sync --source <親> <起動したリポジトリ>" oallowed 'gh repo sync --source up/b me/a'
run "R130: gh repo sync の宛先が別のリポジトリ" oblocked 'gh repo sync up/b --source me/a'
run "R131: 値を詰めた -R（-Rup/b）" oblocked 'gh pr create -Rup/b --fill'
run "R132: 値を詰めた -R のコメント" oblocked 'gh issue comment 3 -Rup/b --body-file f'

# 4 巡目の指摘: コメント本文・説明のフラグの値に書いた URL（サブコマンドごとに本文のフラグが違う）
run "R133: pr close -c の本文の URL は宛先と読まない" oallowed 'gh pr close 5 -c "https://github.com/up/b/pull/7 に置き換え"'
run "R134: label create --description の URL は宛先と読まない" oallowed 'gh label create x --description "https://github.com/up/b/issues/1"'
run "R135: issue close --comment の本文の URL は宛先と読まない" oallowed 'gh issue close 12 --comment "https://github.com/up/b/issues/4 で対応済み"'
run "R136: issue reopen --comment の本文の URL は宛先と読まない" oallowed 'gh issue reopen 3 --comment "https://github.com/up/b/issues/9 が再発"'
run "R137: 本文の URL（起動したリポジトリ）があっても -R の別のリポジトリは止める" oblocked 'gh pr close -c "https://github.com/me/a/pull/5 に置き換え" 4 -R up/b'
run "R138: 本文の URL（起動したリポジトリ）があっても、位置引数の別のリポジトリの URL は止める" oblocked 'gh pr close -c https://github.com/me/a/pull/5 https://github.com/up/b/pull/4'
run "R139: issue close --comment の本文と、位置引数の別のリポジトリの URL" oblocked 'gh issue close --comment "https://github.com/me/a/issues/5 で対応" https://github.com/up/b/issues/4'

# 5 巡目の指摘
run "R140: gh repo delete は位置引数を GH_REPO より先に見る" oblocked 'GH_REPO=me/a gh repo delete up/b --yes'
run "R141: gh repo edit は位置引数を GH_REPO より先に見る" oblocked 'GH_REPO=me/a gh repo edit up/b --description x'
run "R142: gh repo edit の -h は --homepage（ヘルプではない）" oblocked 'gh repo edit up/b -h https://example.com'
run "R143: gh repo create の -h は --homepage（ヘルプではない）" oblocked 'gh repo create up/new --public -h https://example.com'
run "R144: 空の --repo は指定なしと同じ（実行するディレクトリの既定の宛先）" oblocked "cd $TMP/ws/b && gh pr create --repo \"\" --title t --body b"
run "R145: 空の --repo= は指定なしと同じ" oblocked "cd $TMP/ws/b && gh pr merge --repo= 5"
run "R146: 空の -R は指定なしと同じ" oblocked "cd $TMP/ws/b && gh pr create -R \"\" --title t"
run "R147: gh repo edit --help はヘルプ" oallowed 'gh repo edit --help'

# 他のリポジトリの判定で例外が出ても、main の判定は続ける
_repo "$TMP/ws/one-level" main && git -C "$TMP/ws/one-level" remote set-url origin https://github.com/foo.git
mainblocked_with_other() { [ "$(_rc_in "$1" "$2" "$3")" = "2" ] && grep -q "main-commit-ok" "$TMP/stderr"; }
run "R115: パスが 1 段の origin で {owner}/{repo} を解決できなくても、main の commit は止める" mainblocked_with_other 'gh api -X POST repos/{owner}/{repo}/issues -f t=x && git commit -m x' "$TMP/ws/one-level" "$TMP/ws/one-level"

# main の commit の判定は、CLAUDE_PROJECT_DIR があっても変わらない
mblocked() { [ "$(_rc_in "$1" "$2" "$3")" = "2" ] && grep -q "main-commit-ok" "$TMP/stderr"; }
run "R50: 起動したリポジトリの main 上の commit は main-commit として止める" mblocked 'git commit -m x' "$TMP/main" "$TMP/main"

# ---------- primary の checkout での作業ブランチの作成（ADR 0034） ----------
# primary の checkout（git-dir と git-common-dir が同じ作業ツリー）で、新しいブランチを作って切り替える操作を止める。
# 既存ブランチへの切り替え・デフォルトブランチへの切り替え・worktree の中・remote の無いリポジトリ・unborn は止めない
git -C "$TMP/main" worktree add -q -b feat/pw "$TMP/main-wt"
_repo "$TMP/noremote-c" main && git -C "$TMP/noremote-c" remote remove origin && git -C "$TMP/noremote-c" switch -q -c feat/x
pblocked() { [ "$(_rc "$1" "$2")" = "2" ] && grep -q "primary-branch-ok" "$TMP/stderr"; }

# 止める
run "P1: primary で git switch -c" pblocked 'git switch -c feat/y' "$TMP/main"
run "P2: primary で git checkout -b" pblocked 'git checkout -b feat/y' "$TMP/main"
run "P3: git switch -C" pblocked 'git switch -C feat/y' "$TMP/main"
run "P4: git switch --create" pblocked 'git switch --create feat/y' "$TMP/main"
run "P5: git switch --create=（= でつなぐ形）" pblocked 'git switch --create=feat/y' "$TMP/main"
run "P6: git switch -c の値を詰めた形" pblocked 'git switch -cfeat/y' "$TMP/main"
run "P7: git checkout -B と基点" pblocked 'git checkout -B feat/y origin/main' "$TMP/main"
run "P8: git checkout --orphan" pblocked 'git checkout --orphan gh-pages' "$TMP/main"
run "P9: git switch --orphan" pblocked 'git switch --orphan gh-pages' "$TMP/main"
run "P10: git switch --force-create" pblocked 'git switch --force-create feat/y' "$TMP/main"
run "P11: 他のオプションの後ろの -c" pblocked 'git switch -q -c feat/y' "$TMP/main"
run "P12: 短いオプションをまとめた -qb" pblocked 'git checkout -qb feat/y' "$TMP/main"
run "P13: git -C で primary を指す" pblocked "git -C $TMP/main switch -c feat/y" "$TMP/norepo"
run "P14: cd で primary に移ってから" pblocked "cd $TMP/main && git switch -c feat/y" "$TMP/norepo"
run "P15: env -C で primary を指す" pblocked "env -C $TMP/main git switch -c feat/y" "$TMP/norepo"
run "P16: グローバルオプションの後ろの checkout -b" pblocked 'git -c core.x=y checkout -b feat/y' "$TMP/main"
run "P17: primary が作業ブランチにいても止める" pblocked 'git switch -c feat/z' "$TMP/feature"
run "P18: 理由の無い via は通さない" pblocked 'git switch -c feat/y # via:primary-branch-ok:' "$TMP/main"
run "P19: クォート内の via は通さない" pblocked "git switch -c feat/y -- '# via:primary-branch-ok: x'" "$TMP/main"
run "P20: main-commit-ok の via では通さない" pblocked 'git switch -c feat/y # via:main-commit-ok: x' "$TMP/main"

# 通す
pallowed() { [ "$(_rc "$1" "$2")" = "0" ] && [ ! -s "$TMP/stderr" ]; }
run "P30: デフォルトブランチへの切り替え" pallowed 'git switch main && git pull --ff-only' "$TMP/feature"
run "P31: 既存ブランチへの git switch（Q2）" pallowed 'git switch feat/x' "$TMP/main"
run "P32: 既存ブランチへの git checkout（Q2）" pallowed 'git checkout feat/x' "$TMP/main"
run "P33: git checkout -- <path>（ファイルの復元は destructive-guard の担当）" pallowed 'git checkout -- README.md' "$TMP/main"
run "P34: git switch --detach" pallowed 'git switch --detach' "$TMP/main"
run "P35: git worktree add -b（primary の HEAD は動かない）" pallowed 'git worktree add .claude/worktrees/x -b feat/x origin/main' "$TMP/main"
run "P36: gh pr checkout（Q2: 既存ブランチの確認は止めない）" pallowed 'gh pr checkout 12' "$TMP/main"
run "P37: worktree の中での git switch -c" pallowed 'git switch -c feat/y' "$TMP/main-wt"
run "P38: cd で worktree に移ってから git switch -c" pallowed "cd $TMP/main-wt && git switch -c feat/y" "$TMP/main"
run "P39: git -C で worktree を指す" pallowed "git -C $TMP/main-wt checkout -b feat/y" "$TMP/main"
run "P40: remote の無いリポジトリ" pallowed 'git switch -c feat/y' "$TMP/noremote-c"
run "P41: unborn の HEAD（基点が無い）" pallowed 'git switch -c feat/y' "$TMP/unborn"
run "P42: 理由付きの via" pallowed 'git switch -c feat/y # via:primary-branch-ok: ユーザーが primary での作業を指示' "$TMP/main"
run "P43: 他の via と並べた via" pallowed 'git switch -c feat/y # via:create-pr # via:primary-branch-ok: 指示あり' "$TMP/main"
run "P44: commit のメッセージの中の switch -c" pallowed 'git commit -m "git switch -c x"' "$TMP/feature"
run "P45: git branch -c（ブランチの複製。HEAD は動かない）" pallowed 'git branch -c feat/x feat/copy' "$TMP/main"
run "P46: リポジトリ外" pallowed 'git switch -c feat/y' "$TMP/norepo"
run "P47: -- の後ろの -b はパス" pallowed 'git checkout feat/x -- -b' "$TMP/main"
run "P48: 直前のブランチへの切り替え（git switch - / git checkout -）" pallowed 'git switch - && git checkout -' "$TMP/main"

# 止める理由が重なったときは main への commit → 起動したリポジトリ以外 → primary の順（B46・R14 も参照）
run "P50: main 上の switch -c と commit は main-commit として止める" mblocked 'git switch -c feat/y && git commit -m x' "$TMP/main" "$TMP/main"
# 他のリポジトリへの書き込みと primary でのブランチの作成が重なったら、他のリポジトリを示す（ws/b は remote を持つ primary）
other_not_primary() { oblocked "$1" && ! grep -q "primary-branch-ok" "$TMP/stderr"; }
run "P51: 他のリポジトリへの push と primary での switch -c は other-repo として止める" other_not_primary "git -C $TMP/ws/b switch -c fix/y && git -C $TMP/ws/b push -u origin fix/y"

# main への commit の message は、primary なら worktree への退避（stash）、それ以外なら git switch -c を案内する
main_msg_primary() { blocked 'git commit -m x' "$TMP/main" && grep -q "stash push" "$TMP/stderr" && grep -q -- "--no-track" "$TMP/stderr"; }
main_msg_switch() { blocked 'git commit -m x' "$1" && grep -q "git switch -c" "$TMP/stderr" && ! grep -q "stash push" "$TMP/stderr"; }
run "P52: primary の main での commit は stash で worktree へ移す手順を案内する" main_msg_primary
run "P53: unborn の main での commit は git switch -c を案内する" main_msg_switch "$TMP/unborn"

# サブディレクトリで止めたとき、worktree はトップレベルに作るよう案内する
mkdir -p "$TMP/main/sub"
top_msg() { pblocked 'git switch -c feat/y' "$TMP/main/sub" && grep -qF "git -C $(cd "$TMP/main" && pwd -P) worktree add --no-track" "$TMP/stderr"; }
run "P54: サブディレクトリでの switch -c はトップレベルの worktree を案内する" top_msg

# ---------- SessionStart: primary が作業ブランチにいたら警告（ADR 0034） ----------
# 起動したリポジトリ（CLAUDE_PROJECT_DIR、無ければ cwd）の primary の checkout が、remote を持ち、
# デフォルトブランチ以外のブランチにいれば標準出力に警告を出す。常に exit 0
git -C "$TMP/feature" worktree add -q -b feat/fw "$TMP/feature-wt"
_repo "$TMP/dev" main && git -C "$TMP/dev" update-ref refs/remotes/origin/develop HEAD \
    && git -C "$TMP/dev" symbolic-ref refs/remotes/origin/HEAD refs/remotes/origin/develop && git -C "$TMP/dev" switch -q -c develop
_ss() {
    local cwd="$1" proj="$2"
    python3 -c 'import json,sys; print(json.dumps({"hook_event_name":"SessionStart","source":"startup","cwd":sys.argv[1]}))' "$cwd" \
        | CLAUDE_PROJECT_DIR="$proj" python3 "$HOOK" >"$TMP/stdout" 2>"$TMP/stderr"
    echo $?
}
swarned() { [ "$(_ss "$1" "${2-$1}")" = "0" ] && grep -q "$3" "$TMP/stdout" && grep -q "worktree" "$TMP/stdout" && [ ! -s "$TMP/stderr" ]; }
squiet() { [ "$(_ss "$1" "${2-$1}")" = "0" ] && [ ! -s "$TMP/stdout" ] && [ ! -s "$TMP/stderr" ]; }
run "S1: primary が作業ブランチにいれば警告" swarned "$TMP/feature" "$TMP/feature" "feat/x"
run "S2: worktree のセッションでも primary（作業ブランチ）を見て警告" swarned "$TMP/feature-wt" "$TMP/feature-wt" "feat/x"
run "S3: CLAUDE_PROJECT_DIR が無ければ cwd で判定" swarned "$TMP/feature" "" "feat/x"
run "S4: primary がデフォルトブランチ（main）なら何も出さない" squiet "$TMP/main"
run "S5: worktree のセッションで primary が main なら何も出さない" squiet "$TMP/main-wt"
run "S6: origin/HEAD が指すデフォルトブランチ（develop）なら何も出さない" squiet "$TMP/dev"
run "S7: origin/HEAD が無いとき master もデフォルトブランチとみなす" squiet "$TMP/master"
run "S8: remote の無いリポジトリは何も出さない" squiet "$TMP/noremote-c"
run "S9: detached HEAD は何も出さない" squiet "$TMP/detached"
run "S10: リポジトリ外は何も出さない" squiet "$TMP/norepo"
run "S11: CLAUDE_PROJECT_DIR を cwd より優先する" swarned "$TMP/main" "$TMP/feature" "feat/x"
# ブランチ名はリポジトリの外（fork の PR など）から決まりうるので、JSON の文字列としてエスケープして埋め込む
_repo "$TMP/odd" main && git -C "$TMP/odd" switch -q -c "feat/日本\`x"
escaped() { [ "$(_ss "$TMP/odd")" = "0" ] && grep -q '"feat/.u65e5.u672c`x"' "$TMP/stdout" && ! grep -q "日本" "$TMP/stdout"; }
run "S12: ブランチ名の非 ASCII はエスケープして埋め込む" escaped
# ホームの下の primary は ~ で示す（ローカルのユーザー名を文脈に出さない）
# git が返す primary のパスは実パス（macOS では /private/var/...）なので、HOME も実パスにする
tilde() { [ "$(HOME="$(cd "$TMP" && pwd -P)" _ss "$TMP/feature")" = "0" ] && grep -qF '"~/feature"' "$TMP/stdout" && ! grep -q "$(cd "$TMP" && pwd -P)" "$TMP/stdout"; }
run "S13: ホームの下の primary のパスは ~ で示す" tilde

if [ "$FAIL" -gt 0 ]; then
    echo "=== $FAIL test(s) FAILED ==="
    exit 1
fi
echo "=== ALL TESTS PASSED ==="
