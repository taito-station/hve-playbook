#!/usr/bin/env python3
"""
main-commit-guard.py

Claude Code PreToolUse (matcher: Bash) hook。

main / master 上の `git commit` を止める（ADR 0020。branching の「main で直接 commit しない」）。
Edit / Write は止めない。main 上で作った変更は `git switch -c <branch>` で作業ブランチへ
退避してから commit するのが正規の手順（rules/global/git/branching.md）なので、
実害であるコミットの時点で止める。

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
  作業ブランチへの退避（`git switch -c`）と commit は別の Bash 呼び出しで実行する

起動したリポジトリ以外への書き込みも止める（ADR 0033。branching の「起動したリポジトリ以外には書き込まない」）:
- 起動したリポジトリは `CLAUDE_PROJECT_DIR` の origin。比べるのはパスではなく origin の URL を
  `host/owner/repo` にそろえたもの（同じ origin の worktree・並走 clone は同じとみなす）。
  `CLAUDE_PROJECT_DIR` が無い・リポジトリでない・origin が無いときは判定しない。
  host の無い宛先（`--repo OWNER/REPO`・`gh api repos/...`）は起動したリポジトリの host とみなす
- `git commit`: 判定するリポジトリ（上と同じく `git -C`・`cd`・`env -C` を追う。サブシェルの中の `cd` は
  閉じ括弧で戻す）の origin が違えば止める。origin の無いリポジトリ（検証用の一時リポジトリ）は外に出せないので通す
- `git push`: 宛先の remote の push の URL（位置引数・`--repo`、無ければ git と同じく pushRemote → pushDefault →
  追跡先 → origin）か、URL そのものが違えば止める
- `gh` の書き込み（`GH_WRITES` のサブコマンド。エイリアスの `new` を含む）: 宛先（引数の PR・Issue の URL、
  `-R`・`--repo`、前置の `GH_REPO=`、`gh repo` の引数、`gh issue transfer` の移す先、無ければ gh の既定の宛先）が
  違えば止める。gh の既定の宛先は `remote.<name>.gh-resolved` の remote（fork の clone で親へ向かうのを追う）、
  無ければ origin。`gh repo create`・`new`・`fork` は新しいリポジトリを作るので常に止める
- `gh api`: `-X`・`--method` が GET 以外か、本文を送るオプションがあって GET の明示が無いとき、
  パスの `repos/<owner>/<repo>`（完全な URL を含む）が違えば止める。`{owner}`・`{repo}` は gh の既定の宛先で
  置き換える。`user/repos`・`orgs/<org>/repos` への POST（リポジトリの作成）も止める
- 読み取り（`gh pr view`・`gh api` の GET・`git log` など）と `-h`・`--help` は止めない。Edit・Write も止めない（ADR 0020）
- 宛先にシェルの変数・コマンド置換（`$`・バッククォート）を含むときは、値が分からないので判定しない
- 追わないもの: `gh api graphql` の mutation（パスにリポジトリが無い）、`git cherry-pick`・`merge`・`revert`・`am`
  など commit 以外でコミットを作るサブコマンド（外へ出すのは push なので、そこで止まる）、`gh` 以外の手段（`curl` など）

bypass: コマンド中の本物のシェルコメント（クォートと heredoc の本文の外で、単語の先頭の `#`）に
`# via:main-commit-ok: <理由>` があるとき（理由必須）。via はコマンド中のどのコメントにあっても、コメントの中で
他の via（`# via:create-pr` など）と並べてもよく、そのコマンドのすべての commit を通す。起動したリポジトリ以外への書き込みは、別の
`# via:other-repo-ok: <理由>` で通す（ユーザーが指示したときだけ）。片方の via でもう片方は通らない。

限界: シェルの構文を完全には解釈しない best-effort の静的判定で、Claude Code がふだん出す形
（`git commit` / `git -C <リテラルのパス>` / `&&`・`;`・改行での連結 / `<<'EOF'` の heredoc）を対象にする。
変数・コマンド置換・前置コマンド・予約語の中の `cd` など、それ以外の形は見逃すことがあり、
分割に失敗したコマンドは通す（fail-open）。逆に、同じコマンド内で作業ブランチへ退避してからの commit
（`git switch -c x && git commit`。切り替えは追わない）と、`git commit --dry-run` / `-h` は main 上では止める
（別の Bash 呼び出しにすれば回復できる）。

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
GH_URL_RE = re.compile(r"^https?://([^/]+)/([^/]+)/([^/]+)/(?:pull|issues)/\d+")
# 値を別トークンで取る gh api のオプションと、そのうち本文を送るもの（GET の明示が無ければ POST になる）
GH_API_BODY_OPTS = {"-f", "-F", "--field", "--raw-field", "--input"}
GH_API_VALUE_OPTS = GH_API_BODY_OPTS | {"-H", "--header", "-q", "--jq", "-t", "--template", "--hostname", "--cache", "-p", "--preview"}
# 新しいリポジトリの作成の宛先（起動したリポジトリと一致しない値）
NEW_REPO = "<new>"
# host の無い宛先（`--repo OWNER/REPO`・`gh api repos/...`）の接頭辞。host は起動したリポジトリの host で補う
HOSTLESS = "*/"
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
    """remote の URL を `host/owner/repo`（小文字、`.git` なし）にそろえる。ローカルのパスなど、形が分からなければ None。"""
    u = url.strip()
    if _dynamic(u):
        return None
    m = re.match(r"^[A-Za-z][A-Za-z0-9+.-]*://(?:[^@/]+@)?([^/:]+)(?::\d+)?/(.+?)(?:\.git)?/?$", u)
    if m is None and not u.startswith(("/", ".", "~")):
        m = re.match(r"^(?:[^@/]+@)?([^/:]+):(.+?)(?:\.git)?/?$", u)  # scp 形式（git@host:owner/repo）
    if m is None:
        return None
    return f"{m.group(1)}/{m.group(2)}".lower()


def _git_out(d: str, *args: str) -> str | None:
    try:
        r = subprocess.run(["git", "-C", d, *args], capture_output=True, text=True, timeout=5)
    except (OSError, subprocess.SubprocessError):
        return None
    if r.returncode != 0:
        return None
    return r.stdout.strip() or None


def _origin(d: str) -> str | None:
    """d のリポジトリの origin を正規化したもの。リポジトリでない・origin が無い・git の失敗は None（判定しない側）。"""
    url = _git_out(d, "remote", "get-url", "origin")
    return _norm_url(url) if url else None


def _same(target: str, launch: str) -> bool:
    """宛先が起動したリポジトリか。host の無い宛先は owner/repo だけで比べる（host は起動したリポジトリのもの）。"""
    if target.startswith(HOSTLESS):
        return target[len(HOSTLESS) :] == launch.split("/", 1)[-1]
    return target == launch


def _gh_repo(value: str) -> str | None:
    """`--repo` の値（OWNER/REPO・HOST/OWNER/REPO・URL）を宛先にそろえる。OWNER/REPO は host の無い宛先にする。"""
    if _dynamic(value):
        return None
    if "://" in value:
        return _norm_url(value)
    parts = value.strip("/").split("/")
    if len(parts) == 2:
        return HOSTLESS + "/".join(parts).lower()
    if len(parts) == 3:
        return "/".join(parts).lower()
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
    url = _git_out(d, "remote", "get-url", "--push", remote)
    return _norm_url(url) if url else _norm_url(remote)


def _gh_default(d: str) -> str | None:
    """`--repo` の無い gh の宛先。`gh repo set-default`・`gh repo fork` が付ける `remote.<name>.gh-resolved` が
    あればその remote、無ければ origin（fork の clone で gh が親へ向かうのを追う）。"""
    out = _git_out(d, "config", "--get-regexp", r"^remote\..*\.gh-resolved$")
    for line in (out or "").splitlines():
        key, _, val = line.partition(" ")
        name = key[len("remote.") : -len(".gh-resolved")]
        if val == "base":
            url = _git_out(d, "remote", "get-url", name)
            return _norm_url(url) if url else None
        if "/" in val:
            return _gh_repo(val)
    return _origin(d)


def _gh_api_target(args: list[str], d: str) -> tuple[str, str] | None:
    """`gh api` が書き込みなら (宛先, 操作の表示) を、読み取り・リポジトリの外のパス（graphql を含む）なら None を返す。"""
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
    host = None
    m = re.match(r"^https?://([^/]+)/(?:api/v3/)?(.*)$", path)
    if m:
        host = "github.com" if m.group(1).lower() == "api.github.com" else m.group(1).lower()
        path = m.group(2)
    p = path.lstrip("/")
    if re.match(r"^(?:user|orgs/[^/]+)/repos/?$", p):
        return (NEW_REPO, op) if method == "POST" else None
    m = re.match(r"^repos/([^/]+)/([^/?]+)", p)
    if m is None:
        return None
    owner, repo = m.group(1), m.group(2)
    if owner == "{owner}" or repo == "{repo}":
        # プレースホルダは gh の既定の宛先で、owner と repo を別々に置き換える
        dflt = _gh_default(d)
        if dflt is None:
            return None
        h, d_owner, d_repo = dflt.split("/", 2)  # host の無い宛先は h が HOSTLESS の `*`
        owner = d_owner if owner == "{owner}" else owner
        repo = d_repo if repo == "{repo}" else repo
        return f"{h}/{owner}/{repo}".lower(), op
    return (f"{host}/{owner}/{repo}" if host else f"{HOSTLESS}{owner}/{repo}").lower(), op


def _gh_write_target(args: list[str], d: str, env: dict[str, str]) -> tuple[str, str] | None:
    """gh の書き込みなら (宛先, 操作の表示) を（新しいリポジトリの作成は NEW_REPO）、読み取りなら None を返す。"""
    if not args or "-h" in args or "--help" in args:
        return None
    if args[0] == "api":
        return _gh_api_target(args[1:], d)
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
        return NEW_REPO, op
    url_target = None
    for j, t in enumerate(rest):
        if t in ("-R", "--repo") and j + 1 < len(rest):
            repo = rest[j + 1]
        elif t.startswith("--repo="):
            repo = t.split("=", 1)[1]
        m = GH_URL_RE.match(t)
        if m and url_target is None:
            url_target = f"{m.group(1)}/{m.group(2)}/{m.group(3)}".lower()
    if group == "issue" and sub == "transfer":
        # 移す先のリポジトリに Issue を作る（`gh issue transfer <number> <destination-repo>`）
        pos = [t for t in rest if not t.startswith("-")]
        return (_gh_repo(pos[1]), op) if len(pos) >= 2 and _gh_repo(pos[1]) else None
    if url_target:
        return url_target, op
    if repo is not None:
        t = _gh_repo(repo)
        return (t, op) if t else None
    if env.get("GH_REPO"):
        t = _gh_repo(env["GH_REPO"])
        return (t, op) if t else None
    if group == "repo" and rest and not rest[0].startswith("-"):
        t = _gh_repo(rest[0])
        return (t, op) if t else None
    t = _gh_default(d)
    return (t, op) if t else None


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


def _blocked(segs: list[list[str]], cwd: str, proj: str | None) -> tuple[tuple[str, str] | None, tuple[str, str, str] | None]:
    """(main への commit, 起動したリポジトリ以外への書き込み) をそれぞれ返す。
    前者は (ディレクトリ, ブランチ)、後者は (操作, 宛先のリポジトリ, 起動したリポジトリ)。
    起動したリポジトリ（proj の origin）は、書き込みの宛先が分かったときに 1 回だけ求める。
    proj が無い・origin が無ければ後者は判定しない。"""
    base = cwd
    stack: list[str] = []
    main_hit = None
    other_hit = None
    launch_cache: list[str | None] = []

    def launch_repo() -> str | None:
        if not launch_cache:
            launch_cache.append(_origin(proj) if proj else None)
        return launch_cache[0]

    for seg in segs:
        if seg[0].startswith(PAREN_MARK):
            # サブシェルの中の cd は、閉じ括弧で元のディレクトリに戻す
            for ch in seg[0][len(PAREN_MARK) :]:
                if ch == "(":
                    stack.append(base)
                elif ch == ")" and stack:
                    base = stack.pop()
            continue
        if seg[0] == "cd":
            args = [a for a in seg[1:] if not a.startswith("-")]
            if len(args) == 1:
                base = os.path.join(base, os.path.expanduser(args[0]))
            continue
        hit = None
        call = _git_call(seg, base)
        if call is not None:
            d, sub, rest = call
            if sub == "commit" and main_hit is None:
                b = _branch(d)
                if b in PROTECTED and _has_remote(d):
                    main_hit = (d, b)
            if other_hit is None and sub in ("commit", "push"):
                target = _origin(d) if sub == "commit" else _push_target(rest, d)
                hit = (target, f"git {sub}") if target else None
        elif other_hit is None:
            gh = _gh_call(seg, base)
            if gh is not None:
                hit = _gh_write_target(gh[1], gh[0], gh[2])
        if hit is not None:
            launch = launch_repo()
            if launch is not None and not _same(hit[0], launch):
                other_hit = (hit[1], hit[0], launch)
    return main_hit, other_hit


def main() -> int:
    try:
        try:
            payload = json.load(sys.stdin)
        except (json.JSONDecodeError, ValueError, OSError):
            return 0
        if not isinstance(payload, dict):
            return 0
        if payload.get("tool_name") != "Bash":
            return 0
        ti = payload.get("tool_input") or {}
        cmd = ti.get("command", "") if isinstance(ti, dict) else ""
        if not isinstance(cmd, str) or not ("commit" in cmd or "push" in cmd or re.search(r"\bgh\b", cmd)):
            return 0
        cwd = payload.get("cwd")
        if not isinstance(cwd, str) or not cwd:
            cwd = os.getcwd()
        segs, comments = _parse(cmd)
        main_hit, other_hit = _blocked(segs, cwd, os.environ.get("CLAUDE_PROJECT_DIR"))

        # bypass: 分割のときに除いた本物のコメントの中だけで via を探す（判定ごとに別の via）
        if main_hit is not None and not any(VIA_RE.search(c) for c in comments):
            d, b = main_hit
            b = b[len("refs/heads/") :]
            print(
                "BLOCKED by main-commit-guard hook.\n"
                f"reason: `{b}` ブランチ上での git commit（{d}）。main / master へは直接 commit しない。\n"
                "`git switch -c <type>/<short-kebab-description>` で作業ブランチへ退避してから commit する"
                "（未コミットの変更はそのまま持ち越せる）。退避と commit は別の Bash 呼び出しで実行する"
                "（この hook は実行前の HEAD で判定するので、1 つのコマンドにつなぐと止まる）。\n"
                "ユーザーが main への commit を明示的に指示した場合のみ、コマンド中のコメントで "
                "`# via:main-commit-ok: <理由>` を付ける（理由は非空必須）。",
                file=sys.stderr,
            )
            return 2
        if other_hit is not None and not any(VIA_OTHER_RE.search(c) for c in comments):
            op, target, launch = other_hit
            if target == NEW_REPO:
                shown = "新しいリポジトリの作成（fork を含む）"
            elif target.startswith(HOSTLESS):
                shown = launch.split("/", 1)[0] + "/" + target[len(HOSTLESS) :]
            else:
                shown = target
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
        return 0
    except BaseException:
        # hook 失敗で Claude Code を止めない。exit 0 の stderr は動作に影響しないので、原因を追えるよう残す
        traceback.print_exc()
        return 0


if __name__ == "__main__":
    sys.exit(main())
