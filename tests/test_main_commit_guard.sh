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
# 他のリポジトリの判定で例外が出ても、main の判定は続ける
_repo "$TMP/ws/one-level" main && git -C "$TMP/ws/one-level" remote set-url origin https://github.com/foo.git
mainblocked_with_other() { [ "$(_rc_in "$1" "$2" "$3")" = "2" ] && grep -q "main-commit-ok" "$TMP/stderr"; }
run "R115: パスが 1 段の origin で {owner}/{repo} を解決できなくても、main の commit は止める" mainblocked_with_other 'gh api -X POST repos/{owner}/{repo}/issues -f t=x && git commit -m x' "$TMP/ws/one-level" "$TMP/ws/one-level"

# main の commit の判定は、CLAUDE_PROJECT_DIR があっても変わらない
mblocked() { [ "$(_rc_in "$1" "$2" "$3")" = "2" ] && grep -q "main-commit-ok" "$TMP/stderr"; }
run "R50: 起動したリポジトリの main 上の commit は main-commit として止める" mblocked 'git commit -m x' "$TMP/main" "$TMP/main"

if [ "$FAIL" -gt 0 ]; then
    echo "=== $FAIL test(s) FAILED ==="
    exit 1
fi
echo "=== ALL TESTS PASSED ==="
