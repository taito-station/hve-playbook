#!/usr/bin/env python3
"""
main-commit-guard.py

Claude Code PreToolUse (matcher: Bash) と SessionStart の hook。

main / master 上の `git commit` を止める（ADR 0020。branching の「main で直接 commit しない」）。
Edit / Write は止めない。main 上で作った変更は作業ブランチへ退避してから commit するのが正規の手順
（rules/global/git/branching.md。primary の checkout ではタグ付きの stash で worktree へ移し、worktree の中なら
`git switch -c <branch>`）なので、実害であるコミットの時点で止める。

判定:
- heredoc の本文とコメントを除いてから shlex で分割し、`;` `&&` `||` `|` `&` 括弧・改行で区切ったセグメントごとに見る
- セグメントの先頭（`VAR=val` の前置、`if` `while` `then` `do` `{` などの予約語、`command`、
  `env` とそのオプション・代入を除く）が `git` で、グローバルオプション
  （`-C <path>` / `-c <x=y>` / `--git-dir <path>` など / `--opt[=val]`）の後の subcommand が `commit` なら対象
- 判定するリポジトリ: `git -C <path>`（複数なら順に連結。相対パスは基準のディレクトリから）。
  基準のディレクトリは payload の `cwd` で、同じコマンド内の `cd [オプション] <path>` と `env -C <path>` に追従する
- 実行前の `git symbolic-ref -q HEAD` が `refs/heads/main` / `refs/heads/master` で、remote を持つリポジトリなら止める
  （unborn のブランチも含む）。remote の無いリポジトリ（`git init` 直後や検証用の一時リポジトリ）は PR を作れず、
  main を PR で守る branching の目的が当てはまらないので通す。
  detached HEAD・リポジトリ外・git の失敗は通す。同じコマンド内のブランチの切り替えは追わないので、
  作業ブランチへの退避と commit は別の Bash 呼び出しで実行する

起動したリポジトリ以外への書き込みも止める（ADR 0033。branching の「起動したリポジトリ以外には書き込まない」）:
- 起動したリポジトリは `CLAUDE_PROJECT_DIR` の origin。比べるのはパスではなく、remote の URL などから host を除いた
  `owner/repo`（同じ origin の worktree・並走 clone、ssh の別名ホスト・GHE の clone は同じとみなす）。
  `CLAUDE_PROJECT_DIR` が無い・リポジトリでない・origin が無いときは判定しない
- `git commit`: 判定するリポジトリ（上と同じく `git -C`・`cd`・`env -C` を追う。サブシェルの中の `cd` は
  閉じ括弧で戻す）の origin（無ければ push の宛先の remote、次に最初の remote）が違えば止める。
  remote の無いリポジトリ（検証用の一時リポジトリ）は外に出せないので通す
- `git push`: 宛先の remote の push の URL（位置引数・`--repo`、無ければ git と同じく pushRemote → pushDefault →
  追跡先 → origin）か、URL そのものが違えば止める
- `gh` の書き込み（`GH_WRITES` のサブコマンド。エイリアスの `new` を含む）: 宛先（位置引数の PR・Issue の URL、
  `-R`・`--repo`（空の値は指定なしと同じ）、`gh repo edit` などの位置引数、`GH_REPO`（前置の代入と、
  同じコマンド内の `export`）、
  無ければ gh の既定の宛先）が違えば止める。明示した URL と `--repo` はすべて判定し、どれか 1 つでも違えば止める。
  本文などの値（`--body`、close・reopen の `--comment`、label・repo edit の `--description` など）に書いた URL は
  宛先と読まない。`gh issue transfer` は移す元と移す先の両方を見る。
  gh の既定の宛先は gh と同じく、remote を upstream → github → origin → その他の順に並べて `gh-resolved` の
  付いた remote、無ければ先頭の remote（fork の clone で親へ向かうのを追う）。
  `gh repo create`・`new`・`fork` は新しいリポジトリを作るので常に止める。引数なしの `gh repo sync` は
  親からローカルへ取り込むだけなので通す
- `gh api`: `-X`・`--method` が GET 以外か、本文を送るオプションがあって GET の明示が無いとき、
  パスの `repos/<owner>/<repo>`（完全な URL を含む）が違えば止める。`{owner}`・`{repo}` は `GH_REPO`、無ければ
  gh の既定の宛先で置き換える。`user/repos`・`orgs/<org>/repos` への POST（リポジトリの作成）も止める
- 読み取り（`gh pr view`・`gh api` の GET・`git log` など）と `-h`・`--help` は止めない。Edit・Write も止めない（ADR 0020）
- 宛先にシェルの変数・コマンド置換（`$`・バッククォート）を含むときは、値が分からないので判定しない
- この判定で例外が出ても main への commit の判定は続ける
- 追わないもの: `gh api graphql` の mutation（パスにリポジトリが無い）、`git cherry-pick`・`merge`・`revert`・`am`
  など commit 以外でコミットを作るサブコマンド（外へ出すのは push なので、そこで止まる）、org・アカウントへの
  書き込み（`gh secret set --org`・`gh gist create` など）、`gh` 以外の手段（`curl` など）

primary の checkout での作業ブランチの作成も止める（ADR 0034。branching の「作業開始時の手順」）:
- primary の checkout は、`git rev-parse --path-format=absolute --git-dir --git-common-dir` の 2 つが同じ作業ツリー。
  並走するセッションや `~/.claude` の symlink 先と共有されうるので、デフォルトブランチのまま使い、作業は worktree で始める
- 止めるのは、判定するリポジトリ（main への commit と同じく `git -C`・`cd`・`env -C` を追う）が remote を持つ primary の
  checkout で、HEAD がコミットを指すときの、新しいブランチを作るオプション（`git switch` の `-c`・`-C`・`--create`・
  `--force-create`・`--orphan`、`git checkout` の `-b`・`-B`・`--orphan`。短いオプションをまとめた形・値を詰めた形を含む）だけ。
  既存ブランチへの切り替え（`gh pr checkout`、origin にだけあるブランチの名前での `git switch`、`--track` も）、
  デフォルトブランチへの切り替え、ファイルの復元、`--detach`、`git worktree add`、worktree の中、remote の無いリポジトリ、
  unborn の HEAD（worktree を作る基点が無い）は止めない
- 止める理由が重なったら、main への commit → 起動したリポジトリ以外への書き込み → primary でのブランチの作成の順に示す
- SessionStart では止めない。起動したリポジトリ（`CLAUDE_PROJECT_DIR`、無ければ payload の `cwd`）の primary の checkout
  （`git worktree list --porcelain` の先頭。worktree のセッションでも primary を見る）が remote を持ち、デフォルトブランチ
  （`refs/remotes/origin/HEAD` の先、無ければ main と master）以外のブランチにいれば、標準出力に警告を出す（モデルの文脈に入る）

bypass: コマンド中の本物のシェルコメント（クォートと heredoc の本文の外で、単語の先頭の `#`）に
`# via:main-commit-ok: <理由>` があるとき（理由必須）。via はコマンド中のどのコメントにあっても、コメントの中で
他の via（`# via:create-pr` など）と並べてもよく、そのコマンドのすべての commit を通す。起動したリポジトリ以外への書き込みは、別の
`# via:other-repo-ok: <理由>` で、primary の checkout での作業ブランチの作成は `# via:primary-branch-ok: <理由>` で通す
（ユーザーが指示したときだけ）。via はそれぞれの判定にだけ効き、他の判定は通らない。

限界: シェルの構文を完全には解釈しない best-effort の静的判定で、Claude Code がふだん出す形
（`git commit` / `git switch -c` / `git -C <リテラルのパス>` / `&&`・`;`・改行での連結 / `<<'EOF'` の heredoc）を対象にする。
変数・コマンド置換・前置コマンド・予約語の中の `cd` など、それ以外の形は見逃すことがあり、
分割に失敗したコマンドは通す（fail-open）。逆に、同じコマンド内で作業ブランチへ退避してからの commit
（`git switch -c x && git commit`。切り替えは追わない）と、`git commit --dry-run` / `-h` は main 上では止める
（別の Bash 呼び出しにすれば回復できる）。primary でのブランチの作成はオプションだけで判定するので、
`git branch x` と `git switch x` の 2 手に分けた形、長いオプションの省略形（`--cre`）、git の alias（`git co -b`）は止めない。
submodule の作業ツリーは primary と判定されて止まる（誤操作の防止が目的で、迂回への防御ではない。ADR 0020）。

例外は飲み込み、hook 失敗で Claude Code を止めない（exit 0）。
"""

