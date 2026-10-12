#!/usr/bin/env python3
"""
main-commit-guard.py

Claude Code PreToolUse (matcher: Bash) hook。

main / master 上の `git commit` を止める（ADR 0020。branching の「main で直接 commit しない」）。
Edit / Write は止めない。main 上で作った変更は `git switch -c <branch>` で作業ブランチへ
退避してから commit するのが正規の手順（rules/global/git/branching.md）なので、
実害であるコミットの時点で止める。

判定:
- コメントを除いてから shlex で分割し、`;` `&&` `||` `|` `&` 括弧・改行で区切ったセグメントごとに見る
- セグメントの先頭（`VAR=val` の前置と `then` `do` `{` などの予約語を除く）が `git` で、グローバルオプション
  （`-C <path>` / `-c <x=y>` / `--git-dir <path>` など / `--opt[=val]`）の後の subcommand が `commit` なら対象
- 判定するリポジトリ: `git -C <path>`（複数なら順に連結。相対パスは基準のディレクトリから）。
  基準のディレクトリは payload の `cwd` で、同じコマンド内の `cd <path>` に追従する
- `git symbolic-ref --short -q HEAD` が `main` / `master` なら止める（unborn のブランチも含む）。
  detached HEAD・リポジトリ外・git の失敗は通す

bypass: コマンド末尾の本物のシェルコメント `# via:main-commit-ok: <理由>`（理由必須。
クォート内に紛れ込ませたものは無効）。

静的判定の限界（止めない）: 変数展開・コマンド置換・eval で組み立てた commit、
`cd` 以外の手段（pushd など）で移ったディレクトリでの commit、`--git-dir` / `--work-tree` で
別のリポジトリを指した commit（基準のディレクトリのブランチで判定する）、
`git merge` / `cherry-pick` など commit 以外で main に履歴を積む操作。
サブシェルの中の `cd` は外にも効くものとして扱う（止める側に倒れる）。
クォートの対応が取れないコマンドは shlex が失敗するので通す（fail-open）。

例外は飲み込み、hook 失敗で Claude Code を止めない（exit 0）。
"""

from __future__ import annotations

import json
import os
import re
import shlex
import subprocess
import sys

PROTECTED = ("main", "master")
PUNCT = ";&|()\n"
OPERATORS = set(PUNCT)
ASSIGN_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")
# セグメントの先頭で読み飛ばすシェルの予約語
LEADING_WORDS = {"then", "do", "else", "!", "{", "time"}
# 値を別トークンで取る git のグローバルオプション（-C は別に扱う）
GIT_VALUE_OPTS = {"-c", "--git-dir", "--work-tree", "--namespace", "--config-env"}


def _strip_comments(cmd: str) -> str:
    """クォートの外で単語の先頭にある `#` から行末までを除く（改行は残す）。
    shlex のコメント処理は改行まで読み捨てて次の行と 1 つのセグメントにつなげてしまうため、自前で除く。"""
    out = []
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
            while i < len(cmd) and cmd[i] != "\n":
                i += 1
            continue
        else:
            out.append(c)
        i += 1
    return "".join(out)


def _segments(cmd: str) -> list[list[str]]:
    """コマンドを演算子・括弧・改行で区切ったトークン列のリストにする。コメントは除く。"""
    cmd = _strip_comments(re.sub(r"\\\n", " ", cmd))
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
    return [s for s in segs if s]


def _commit_dir(seg: list[str], base: str) -> str | None:
    """seg が git commit なら判定するディレクトリを、そうでなければ None を返す。"""
    i = 0
    while i < len(seg) and (seg[i] in LEADING_WORDS or ASSIGN_RE.match(seg[i])):
        i += 1
    if i >= len(seg) or seg[i] != "git":
        return None
    i += 1
    d = base
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
    if i < len(seg) and seg[i] == "commit":
        return d
    return None


def _branch(d: str) -> str | None:
    try:
        r = subprocess.run(
            ["git", "-C", d, "symbolic-ref", "--short", "-q", "HEAD"],
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if r.returncode != 0:
        return None
    return r.stdout.strip() or None


def _blocked(cmd: str, cwd: str) -> tuple[str, str] | None:
    """止めるなら (ディレクトリ, ブランチ) を返す。"""
    base = cwd
    for seg in _segments(cmd):
        if seg[0] == "cd" and len(seg) == 2:
            base = os.path.join(base, os.path.expanduser(seg[1]))
            continue
        d = _commit_dir(seg, base)
        if d is None:
            continue
        b = _branch(d)
        if b in PROTECTED:
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

        hit = _blocked(cmd, cwd)
        if hit is None:
            return 0

        # bypass: クォートを除いてから、本物のコメント位置の via を探す（destructive-guard と同じ方式）
        stripped = re.sub(r"'[^']*'|\"(?:[^\"\\]|\\.)*\"", "", cmd)
        if re.search(r"(?:^|\s)#\s*via:main-commit-ok\s*:\s*\S", stripped):
            return 0

        d, b = hit
        print(
            "BLOCKED by main-commit-guard hook.\n"
            f"reason: `{b}` ブランチ上での git commit（{d}）。main / master へは直接 commit しない。\n"
            "`git switch -c <type>/<short-kebab-description>` で作業ブランチへ退避してから commit する"
            "（未コミットの変更はそのまま持ち越せる）。\n"
            "ユーザーが main への commit を明示的に指示した場合のみ、コマンド末尾に "
            "`# via:main-commit-ok: <理由>` を付ける（理由は非空必須）。",
            file=sys.stderr,
        )
        return 2
    except BaseException:
        # hook 失敗で Claude Code を止めない
        return 0


if __name__ == "__main__":
    sys.exit(main())
