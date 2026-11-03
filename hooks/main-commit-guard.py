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

起動したリポジトリ以外への書き込みも止める（ADR 0033。branching の「GitHub 操作」）:
- 起動したリポジトリは `CLAUDE_PROJECT_DIR` の origin。比べるのはパスではなく origin の URL を
  `host/owner/repo` にそろえたもの（同じ origin の worktree・並走 clone は同じとみなす）。
  `CLAUDE_PROJECT_DIR` が無い・リポジトリでない・origin が無いときは判定しない
- `git commit`: 判定するリポジトリ（上と同じく `git -C`・`cd`・`env -C` を追う）の origin が違えば止める。
  origin の無いリポジトリ（検証用の一時リポジトリ）は外に出せないので通す
- `git push`: 宛先（`<remote>` の URL か、URL そのもの。remote の引数が無ければ origin）が違えば止める
- `gh` の書き込み（`GH_WRITES` のサブコマンド）: 宛先（`-R`・`--repo`、引数の PR・Issue の URL、`gh repo` の引数、
  無ければ実行するディレクトリの origin）が違えば止める。`gh repo create` は常に止める
- `gh api`: `-X`・`--method` が GET 以外か、本文を送るオプションがあって GET の明示が無いとき、
  パスの `repos/<owner>/<repo>` が違えば止める（`{owner}/{repo}` は実行するディレクトリで解決する）
- 読み取り（`gh pr view`・`gh api` の GET・`git log` など）は止めない。Edit・Write も止めない（ADR 0020）
- fork の clone で `gh` が `--repo` 無しに親へ向かう挙動は追わない（実行するディレクトリの origin で判定する）

bypass: コマンド中の本物のシェルコメント（クォートと heredoc の本文の外で、単語の先頭の `#`）が
`# via:main-commit-ok: <理由>` のとき（理由必須）。via はコマンド中のどのコメントにあっても、
そのコマンドのすべての commit を通す。起動したリポジトリ以外への書き込みは、別の
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
VIA_RE = re.compile(r"#\s*via:main-commit-ok\s*:\s*\S")
VIA_OTHER_RE = re.compile(r"#\s*via:other-repo-ok\s*:\s*\S")
# 値を別トークンで取る git のグローバルオプション（-C は別に扱う）
GIT_VALUE_OPTS = {"-c", "--git-dir", "--work-tree", "--namespace", "--config-env"}
# 値を別トークンで取る git push のオプション
GIT_PUSH_VALUE_OPTS = {"-o", "--push-option", "--repo", "--receive-pack", "--exec"}
# 書き込みとみなす gh のサブコマンド
GH_WRITES = {
    "pr": {"create", "edit", "merge", "comment", "review", "close", "reopen", "ready"},
    "issue": {"create", "edit", "comment", "close", "reopen", "delete", "transfer", "lock"},
    "label": {"create", "edit", "delete", "clone"},
    "release": {"create", "edit", "delete", "upload"},
    "repo": {"fork", "create", "edit", "delete", "rename", "archive"},
}
# gh pr / issue の引数に渡す URL（https://github.com/OWNER/REPO/pull/N）
GH_URL_RE = re.compile(r"^https?://([^/]+)/([^/]+)/([^/]+)/(?:pull|issues)/\d+")
# 値を別トークンで取る gh api のオプションと、そのうち本文を送るもの（GET の明示が無ければ POST になる）
GH_API_BODY_OPTS = {"-f", "-F", "--field", "--raw-field", "--input"}
GH_API_VALUE_OPTS = GH_API_BODY_OPTS | {"-H", "--header", "-q", "--jq", "-t", "--template", "--hostname", "--cache", "-p", "--preview"}
# gh repo create の宛先（起動したリポジトリと一致しない値）
NEW_REPO = "<new>"


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
            segs.append([])
        else:
            segs[-1].append(tok)
    return [s for s in segs if s], comments


def _skip_prefix(seg: list[str], base: str) -> tuple[int, str]:
    """セグメントの先頭の予約語・代入・前置コマンド・env を読み飛ばし、(コマンド名の位置, 実行するディレクトリ) を返す。"""
    i = 0
    d = base
    while i < len(seg):
        t = seg[i]
        if t in LEADING_WORDS or ASSIGN_RE.match(t):
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
    return i, d


def _git_call(seg: list[str], base: str) -> tuple[str, str, list[str]] | None:
    """seg が git の呼び出しなら (判定するディレクトリ, subcommand, subcommand の後の引数) を、そうでなければ None を返す。"""
    i, d = _skip_prefix(seg, base)
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


def _gh_call(seg: list[str], base: str) -> tuple[str, list[str]] | None:
    """seg が gh の呼び出しなら (実行するディレクトリ, gh の後の引数) を、そうでなければ None を返す。"""
    i, d = _skip_prefix(seg, base)
    if i >= len(seg) or seg[i] != "gh":
        return None
    return d, seg[i + 1 :]


def _norm_url(url: str) -> str | None:
    """remote の URL を `host/owner/repo`（小文字、`.git` なし）にそろえる。ローカルのパスなど、形が分からなければ None。"""
    u = url.strip()
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