from __future__ import annotations

import json
import os
import re
import shlex
import subprocess
import sys
import traceback

PROTECTED = ("refs/heads/main", "refs/heads/master")
PUNCT = ";&|()\n"
OPERATORS = set(PUNCT)
ASSIGN_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")
# セグメントの先頭で読み飛ばすシェルの予約語と前置コマンド
LEADING_WORDS = {"if", "elif", "while", "until", "then", "do", "else", "!", "{", "time", "command"}
# 前置語の直後で読み飛ばすオプション（`time -p`）
LEADING_OPTS = {"-p"}
# env のオプションのうち値を別トークンで取るもの
ENV_VALUE_OPTS = {"-u", "--unset", "-C", "--chdir", "-S", "--split-string"}
HEREDOC_RE = re.compile(r"""(?<!<)<<(-?)\s*\\?(?:'([^']+)'|"([^"]+)"|([^\s;&|<>()'"]+))""")
# via はコメントの中のどこにあってもよい（`# via:create-pr # via:other-repo-ok: x` のように並べられる）
VIA_RE = re.compile(r"(?:^|\s)#\s*via:main-commit-ok\s*:\s*\S")
VIA_OTHER_RE = re.compile(r"(?:^|\s)#\s*via:other-repo-ok\s*:\s*\S")
VIA_PRIMARY_RE = re.compile(r"(?:^|\s)#\s*via:primary-branch-ok\s*:\s*\S")
# 新しいブランチを作って切り替えるオプション（短いオプションは文字、長いオプションは `=` の前の名前）
CREATE_SHORT = {"switch": "cC", "checkout": "bB"}
CREATE_LONG = {"switch": {"--create", "--force-create", "--orphan"}, "checkout": {"--orphan"}}
# 値を別トークンで取る git のグローバルオプション（-C は別に扱う）
GIT_VALUE_OPTS = {"-c", "--git-dir", "--work-tree", "--namespace", "--config-env"}
# 値を別トークンで取る git push のオプション（`--repo` は宛先なので別に扱う）
GIT_PUSH_VALUE_OPTS = {"-o", "--push-option", "--receive-pack", "--exec"}
# 書き込みとみなす gh のサブコマンド（エイリアスの `new` を含む）
GH_WRITES = {
    "pr": {"create", "new", "edit", "merge", "comment", "review", "close", "reopen", "ready", "lock", "unlock", "revert", "update-branch"},
    "issue": {"create", "new", "edit", "comment", "close", "reopen", "delete", "transfer", "lock", "unlock", "pin", "unpin", "develop"},
    "label": {"create", "edit", "delete", "clone"},
    "release": {"create", "new", "edit", "delete", "upload", "delete-asset"},
    "repo": {"fork", "create", "new", "edit", "delete", "rename", "archive", "unarchive", "sync", "deploy-key", "autolink"},
    "workflow": {"run", "enable", "disable"},
    "run": {"rerun", "cancel", "delete"},
    "secret": {"set", "delete"},
    "variable": {"set", "delete"},
    "cache": {"delete"},
}
# gh repo deploy-key / autolink のうち書き込みのもの（list などの読み取りは通す）
GH_REPO_NESTED_WRITES = {"add", "create", "delete"}
# 新しいリポジトリを作る操作（fork を含む）。起動したリポジトリとは常に別
GH_REPO_CREATES = {"create", "new", "fork"}
# gh pr / issue の引数に渡す URL（https://github.com/OWNER/REPO/pull/N）
# 末尾まで固定する（「URL で始まる本文」を URL と読まないため）
GH_URL_RE = re.compile(r"^https?://([^/]+)/([^/]+)/([^/]+)/(?:pull|issues)/\d+(?:[/?#]\S*)?$")
# 値を別トークンで取る gh api のオプションと、そのうち本文を送るもの（GET の明示が無ければ POST になる）
GH_API_BODY_OPTS = {"-f", "-F", "--field", "--raw-field", "--input"}
GH_API_VALUE_OPTS = GH_API_BODY_OPTS | {"-H", "--header", "-q", "--jq", "-t", "--template", "--hostname", "--cache", "-p", "--preview"}
# 位置引数にリポジトリを取る gh repo のサブコマンド（rename の新しい名前、deploy-key の鍵のファイルなどは除く）
GH_REPO_POSITIONAL = {"edit", "delete", "archive", "unarchive", "sync"}
# 値を別トークンで取る gh の主なオプション（位置引数を数えるときと、値として書いた `-h` を除くときに使う）
GH_VALUE_FLAGS = {
    "-R", "--repo", "-t", "--title", "-b", "--body", "-F", "--body-file", "-B", "--base", "-H", "--head",
    "-l", "--label", "-a", "--assignee", "-r", "--reviewer", "-m", "--milestone", "-p", "--project",
    "-T", "--template", "-n", "--notes", "--notes-file", "-c", "--color", "-d", "--description",
    "-q", "--jq", "--json", "--name", "--org", "--env", "-s", "--source", "--branch",
}
# 本文などの文字列を値に取るオプション。PR・Issue の URL を探すとき、これらの値は宛先と読まない
GH_TEXT_FLAGS = {"-b", "--body", "-t", "--title", "--subject", "-n", "--notes"}
# サブコマンドによって本文を値に取るオプション（`gh pr review` の `-c` は真偽値なので、ここには入れない）
GH_TEXT_FLAGS_BY_SUB = {
    ("pr", "close"): {"-c", "--comment"},
    ("pr", "reopen"): {"-c", "--comment"},
    ("issue", "close"): {"-c", "--comment"},
    ("issue", "reopen"): {"-c", "--comment"},
    ("label", "create"): {"-d", "--description"},
    ("label", "edit"): {"-d", "--description"},
    ("repo", "edit"): {"-d", "--description"},
}
# 新しいリポジトリの作成の宛先（起動したリポジトリと一致しない値）
NEW_REPO = "<new>"
# サブシェルの括弧を _parse から _blocked へ伝える印（cd をサブシェルの外へ持ち出さないため）
PAREN_MARK = "\x00"


