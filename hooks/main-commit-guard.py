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

bypass: コマンド中の本物のシェルコメント（クォートと heredoc の本文の外で、単語の先頭の `#`）が
`# via:main-commit-ok: <理由>` のとき（理由必須）。via はコマンド中のどのコメントにあっても、
そのコマンドのすべての commit を通す。

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
# 値を別トークンで取る git のグローバルオプション（-C は別に扱う）
GIT_VALUE_OPTS = {"-c", "--git-dir", "--work-tree", "--namespace", "--config-env"}


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


def _git_call(seg: list[str], base: str) -> tuple[str, str] | None:
    """seg が git の呼び出しなら (判定するディレクトリ, subcommand) を、そうでなければ None を返す。"""
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
    return d, seg[i]


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


def _blocked(segs: list[list[str]], cwd: str) -> tuple[str, str] | None:
    """止めるなら (ディレクトリ, ブランチ) を返す。"""
    base = cwd
    for seg in segs:
        if seg[0] == "cd":
            args = [a for a in seg[1:] if not a.startswith("-")]
            if len(args) == 1:
                base = os.path.join(base, os.path.expanduser(args[0]))
            continue
        call = _git_call(seg, base)
        if call is None:
            continue
        d, sub = call
        if sub != "commit":
            continue
        b = _branch(d)
        if b in PROTECTED and _has_remote(d):
            return d, b
    return None


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
        if not isinstance(cmd, str) or "commit" not in cmd:
            return 0
        cwd = payload.get("cwd")
        if not isinstance(cwd, str) or not cwd:
            cwd = os.getcwd()

        segs, comments = _parse(cmd)
        hit = _blocked(segs, cwd)
        if hit is None:
            return 0

        # bypass: 分割のときに除いた本物のコメントの中だけで via を探す
        if any(VIA_RE.match(c) for c in comments):
            return 0

        d, b = hit
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
    except BaseException:
        # hook 失敗で Claude Code を止めない。exit 0 の stderr は動作に影響しないので、原因を追えるよう残す
        traceback.print_exc()
        return 0


if __name__ == "__main__":
    sys.exit(main())