def _gh_repo(value: str) -> str | None:
    """`--repo` の値（OWNER/REPO・HOST/OWNER/REPO・URL）を `host/owner/repo` にそろえる。"""
    if "://" in value:
        return _norm_url(value)
    parts = value.strip("/").split("/")
    if len(parts) == 2:
        return f"github.com/{value.strip('/')}".lower()
    if len(parts) == 3:
        return value.strip("/").lower()
    return None


def _push_target(args: list[str], d: str) -> str | None:
    """`git push` の宛先のリポジトリ。remote の引数が無ければ origin とみなす。"""
    i = 0
    while i < len(args):
        t = args[i]
        if t in GIT_PUSH_VALUE_OPTS:
            i += 2
            continue
        if t.startswith("-"):
            i += 1
            continue
        url = _git_out(d, "remote", "get-url", t)
        return _norm_url(url) if url else _norm_url(t)
    return _origin(d)


def _gh_api_target(args: list[str], d: str) -> str | None:
    """`gh api` が書き込みなら対象のリポジトリを、読み取り・リポジトリの外のパスなら None を返す。"""
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
        elif t in GH_API_BODY_OPTS or t.startswith(("--field=", "--raw-field=", "--input=")):
            body = True
            if t in GH_API_BODY_OPTS:
                i += 2
                continue
        elif t in GH_API_VALUE_OPTS:
            i += 2
            continue
        elif not t.startswith("-") and path is None:
            path = t
        i += 1
    if (method or ("POST" if body else "GET")).upper() == "GET" or path is None:
        return None
    m = re.match(r"^/?repos/([^/]+)/([^/?]+)", path)
    if m is None:
        return None
    if m.group(1) == "{owner}" or m.group(2) == "{repo}":
        return _origin(d)
    return f"github.com/{m.group(1)}/{m.group(2)}".lower()


def _gh_write_target(args: list[str], d: str) -> str | None:
    """gh の書き込みなら対象のリポジトリを（新しいリポジトリの作成は NEW_REPO）、読み取りなら None を返す。"""
    if not args:
        return None
    if args[0] == "api":
        return _gh_api_target(args[1:], d)
    if len(args) < 2 or args[1] not in GH_WRITES.get(args[0], ()):
        return None
    group, sub, rest = args[0], args[1], args[2:]
    if group == "repo" and sub == "create":
        return NEW_REPO
    for j, t in enumerate(rest):
        if t in ("-R", "--repo") and j + 1 < len(rest):
            return _gh_repo(rest[j + 1])
        if t.startswith("--repo="):
            return _gh_repo(t.split("=", 1)[1])
        m = GH_URL_RE.match(t)
        if m:
            return f"{m.group(1)}/{m.group(2)}/{m.group(3)}".lower()
    if group == "repo" and rest and not rest[0].startswith("-"):
        return _gh_repo(rest[0])
    return _origin(d)


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
    起動したリポジトリ（proj の origin）は、git commit・git push・gh のセグメントが来たときに 1 回だけ求める。
    proj が無い・origin が無ければ後者は判定しない。"""
    base = cwd
    main_hit = None
    other_hit = None
    launch_cache: list[str | None] = []

    def launch_repo() -> str | None:
        if not launch_cache:
            launch_cache.append(_origin(proj) if proj else None)
        return launch_cache[0]

    for seg in segs:
        if seg[0] == "cd":
            args = [a for a in seg[1:] if not a.startswith("-")]
            if len(args) == 1:
                base = os.path.join(base, os.path.expanduser(args[0]))
            continue
        target = None
        op = None
        call = _git_call(seg, base)
        if call is not None:
            d, sub, rest = call
            if sub == "commit" and main_hit is None:
                b = _branch(d)
                if b in PROTECTED and _has_remote(d):
                    main_hit = (d, b)
            if other_hit is None and sub in ("commit", "push") and launch_repo() is not None:
                op = f"git {sub}"
                target = _origin(d) if sub == "commit" else _push_target(rest, d)
        elif other_hit is None:
            gh = _gh_call(seg, base)
            if gh is not None and launch_repo() is not None:
                d, rest = gh
                target = _gh_write_target(rest, d)
                op = "gh " + " ".join(rest[:2])
        if target is not None and target != launch_repo():
            other_hit = (op, target, launch_repo())
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
        if not isinstance(cmd, str) or not any(k in cmd for k in ("commit", "push", "gh")):
            return 0
        cwd = payload.get("cwd")
        if not isinstance(cwd, str) or not cwd:
            cwd = os.getcwd()
        segs, comments = _parse(cmd)
        main_hit, other_hit = _blocked(segs, cwd, os.environ.get("CLAUDE_PROJECT_DIR"))

        # bypass: 分割のときに除いた本物のコメントの中だけで via を探す（判定ごとに別の via）
        if main_hit is not None and not any(VIA_RE.match(c) for c in comments):
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
        if other_hit is not None and not any(VIA_OTHER_RE.match(c) for c in comments):
            op, target, launch = other_hit
            shown = "新しいリポジトリの作成" if target == NEW_REPO else target
            print(
                "BLOCKED by main-commit-guard hook.\n"
                f"reason: 起動したリポジトリ（{launch}）以外への書き込み: `{op}` → {shown}。\n"
                "起動したリポジトリ以外（上流・vendor 元・依存先・別のプロジェクト）には、ユーザーの明示的な指示がない限り"
                "書き込まない（rules/global/git/branching.md の「GitHub 操作」、ADR 0033）。"
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