def _strip_heredocs(cmd: str) -> str:
    """heredoc（`<<WORD` / `<<'WORD'` / `<<\\WORD` / `<<-WORD`）の本文の行を除く。本文はシェルのコマンドでは
    ないので、shlex に通すとアポストロフィなどで分割に失敗し、コメントや via の判定も誤る。
    クォート内の `<<EOF` や算術展開の `$((1<<n))` も `<<` に見えるが、終端の行が見つからないので
    heredoc ではなかったとみなし、除いた行を戻す（後ろの行の commit を見逃さないため）。"""
    lines = cmd.split("\n")
    out: list[str] = []
    i = 0
    while i < len(lines):
        out.append(lines[i])
        pending = [(m.group(2) or m.group(3) or m.group(4), m.group(1) == "-") for m in HEREDOC_RE.finditer(lines[i])]
        j = i + 1
        while pending and j < len(lines):
            word, dash = pending[0]
            if (lines[j].lstrip("\t") if dash else lines[j]) == word:
                pending.pop(0)
            j += 1
        if pending:  # 終端の行が無い → heredoc ではなかった
            i += 1
        else:
            i = j
    return "\n".join(out)


def _strip_comments(cmd: str) -> tuple[str, list[str]]:
    """クォートの外で単語の先頭にある `#` から行末までを除き（改行は残す）、除いたコメントも返す。
    shlex のコメント処理は改行まで読み捨てて次の行と 1 つのセグメントにつなげてしまうため、自前で除く。"""
    out = []
    comments = []
    quote = None
    i = 0
    while i < len(cmd):
        c = cmd[i]
        if quote:
            out.append(c)
            if c == "\\" and quote == '"' and i + 1 < len(cmd):
                out.append(cmd[i + 1])
                i += 2
                continue
            if c == quote:
                quote = None
        elif c == "\\" and i + 1 < len(cmd):
            out.append(c + cmd[i + 1])
            i += 2
            continue
        elif c in "'\"":
            quote = c
            out.append(c)
        elif c == "#" and (not out or out[-1] in " \t\n" + PUNCT):
            j = cmd.find("\n", i)
            j = len(cmd) if j < 0 else j
            comments.append(cmd[i:j])
            i = j
            continue
        else:
            out.append(c)
        i += 1
    return "".join(out), comments


def _parse(cmd: str) -> tuple[list[list[str]], list[str]]:
    """コマンドを演算子・括弧・改行で区切ったトークン列のリストと、コメントのリストにする。"""
    cmd, comments = _strip_comments(_strip_heredocs(re.sub(r"\\\n", " ", cmd)))
    lex = shlex.shlex(cmd, posix=True, punctuation_chars=PUNCT)
    lex.whitespace = " \t\r"
    lex.whitespace_split = True
    lex.commenters = ""
    segs: list[list[str]] = [[]]
    for tok in lex:
        if tok and set(tok) <= OPERATORS:
            if "(" in tok or ")" in tok:
                segs.append([PAREN_MARK + tok])
            segs.append([])
        else:
            segs[-1].append(tok)
    return [s for s in segs if s], comments


def _skip_prefix(seg: list[str], base: str) -> tuple[int, str, dict[str, str]]:
    """セグメントの先頭の予約語・代入・前置コマンド・env を読み飛ばし、
    (コマンド名の位置, 実行するディレクトリ, 前置の代入) を返す。"""
    i = 0
    d = base
    env: dict[str, str] = {}
    while i < len(seg):
        t = seg[i]
        if t in LEADING_WORDS or ASSIGN_RE.match(t):
            if ASSIGN_RE.match(t):
                k, _, v = t.partition("=")
                env[k] = v
            i += 1
            while i < len(seg) and seg[i] in LEADING_OPTS:
                i += 1
            continue
        if t == "env":
            i += 1
            while i < len(seg) and seg[i].startswith("-"):
                if seg[i] in ("-C", "--chdir") and i + 1 < len(seg):
                    d = os.path.join(d, os.path.expanduser(seg[i + 1]))
                i += 2 if seg[i] in ENV_VALUE_OPTS else 1
            continue
        break
    return i, d, env


def _git_call(seg: list[str], base: str) -> tuple[str, str, list[str]] | None:
    """seg が git の呼び出しなら (判定するディレクトリ, subcommand, subcommand の後の引数) を、そうでなければ None を返す。"""
    i, d, _ = _skip_prefix(seg, base)
    if i >= len(seg) or seg[i] != "git":
        return None
    i += 1
    while i < len(seg):
        t = seg[i]
        if t == "-C" and i + 1 < len(seg):
            d = os.path.join(d, os.path.expanduser(seg[i + 1]))
            i += 2
            continue
        if t in GIT_VALUE_OPTS:
            i += 2
            continue
        if t.startswith("-"):
            i += 1
            continue
        break
    if i >= len(seg):
        return None
    return d, seg[i], seg[i + 1 :]


def _gh_call(seg: list[str], base: str) -> tuple[str, list[str], dict[str, str]] | None:
    """seg が gh の呼び出しなら (実行するディレクトリ, gh の後の引数, 前置の代入) を、そうでなければ None を返す。"""
    i, d, env = _skip_prefix(seg, base)
    if i >= len(seg) or seg[i] != "gh":
        return None
    return d, seg[i + 1 :], env


def _dynamic(s: str) -> bool:
    """シェルの変数・コマンド置換を含むか。値が静的に分からないので判定しない（fail-open）。"""
    return "$" in s or "`" in s


def _norm_url(url: str) -> str | None:
    """remote の URL を `owner/repo`（host を除いたパス。小文字、`.git` なし）にそろえる。
    host は比べない（ssh の別名ホスト・GHE でも同じ owner/repo は同じリポジトリとみなす）。形が分からなければ None。"""
    u = url.strip()
    if _dynamic(u) or u.lower().startswith("file://"):
        return None  # file:// はローカルのパスと同じ扱い（検証用の一時リポジトリの bare など）
    m = re.match(r"^[A-Za-z][A-Za-z0-9+.-]*://(?:[^@/]+@)?[^/:]+(?::\d+)?/(.+?)(?:\.git)?/?$", u)
    if m is None and "://" not in u and not u.startswith(("/", ".", "~")):
        m = re.match(r"^(?:[^@/]+@)?[^/:]+:(.+?)(?:\.git)?/?$", u)  # scp 形式（git@host:owner/repo）
    if m is None or "/" not in m.group(1):
        return None
    return m.group(1).lower()


def _git_out(d: str, *args: str) -> str | None:
    try:
        r = subprocess.run(["git", "-C", d, *args], capture_output=True, text=True, timeout=5)
    except (OSError, subprocess.SubprocessError):
        return None
    if r.returncode != 0:
        return None
    return r.stdout.strip() or None


def _remote_url(d: str, name: str, push: bool = False) -> str | None:
    url = _git_out(d, "remote", "get-url", *(["--push"] if push else []), name)
    return _norm_url(url) if url else None


def _origin(d: str) -> str | None:
    """d のリポジトリの origin を正規化したもの。リポジトリでない・origin が無い・git の失敗は None（判定しない側）。"""
    return _remote_url(d, "origin")


def _gh_repo(value: str) -> str | None:
    """`--repo`・`GH_REPO` などの値（OWNER/REPO・HOST/OWNER/REPO・URL）を `owner/repo` にそろえる。"""
    if _dynamic(value):
        return None
    if "://" in value:
        return _norm_url(value)
    parts = value.strip("/").split("/")
    if len(parts) == 2:
        return "/".join(parts).lower()
    if len(parts) == 3:
        return "/".join(parts[1:]).lower()
    return None


def _push_remote(d: str) -> str:
    """remote の引数が無い `git push` の宛先の remote（git と同じく pushRemote → pushDefault → 追跡先 → origin）。"""
    b = _git_out(d, "symbolic-ref", "--short", "-q", "HEAD")
    keys = [f"branch.{b}.pushRemote", "remote.pushDefault", f"branch.{b}.remote"] if b else ["remote.pushDefault"]
    for key in keys:
        v = _git_out(d, "config", "--get", key)
        if v and v != ".":
            return v
    return "origin"


def _push_target(args: list[str], d: str) -> str | None:
    """`git push` の宛先のリポジトリ（remote の push の URL か、URL そのもの）。"""
    positional = None
    repo_opt = None
    i = 0
    while i < len(args):
        t = args[i]
        if t == "--repo" and i + 1 < len(args):
            repo_opt = args[i + 1]
            i += 2
            continue
        if t.startswith("--repo="):
            repo_opt = t.split("=", 1)[1]
        elif t in GIT_PUSH_VALUE_OPTS:
            i += 2
            continue
        elif not t.startswith("-"):
            positional = t
            break
        i += 1
    # 位置引数の remote は --repo より優先する（git push の仕様）
    remote = positional or repo_opt or _push_remote(d)
    if _dynamic(remote):
        return None
    return _remote_url(d, remote, push=True) or _norm_url(remote)


def _commit_target(d: str) -> str | None:
    """`git commit` を判定するリポジトリ。origin、無ければ push の宛先の remote、次に最初の remote。
    origin を先に見るのは、起動したリポジトリで追跡先を upstream にした作業ブランチ（`git switch -c x upstream/main`）
    の commit を止めないため（外へ出すのは push で、そこで判定する）。
    remote の無いリポジトリ（検証用の一時リポジトリ）は外に出せないので None（通す）。"""
    t = _origin(d) or _remote_url(d, _push_remote(d))
    if t:
        return t
    for name in (_git_out(d, "remote") or "").splitlines():
        t = _remote_url(d, name)
        if t:
            return t
    return None


def _gh_default(d: str) -> str | None:
    """`--repo` の無い gh の宛先（gh の既定の宛先）。gh と同じく remote を upstream → github → origin → その他の順に
    並べ、`remote.<name>.gh-resolved`（`gh repo clone`・`gh repo fork --clone`・`gh repo set-default` が付ける）が
    あればそれを、無ければ先頭の remote を使う（端末に問い合わせられない Bash では、gh は先頭を選ぶ）。"""
    names = (_git_out(d, "remote") or "").splitlines()
    score = {"upstream": 3, "github": 2, "origin": 1}
    names.sort(key=lambda n: -score.get(n, 0))
    for n in names:
        val = _git_out(d, "config", "--get", f"remote.{n}.gh-resolved")
        if val == "base":
            return _remote_url(d, n)
        if val and "/" in val:
            return _gh_repo(val)
    for n in names:
        t = _remote_url(d, n)
        if t:
            return t
    return None


def _gh_positionals(args: list[str], extra_value_flags: set[str] = frozenset()) -> list[str]:
    """gh のサブコマンドの後の位置引数（値を取るオプションの値を除く）。"""
    pos = []
    i = 0
    while i < len(args):
        t = args[i]
        if t in GH_VALUE_FLAGS or t in extra_value_flags:
            i += 2
            continue
        if not t.startswith("-"):
            pos.append(t)
        i += 1
    return pos


def _gh_api_target(args: list[str], d: str, env: dict[str, str]) -> tuple[list[str], str] | None:
    """`gh api` が書き込みなら ([宛先], 操作の表示) を、読み取り・リポジトリの外のパス（graphql を含む）なら None を返す。"""
    method = None
    body = False
    path = None
    i = 0
    while i < len(args):
        t = args[i]
        if t in ("-X", "--method") and i + 1 < len(args):
            method = args[i + 1]
            i += 2
            continue
        if t.startswith("--method="):
            method = t.split("=", 1)[1]
        elif t.startswith("-X") and len(t) > 2:
            method = t[2:]
        elif t in GH_API_BODY_OPTS:
            body = True
            i += 2
            continue
        elif t.startswith(("--field=", "--raw-field=", "--input=")) or (t[:2] in ("-f", "-F") and len(t) > 2):
            body = True  # `-fbody=x` のように値を詰めた形を含む
        elif t in GH_API_VALUE_OPTS:
            i += 2
            continue
        elif not t.startswith("-") and path is None:
            path = t
        i += 1
    method = (method or ("POST" if body else "GET")).upper()
    if method == "GET" or path is None or _dynamic(path):
        return None
    op = f"gh api {method} {path}"
    m = re.match(r"^https?://[^/]+/(?:api/v3/)?(.*)$", path)
    if m:
        path = m.group(1)
    p = path.lstrip("/")
    if re.match(r"^(?:user|orgs/[^/]+)/repos/?$", p):
        return ([NEW_REPO], op) if method == "POST" else None
    m = re.match(r"^repos/([^/]+)/([^/?]+)", p)
    if m is None:
        return None
    owner, repo = m.group(1), m.group(2)
    if owner == "{owner}" or repo == "{repo}":
        # プレースホルダは GH_REPO、無ければ gh の既定の宛先で、owner と repo を別々に置き換える
        dflt = _gh_repo(env["GH_REPO"]) if env.get("GH_REPO") else _gh_default(d)
        if dflt is None or dflt.count("/") != 1:
            return None
        d_owner, d_repo = dflt.split("/")
        owner = d_owner if owner == "{owner}" else owner
        repo = d_repo if repo == "{repo}" else repo
    return [f"{owner}/{repo}".lower()], op


def _gh_write_target(args: list[str], d: str, env: dict[str, str]) -> tuple[list[str], str] | None:
    """gh の書き込みなら ([宛先], 操作の表示) を（新しいリポジトリの作成は NEW_REPO）、読み取りなら None を返す。"""
    if not args:
        return None
    # ヘルプ（値を取るオプションの値として書いた `-h` は除く）は読み取り。
    # `gh repo edit`・`create`・`new` の `-h` は `--homepage <URL>` なので、そこでは `--help` だけをヘルプとみなす
    homepage = args[0] == "repo" and next((a for a in args[1:] if not a.startswith("-")), None) in ("edit", "create", "new")
    helps = ("--help",) if homepage else ("-h", "--help")
    if any(t in helps and (j == 0 or args[j - 1] not in GH_VALUE_FLAGS) for j, t in enumerate(args)):
        return None
    if args[0] == "api":
        return _gh_api_target(args[1:], d, env)
    group = args[0]
    repo = None
    # サブコマンドの前に置いたフラグ（`gh pr --repo X create`）を読み飛ばす
    i = 1
    while i < len(args) and args[i].startswith("-"):
        if args[i] in ("-R", "--repo") and i + 1 < len(args):
            repo = args[i + 1]
            i += 2
            continue
        if args[i].startswith("--repo="):
            repo = args[i].split("=", 1)[1]
        elif args[i].startswith("-R") and len(args[i]) > 2:
            repo = args[i][2:].lstrip("=")  # 値を詰めた形（`-Rowner/repo`）
        i += 1
    if i >= len(args) or args[i] not in GH_WRITES.get(group, ()):
        return None
    sub, rest = args[i], args[i + 1 :]
    op = f"gh {group} {sub}"
    if group == "repo" and sub in ("deploy-key", "autolink"):
        if not rest or rest[0] not in GH_REPO_NESTED_WRITES:
            return None
        op += f" {rest[0]}"
        rest = rest[1:]
    if group == "repo" and sub in GH_REPO_CREATES:
        return [NEW_REPO], op
    for j, t in enumerate(rest):
        if t in ("-R", "--repo") and j + 1 < len(rest):
            repo = rest[j + 1]
        elif t.startswith("--repo="):
            repo = t.split("=", 1)[1]
        elif t.startswith("-R") and len(t) > 2:
            repo = t[2:].lstrip("=")
    if repo == "":
        repo = None  # 空の `--repo ""`・`--repo=` は指定なしと同じ（実行するディレクトリの既定の宛先）
    pos = _gh_positionals(rest, {"-h"} if homepage else set())
    if group == "repo" and sub == "sync" and not pos:
        return None  # 引数なしの sync は親からローカルへ取り込むだけで、remote に書き込まない
    # 操作するリポジトリ: PR・Issue の URL と --repo（明示されたものはすべて判定する。どれか 1 つでも違えば止める）、
    # 無ければ gh repo の位置引数 → GH_REPO → gh の既定の宛先（gh repo の位置引数は GH_REPO より優先する。gh と同じ）。
    # URL は本文などの値（GH_TEXT_FLAGS とサブコマンドごとの本文のフラグの直後）を除いたトークンから探す。
    # 短いフラグはサブコマンドで値を取るか真偽値かが変わる（`pr merge -d` は真偽値）ので、位置引数に限らずに探す
    text_flags = GH_TEXT_FLAGS | GH_TEXT_FLAGS_BY_SUB.get((group, sub), set())
    targets = [
        f"{m.group(2)}/{m.group(3)}".lower()  # group(1) は host（比べない）
        for j, t in enumerate(rest)
        if not (j and rest[j - 1] in text_flags) and (m := GH_URL_RE.match(t))
    ]
    if repo is not None and _gh_repo(repo):
        targets.append(_gh_repo(repo))
    if not targets and repo is None:
        target = None
        repo_pos = group == "repo" and sub in GH_REPO_POSITIONAL and bool(pos)
        if repo_pos:
            target = _gh_repo(pos[0])
        elif env.get("GH_REPO"):
            target = _gh_repo(env["GH_REPO"])
        if target is None and not repo_pos and not env.get("GH_REPO"):
            target = _gh_default(d)
        if target:
            targets.append(target)
    if group == "issue" and sub == "transfer" and len(pos) >= 2:
        # 移す元（上の target）から Issue を消し、移す先に作る。両方を判定する
        dest = _gh_repo(pos[1])
        if dest:
            targets.append(dest)
    return (targets, op) if targets else None


def _branch(d: str) -> str | None:
    try:
        r = subprocess.run(
            ["git", "-C", d, "symbolic-ref", "-q", "HEAD"],
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if r.returncode != 0:
        return None
    return r.stdout.strip() or None


def _has_remote(d: str) -> bool:
    """remote を 1 つ以上持つか。git が失敗したときは False（通す側）。"""
    try:
        r = subprocess.run(["git", "-C", d, "remote"], capture_output=True, text=True, timeout=5)
    except (OSError, subprocess.SubprocessError):
        return False
    return r.returncode == 0 and bool(r.stdout.strip())


def _creates_branch(sub: str, args: list[str]) -> bool:
    """`git switch` / `git checkout` の引数が新しいブランチを作るオプションを含むか。`--` の後ろはパスなので見ない。
    switch・checkout の短いオプションで値を取るのは、作成のもの（-c・-C・-b・-B）のほかは checkout の -U（数値）だけで、
    その値は作成の文字を含まない。そのため、まとめた形（`-qb`）や値を詰めた形（`-cfeat/x`）も、文字のどれかが作成の
    オプションなら作成とみなす。長いオプションの省略形（`--cre`）と alias（`git co -b`）は追わない。"""
    if sub not in CREATE_SHORT:
        return False
    for a in args:
        if a == "--":
            return False
        if a.startswith("--"):
            if a.split("=", 1)[0] in CREATE_LONG[sub]:
                return True
        elif a.startswith("-") and any(c in CREATE_SHORT[sub] for c in a[1:]):
            return True
    return False


def _is_primary(d: str) -> bool:
    """d が primary の checkout（git-dir と git-common-dir が同じ作業ツリー）か。git が失敗したときは False（通す側）。"""
    out = _git_out(d, "rev-parse", "--path-format=absolute", "--git-dir", "--git-common-dir")
    if not out:
        return False
    dirs = out.splitlines()
    return len(dirs) == 2 and dirs[0] == dirs[1]


def _has_commit(d: str) -> bool:
    """HEAD がコミットを指すか（unborn でないか）。"""
    return _git_out(d, "rev-parse", "-q", "--verify", "HEAD") is not None


def _guarded_primary(d: str) -> bool:
    """d が remote を持つリポジトリの primary の checkout で、HEAD がコミットを指すか。
    remote の無いリポジトリ（一時リポジトリ）と unborn（worktree を作る基点が無い）は対象外。"""
    return _is_primary(d) and _has_remote(d) and _has_commit(d)


def _toplevel(d: str) -> str:
    """d のリポジトリのトップレベル（worktree の置き場所の基準）。求められなければ d のまま。"""
    return _git_out(d, "rev-parse", "--show-toplevel") or d


def _home_tilde(path: str) -> str:
    """ホームの下のパスを ~ で始まる形にする。"""
    home = os.path.expanduser("~")
    return "~" + path[len(home) :] if home and home != "/" and (path == home or path.startswith(home + "/")) else path


def _default_branches(d: str) -> set[str]:
    """デフォルトブランチの名前。`refs/remotes/origin/HEAD` があればその先、無ければ main と master。"""
    ref = _git_out(d, "symbolic-ref", "-q", "--short", "refs/remotes/origin/HEAD")
    if ref and ref.startswith("origin/"):
        return {ref[len("origin/") :]}
    return {"main", "master"}


def _session_start_warning(payload: dict) -> str | None:
    """起動したリポジトリの primary の checkout が、デフォルトブランチ以外のブランチにいれば警告文を返す。
    worktree のセッションでも primary を見る（`git worktree list --porcelain` の先頭が primary）。"""
    d = os.environ.get("CLAUDE_PROJECT_DIR") or payload.get("cwd") or os.getcwd()
    if not isinstance(d, str):
        return None
    out = _git_out(d, "worktree", "list", "--porcelain")
    if not out:
        return None
    first = out.split("\n\n", 1)[0].splitlines()
    primary = next((l[len("worktree ") :] for l in first if l.startswith("worktree ")), None)
    branch = next((l[len("branch refs/heads/") :] for l in first if l.startswith("branch refs/heads/")), None)
    if primary is None or branch is None or not _has_remote(primary):
        return None  # bare・detached・remote の無いリポジトリは対象外
    defaults = _default_branches(primary)
    if branch in defaults:
        return None
    # ブランチ名は fork の PR などリポジトリの外から決まりうるので、モデルの文脈に入れる前に
    # JSON の文字列として埋め込む（非 ASCII・引用符・バックスラッシュ・制御文字をエスケープし、長さも抑える）。
    # パスはホームを ~ に置き換える（ローカルのユーザー名を文脈に出さない）
    shown = json.dumps(branch[:100] + ("…" if len(branch) > 100 else ""))
    return (
        "[main-commit-guard] primary の checkout（" + json.dumps(_home_tilde(primary), ensure_ascii=False) + "）が、デフォルトブランチ（"
        + " / ".join(sorted(defaults)) + "）ではなく作業ブランチ " + shown + " にある。"
        "並走するセッションの作業かもしれないので、primary のブランチを自分の判断で戻したり切り替えたりしない。"
        "作業は worktree で行う（rules/global/git/branching.md の「作業開始時の手順」）。"
        "戻す必要があれば、他のセッションが使っていないかをユーザーに確かめてから戻す。"
    )


def _other_hit(seg: list[str], base: str, env: dict[str, str]) -> tuple[list[str], str] | None:
    """seg が書き込みなら ([宛先], 操作の表示) を返す。例外は飲み込んで None（main の判定を巻き込まない）。"""
    try:
        call = _git_call(seg, base)
        if call is not None:
            d, sub, rest = call
            if sub == "commit":
                t = _commit_target(d)
            elif sub == "push":
                t = _push_target(rest, d)
            else:
                return None
            return ([t], f"git {sub}") if t else None
        gh = _gh_call(seg, base)
        if gh is not None:
            return _gh_write_target(gh[1], gh[0], {**env, **gh[2]})
    except Exception:
        traceback.print_exc()
    return None


def _blocked(
    segs: list[list[str]], cwd: str, proj: str | None
) -> tuple[tuple[str, str] | None, tuple[str, str, str] | None, str | None]:
    """(main への commit, 起動したリポジトリ以外への書き込み, primary の checkout でのブランチの作成) をそれぞれ返す。
    1 つ目は (ディレクトリ, ブランチ)、2 つ目は (操作, 宛先のリポジトリ, 起動したリポジトリ)、3 つ目は primary のディレクトリ。
    起動したリポジトリ（proj の origin）は、書き込みの宛先が分かったときに 1 回だけ求める。
    proj が無い・origin が無ければ後者は判定しない。"""
    base = cwd
    env: dict[str, str] = {}  # 同じコマンド内の `export VAR=val`
    stack: list[tuple[str, dict[str, str]]] = []
    main_hit = None
    other_hit = None
    primary_hit = None
    check_other = bool(proj)
    launch_cache: list[str | None] = []

    def launch_repo() -> str | None:
        if not launch_cache:
            launch_cache.append(_origin(proj) if proj else None)
        return launch_cache[0]

    for seg in segs:
        if seg[0].startswith(PAREN_MARK):
            # サブシェルの中の cd・export は、閉じ括弧で元に戻す
            for ch in seg[0][len(PAREN_MARK) :]:
                if ch == "(":
                    stack.append((base, dict(env)))
                elif ch == ")" and stack:
                    base, env = stack.pop()
            continue
        if seg[0] == "cd":
            args = [a for a in seg[1:] if not a.startswith("-")]
            if len(args) == 1:
                base = os.path.join(base, os.path.expanduser(args[0]))
            continue
        if seg[0] == "export":
            for a in seg[1:]:
                if ASSIGN_RE.match(a):
                    k, _, v = a.partition("=")
                    env[k] = v
            continue
        call = _git_call(seg, base)
        if call is not None and call[1] == "commit" and main_hit is None:
            b = _branch(call[0])
            if b in PROTECTED and _has_remote(call[0]):
                main_hit = (call[0], b)
        if call is not None and primary_hit is None and _creates_branch(call[1], call[2]) and _guarded_primary(call[0]):
            primary_hit = _toplevel(call[0])
        if not check_other or other_hit is not None:
            continue
        hit = _other_hit(seg, base, env)
        if hit is None:
            continue
        launch = launch_repo()
        if launch is None:
            check_other = False  # 起動したリポジトリが分からないので、以降も判定しない
            continue
        bad = next((t for t in hit[0] if t != launch), None)
        if bad is not None:
            other_hit = (hit[1], bad, launch)
    return main_hit, other_hit, primary_hit


def main() -> int:
    try:
        try:
            payload = json.load(sys.stdin)
        except (json.JSONDecodeError, ValueError, OSError):
            return 0
        if not isinstance(payload, dict):
            return 0
        if payload.get("hook_event_name") == "SessionStart":
            # 止めない。標準出力はモデルの文脈に入る
            warning = _session_start_warning(payload)
            if warning:
                print(warning)
            return 0
        if payload.get("tool_name") != "Bash":
            return 0
        ti = payload.get("tool_input") or {}
        cmd = ti.get("command", "") if isinstance(ti, dict) else ""
        if not isinstance(cmd, str) or not ("commit" in cmd or "push" in cmd or "switch" in cmd or "checkout" in cmd or re.search(r"\bgh\b", cmd)):
            return 0
        cwd = payload.get("cwd")
        if not isinstance(cwd, str) or not cwd:
            cwd = os.getcwd()
        segs, comments = _parse(cmd)
        main_hit, other_hit, primary_hit = _blocked(segs, cwd, os.environ.get("CLAUDE_PROJECT_DIR"))

        # bypass: 分割のときに除いた本物のコメントの中だけで via を探す（判定ごとに別の via）
        # 止める理由が重なったら、main への commit → 起動したリポジトリ以外への書き込み → primary でのブランチの作成の順に示す
        if main_hit is not None and not any(VIA_RE.search(c) for c in comments):
            d, b = main_hit
            b = b[len("refs/heads/") :]
            if _guarded_primary(d):
                top = shlex.quote(_toplevel(d))
                how = (
                    "primary の checkout なので、rules/global/git/branching.md の「作業開始時の手順」の退避手順で、"
                    "自分の未コミットの変更だけを worktree へ移してから commit する（自分が作ったと言い切れない変更は移さずにユーザーに確認する。"
                    "`git stash push -u -m <固有のタグ> -- <自分が変えたパス>` → "
                    f"`git -C {top} worktree add --no-track -b <type>/<short-kebab-description> .claude/worktrees/<名前> origin/<default>` → "
                    "worktree で `git stash apply <その stash の SHA>` → 自分の stash を drop。素の `git stash pop` は使わない）。\n"
                )
            else:
                how = (
                    "`git switch -c <type>/<short-kebab-description>` で作業ブランチへ退避してから commit する"
                    "（未コミットの変更はそのまま持ち越せる）。退避と commit は別の Bash 呼び出しで実行する"
                    "（この hook は実行前の HEAD で判定するので、1 つのコマンドにつなぐと止まる）。\n"
                )
            print(
                "BLOCKED by main-commit-guard hook.\n"
                f"reason: `{b}` ブランチ上での git commit（{shlex.quote(d)}）。main / master へは直接 commit しない。\n"
                + how +
                "ユーザーが main への commit を明示的に指示した場合のみ、コマンド中のコメントで "
                "`# via:main-commit-ok: <理由>` を付ける（理由は非空必須）。",
                file=sys.stderr,
            )
            return 2
        if other_hit is not None and not any(VIA_OTHER_RE.search(c) for c in comments):
            op, target, launch = other_hit
            shown = "新しいリポジトリの作成（fork を含む）" if target == NEW_REPO else target
            print(
                "BLOCKED by main-commit-guard hook.\n"
                f"reason: 起動したリポジトリ（{launch}）以外への書き込み: `{op}` → {shown}。\n"
                "起動したリポジトリ以外（上流・vendor 元・依存先・別のプロジェクト）には、ユーザーの明示的な指示がない限り"
                "書き込まない（rules/global/git/branching.md の「起動したリポジトリ以外には書き込まない」、ADR 0033）。"
                "直すべき点を見つけたなら、自分で PR・Issue・push をせず、ユーザーに報告して判断を委ねる。\n"
                "ユーザーがこのリポジトリへの書き込みを明示的に指示した場合のみ、コマンド中のコメントで "
                "`# via:other-repo-ok: <理由>` を付ける（理由は非空必須）。",
                file=sys.stderr,
            )
            return 2
        if primary_hit is not None and not any(VIA_PRIMARY_RE.search(c) for c in comments):
            print(
                "BLOCKED by main-commit-guard hook.\n"
                f"reason: primary の checkout（{shlex.quote(primary_hit)}）で新しいブランチを作って切り替えようとしている。"
                "primary は並走するセッションと共有されうるので、デフォルトブランチのまま使い、"
                "作業は worktree で始める（rules/global/git/branching.md の「作業開始時の手順」、ADR 0034）。\n"
                f"`git -C {shlex.quote(primary_hit)} worktree add --no-track -b <type>/<short-kebab-description> .claude/worktrees/<名前> origin/<default>` "
                "で worktree を作り、EnterWorktree の `path` にそのパスを渡して移る。"
                "main 上に未コミットの変更があれば、branching.md の退避手順（タグ付きの stash → worktree で SHA を指定して apply）で移す。"
                "`git branch <名前>` と `git switch <名前>` の 2 手に分けて回避しない。\n"
                "ユーザーが primary での作業を明示的に指示した場合のみ、コマンド中のコメントで "
                "`# via:primary-branch-ok: <理由>` を付ける（理由は非空必須）。",
                file=sys.stderr,
            )
            return 2
        return 0
    except BaseException:
        # hook 失敗で Claude Code を止めない。exit 0 の stderr は動作に影響しないので、原因を追えるよう残す
        traceback.print_exc()
        return 0


if __name__ == "__main__":
    sys.exit(main())
