#!/usr/bin/env python3
"""決定ログ（knowledge/ の append-only な決定の記録）の不変性を機械検査する（#27）。

`rules/hve/artifact-management.md`「決定ログの不変性」が定める 2 方式を、方式の宣言
なしに自動判定して検査する:

- **独立ファイル方式（既定）**: `--adr-dir`（既定 `knowledge/adr`）が base コミット時点
  で存在するリポジトリに適用する。base にあった ADR ファイル（README.md を除く）は
  削除・改名を禁止する。`## ステータス` 節を除いた本文は、行数が同じで同じ位置の行の
  中だけが変わっている（誤字修正や決定の書き換えが 1 行の中に収まっている）場合のみ
  警告にする。行の追加・削除（行数が変わる、または行の対応が取れない変更）は、機械で
  誤字修正と判定できないため error にする。`## ステータス` 見出し自体の数が base と
  現在で変わっていれば警告する。一覧 `README.md` は base にあった行の削除を禁止し、
  ステータス列以外の変更を警告、ステータス列の変更は許可する。README のステータス列と
  ADR 本体のステータス節の値の食い違いは、base に無い新規 ADR を含む現在の全行について
  検査し、食い違えば警告する。`--adr-dir` 配下にサブディレクトリや `.md` 以外のファイル
  （`README.md` を除く）があれば、独立ファイル方式の前提（フラット配置）から外れるため
  検査対象外になる旨を警告する（base にあったそれらの削除も同様に警告）。
- **インライン方式**: `--dir`（既定 `knowledge`）配下を再帰的に見て、base 側で
  `## 決定ログ` 見出し（コードフェンスの外）を持つ `.md` を対象にする。base 時点の
  節の内容が、現在の節の先頭に一致する（prefix）ことだけを求める。末尾への追記だけが
  許され、既存行の変更・削除・途中への挿入・節や文書そのものの削除は error になる。
  1 つの文書に `## 決定ログ` 見出しが 2 つ以上ある（base・現在のいずれか）のも error
  にする（節の境界が一意に決まらないため）。ディレクトリの改名に伴う、節内のパス参照の
  置換は許容する。置換ペアは改名の前後のディレクトリの full path だけで、末尾成分だけの
  ペア（例: `src/v1` → `src/v2` の改名から `v1` → `v2` を作る）は作らない。置換も
  パス区切り等で挟まれた一致だけに当てる（無関係な文字列への誤爆を避けるため）。

比較は `git merge-base <head> <base-ref>`（既定 `<base-ref>` = `origin/main`、無ければ
`main`）を基準に行う。`--head <commit>` を渡すとそのコミットの内容と比較し、渡さない
ときは作業ツリー（未コミットの変更を含む）と比較する。merge-base が解決できない
（ref が無い・shallow clone で履歴が足りない等）ときは、違反の有無を判定できないので
exit 2 にする（違反なしとして通さない）。

git の出力は `-c core.quotePath=false -c diff.noprefix=false -c diff.mnemonicPrefix=false`
で固定し、diff を使う箇所は `--no-ext-diff --no-textconv --no-color --text` を付ける。
内容の比較は `git diff` の文字列出力ではなく `git show <commit>:<path>`（または作業
ツリーのバイト列）を読んで行うため、`diff.external` / textconv の設定に影響されない。
パスの存在確認は `git cat-file -e <commit>:<path>` の終了コードだけで判定し、「パスが
無い」と「git 自体の失敗（壊れたオブジェクト等）」を混同しない。後者は判定不能として
`git_failed()` 経由で exit 2 にする（違反なしとして通さない）。
リネーム検出（`-M`）は、インライン方式のディレクトリ改名の許容判定と、独立ファイル
方式の ADR 改名検出のためだけに使う。

使い方:
  # 既定（origin/main または main の merge-base と、作業ツリーを比較）
  python3 hve-scripts/check-decision-log.py

  # pre-push hook から: stdin で渡される push 先の commit を --head に渡す
  #   <local ref> <local sha> <remote ref> <remote sha>
  while read local_ref local_sha remote_ref remote_sha; do
      python3 hve-scripts/check-decision-log.py --head "$local_sha" || exit 1
  done

  # CI で特定のコミットを検査する
  python3 hve-scripts/check-decision-log.py --base origin/main --head "$GITHUB_SHA"

終了コード:
  0 - 違反なし（警告のみを含む場合もある）
  1 - 不変性違反（error）がある
  2 - 判定不能（merge-base が解決できない）または引数が不正

依存は標準ライブラリのみ。Python 3.9 以上で動く。
"""

import argparse
import re
import subprocess
import sys
from pathlib import Path

GIT_CONFIG_ARGS = [
    "-c", "core.quotePath=false",
    "-c", "diff.noprefix=false",
    "-c", "diff.mnemonicPrefix=false",
]
DIFF_FIXED_ARGS = ["--no-ext-diff", "--no-textconv", "--no-color", "--text"]

RE_DECISION_LOG_HEADING = re.compile(r"^##\s+決定ログ\s*$")
RE_STATUS_HEADING = re.compile(r"^##\s+ステータス\s*$")
# 節の終端。h1 / h2 が来たらそこまで（h3 以下は節の内側）。
RE_SECTION_END = re.compile(r"^#{1,2}\s+\S")
RE_FENCE = re.compile(r"^(`{3,}|~{3,})")
RE_TABLE_ROW = re.compile(r"^\s*\|(.+)\|\s*$")
RE_TABLE_SEP_CELL = re.compile(r"^:?-{1,}:?$")
RE_NUMBER = re.compile(r"(\d{3,})")


# --- git ヘルパー -------------------------------------------------------------


def run_git(root, *args):
    return subprocess.run(
        ["git", *GIT_CONFIG_ARGS, *args], cwd=str(root), capture_output=True, text=True
    )


def git_failed(proc, what):
    """git の失敗は判定不能として exit 2 で止める（違反なしとして通さない）。"""
    print(f"✗ git {what} に失敗した: {proc.stderr.strip()}", file=sys.stderr)
    sys.exit(2)


def repo_root():
    proc = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"], capture_output=True, text=True
    )
    if proc.returncode != 0:
        print("✗ git リポジトリ外では実行できない", file=sys.stderr)
        sys.exit(2)
    return Path(proc.stdout.strip())


def show_blob(root, commit, rel):
    """`<commit>:<rel>` の内容を返す。パスが無ければ None。

    `git show` が失敗しても、`git cat-file -e` でパス自体の存在を別途確認する。
    パスがあるのに `git show` が失敗する（壊れたオブジェクト等）場合は、
    「存在しない」に寄せず git_failed() で exit 2 にする。
    """
    proc = subprocess.run(
        ["git", *GIT_CONFIG_ARGS, "show", f"{commit}:{rel}"],
        cwd=str(root),
        capture_output=True,
    )
    if proc.returncode != 0:
        if not path_exists_at(root, commit, rel):
            return None
        git_failed(
            subprocess.CompletedProcess(
                proc.args, proc.returncode, proc.stdout,
                proc.stderr.decode("utf-8", "replace"),
            ),
            f"show {commit}:{rel}",
        )
    return proc.stdout.decode("utf-8", "surrogateescape")


def read_current(root, head, rel):
    """現在（--head があればそのコミット、無ければ作業ツリー）の内容を返す。無ければ None。"""
    if head is None:
        path = root / rel
        if not path.is_file():
            return None
        return path.read_bytes().decode("utf-8", "surrogateescape")
    return show_blob(root, head, rel)


def path_exists_at(root, commit, rel):
    """`<commit>:<rel>` が存在するかを `git cat-file -e` の終了コードだけで判定する。

    （`ls-tree` の出力の有無で判定すると、git 自体の失敗で出力が空になった場合も
    「存在しない」と誤判定してしまうため使わない。）
    """
    proc = subprocess.run(
        ["git", *GIT_CONFIG_ARGS, "cat-file", "-e", f"{commit}:{rel}"],
        cwd=str(root),
        capture_output=True,
    )
    return proc.returncode == 0


def list_md_files(root, commit, directory, recursive):
    """`directory` 配下の `.md` を列挙する（commit 時点）。"""
    norm_dir = directory.rstrip("/")
    args = ["ls-tree", "--name-only"]
    if recursive:
        args.append("-r")
    args.append(f"{commit}:{norm_dir}")
    proc = run_git(root, *args)
    if proc.returncode != 0:
        # その時点にディレクトリが無いだけなら対象なし。それ以外の失敗は判定不能として止める
        # （空として扱うと、検査を素通りさせてしまう）。
        commit_ok = run_git(root, "rev-parse", "--verify", "--quiet", f"{commit}^{{commit}}").returncode == 0
        dir_missing = run_git(root, "cat-file", "-e", f"{commit}:{norm_dir}").returncode != 0
        if commit_ok and dir_missing:
            return []
        git_failed(proc, f"ls-tree {commit}:{norm_dir}")
    names = []
    for line in proc.stdout.splitlines():
        line = line.strip()
        if line.endswith(".md"):
            names.append(f"{norm_dir}/{line}")
    return sorted(names)


def list_dir_tree_entries(root, commit, directory):
    """`commit` 時点の `directory` 直下のエントリを (name, kind) で返す
    （`kind` は 'blob' か 'tree'）。`directory` が無ければ空リストを返す。
    """
    norm_dir = directory.rstrip("/")
    proc = run_git(root, "ls-tree", f"{commit}:{norm_dir}")
    if proc.returncode != 0:
        commit_ok = run_git(root, "rev-parse", "--verify", "--quiet", f"{commit}^{{commit}}").returncode == 0
        dir_missing = not path_exists_at(root, commit, norm_dir)
        if commit_ok and dir_missing:
            return []
        git_failed(proc, f"ls-tree {commit}:{norm_dir}")
    entries = []
    for line in proc.stdout.splitlines():
        line = line.rstrip("\n")
        if not line:
            continue
        meta, _, name = line.partition("\t")
        fields = meta.split()
        kind = fields[1] if len(fields) > 1 else "blob"
        entries.append((name, kind))
    return entries


def list_current_dir_entries(root, head, directory):
    """`directory` 直下のエントリを (name, kind) で返す（`head` 指定時はそのコミット、
    無指定なら作業ツリー）。`kind` は 'blob' か 'tree'。
    """
    if head is None:
        path = root / directory
        if not path.is_dir():
            return []
        return sorted(
            (child.name, "tree" if child.is_dir() else "blob")
            for child in path.iterdir()
        )
    return list_dir_tree_entries(root, head, directory)


def run_diff_name_status(root, base_sha, head, paths=None, rename=True, diff_filter=None):
    args = ["diff", *DIFF_FIXED_ARGS]
    if rename:
        args.append("-M")
    if diff_filter:
        args.append(f"--diff-filter={diff_filter}")
    args.append("--name-status")
    args.append(base_sha)
    if head is not None:
        args.append(head)
    if paths:
        args.append("--")
        args.extend(paths)
    proc = run_git(root, *args)
    if proc.returncode != 0:
        git_failed(proc, "diff --name-status")
    return [line for line in proc.stdout.splitlines() if line.strip()]


def file_rename_map(root, base_sha, head, scope_dir):
    """`scope_dir` 配下での base→現在 のファイル改名を {旧パス: 新パス} で返す。"""
    lines = run_diff_name_status(root, base_sha, head, paths=[scope_dir], rename=True, diff_filter="R")
    mapping = {}
    for line in lines:
        parts = line.split("\t")
        if len(parts) >= 3:
            mapping[parts[1]] = parts[2]
    return mapping


def detect_path_renames(root, base_sha, head):
    """base..head（or 作業ツリー）間のファイルリネームからディレクトリリネームを検出する。

    返り値は (旧 full path, 新 full path) のリスト（長い順）。base の行に適用して
    現在の行と一致すれば「パスリネームのみの変更」と判定できる。置換ペアは改名の
    前後のディレクトリの full path だけにする。末尾成分だけのペア（例:
    `src/v1` → `src/v2` の改名から `v1` → `v2` を作る）は作らない。これを作ると、
    改名と無関係な本文中の同名の文字列（例: 「方式 v1 を採用する」の `v1`）まで
    書き換えを許容してしまい、決定の書き換えを見逃す。
    リポジトリ全体を対象にする（リンク先が --dir の外にあることがあるため）。
    """
    lines = run_diff_name_status(root, base_sha, head, paths=None, rename=True, diff_filter="R")

    dir_renames = set()
    for line in lines:
        parts = line.split("\t")
        if len(parts) < 3:
            continue
        old_dir = str(Path(parts[1]).parent)
        new_dir = str(Path(parts[2]).parent)
        if old_dir != new_dir:
            dir_renames.add((old_dir, new_dir))

    subs = sorted(dir_renames, key=lambda p: len(p[0]), reverse=True)
    return subs


# パス境界とみなす文字（この文字で挟まれていない一致は置換しない）。英数字・`_`・`-`・`.`
# は path/word の構成要素として扱い、境界にはしない。
_NOT_BOUNDARY_CHARS = r"[\w\-.]"


def _path_boundary_pattern(token):
    return re.compile(
        rf"(?<!{_NOT_BOUNDARY_CHARS}){re.escape(token)}(?!{_NOT_BOUNDARY_CHARS})"
    )


def apply_renames(line, renames):
    """`renames`（旧→新の full path ペア）を、パス境界に挟まれた一致だけに当てる。"""
    result = line
    for old, new in renames:
        result = _path_boundary_pattern(old).sub(lambda m, new=new: new, result)
    return result


# --- Markdown 節の抽出 ---------------------------------------------------------


def extract_section(text, heading_re):
    """`heading_re` に一致する見出し直下から次の h1/h2 まで（フェンス除外）を
    (行番号, 行末空白を落とした本文) のリストで返す。見出しが無ければ None。
    見出し行そのものは含めない。節末尾の空行は落とす。
    """
    collected = None
    fence = None
    for lineno, raw in enumerate(text.splitlines(), 1):
        stripped = raw.strip()
        opener = RE_FENCE.match(stripped)
        if opener:
            token = opener.group(1)
            if fence is None:
                fence = (token[0], len(token))
            elif token[0] == fence[0] and len(token) >= fence[1]:
                fence = None
            if collected is not None:
                collected.append((lineno, raw.rstrip()))
            continue
        if fence is None:
            if heading_re.match(raw.rstrip()):
                collected = []
                continue
            if collected is not None and RE_SECTION_END.match(raw):
                break
        if collected is not None:
            collected.append((lineno, raw.rstrip()))
    if collected is None:
        return None
    while collected and not collected[-1][1]:
        collected.pop()
    return collected


def count_headings(text, heading_re):
    """`heading_re` に一致する見出し（コードフェンスの外）の数を返す。"""
    count = 0
    fence = None
    for raw in text.splitlines():
        stripped = raw.strip()
        opener = RE_FENCE.match(stripped)
        if opener:
            token = opener.group(1)
            if fence is None:
                fence = (token[0], len(token))
            elif token[0] == fence[0] and len(token) >= fence[1]:
                fence = None
            continue
        if fence is None and heading_re.match(raw.rstrip()):
            count += 1
    return count


def strip_section(text, heading_re):
    """`heading_re` に一致する見出し行から次の h1/h2 まで（フェンス除外）を取り除いた
    残りの行リスト（行末空白を落とす）を返す。見出しが無ければ全文をそのまま返す。
    """
    result = []
    in_section = False
    fence = None
    for raw in text.splitlines():
        stripped = raw.strip()
        opener = RE_FENCE.match(stripped)
        if opener:
            token = opener.group(1)
            if fence is None:
                fence = (token[0], len(token))
            elif token[0] == fence[0] and len(token) >= fence[1]:
                fence = None
            if not in_section:
                result.append(raw.rstrip())
            continue
        if fence is None:
            if heading_re.match(raw.rstrip()):
                in_section = True
                continue
            if in_section and RE_SECTION_END.match(raw):
                in_section = False
        if not in_section:
            result.append(raw.rstrip())
    while result and not result[-1]:
        result.pop()
    return result


def first_diff(base_lines, current_lines):
    """最初に異なる行の (index, base の行 or None, 現在の行 or None) を返す。無ければ None。"""
    for i in range(max(len(base_lines), len(current_lines))):
        b = base_lines[i] if i < len(base_lines) else None
        c = current_lines[i] if i < len(current_lines) else None
        if b != c:
            return i, b, c
    return None


def extract_status_value(text):
    """`## ステータス` 節の最初の非空行から、`— 日付` の前の値を取る。節が無ければ None。"""
    section = extract_section(text, RE_STATUS_HEADING)
    if not section:
        return None
    for _, line in section:
        line = line.strip()
        if not line:
            continue
        return re.split(r"\s+—\s+", line, maxsplit=1)[0].strip()
    return None


def parse_tables(text):
    """テキスト中の Markdown テーブルをすべて抽出する。[(header_cells, [row_cells, ...]), ...]。"""
    lines = text.splitlines()
    tables = []
    i = 0
    n = len(lines)
    while i < n:
        header_m = RE_TABLE_ROW.match(lines[i])
        if header_m and i + 1 < n:
            sep_m = RE_TABLE_ROW.match(lines[i + 1])
            if sep_m:
                sep_cells = [c.strip() for c in sep_m.group(1).split("|")]
                if sep_cells and all(RE_TABLE_SEP_CELL.match(c) for c in sep_cells):
                    header_cells = [c.strip() for c in header_m.group(1).split("|")]
                    i += 2
                    rows = []
                    while i < n:
                        row_m = RE_TABLE_ROW.match(lines[i])
                        if not row_m:
                            break
                        rows.append([c.strip() for c in row_m.group(1).split("|")])
                        i += 1
                    tables.append((header_cells, rows))
                    continue
        i += 1
    return tables


def row_key(cells):
    first = cells[0] if cells else ""
    m = RE_NUMBER.search(first)
    return m.group(1) if m else first


def adr_number(name):
    m = RE_NUMBER.search(name)
    return m.group(1) if m else name


# --- インライン方式 ------------------------------------------------------------


def compare_prefix(rel, base_log, current_log, renames, errors):
    """違反は先頭 1 件だけ報告する（prefix 比較なので後続は連鎖的な偽陽性になるため）。"""
    for i, (base_lineno, base_line) in enumerate(base_log):
        if i >= len(current_log):
            errors.append(
                f"{rel}: 決定ログの既存エントリが削除されている"
                f"（base は {len(base_log)} 行 / 現在は {len(current_log)} 行）。"
                f"base の {base_lineno} 行目以降が消えた\n"
                f"      - base:  {base_line or '(空行)'}"
            )
            return
        current_lineno, current_line = current_log[i]
        if base_line != current_line:
            if renames and apply_renames(base_line, renames) == current_line:
                continue
            errors.append(
                f"{rel}: 決定ログの既存エントリが変更されている（{current_lineno} 行目）。"
                "決定ログは append-only で、既存の決定は書き換えず新しいエントリで覆す\n"
                f"      - base:  {base_line or '(空行)'}\n"
                f"      + 現在:  {current_line or '(空行)'}"
            )
            return


def check_inline_method(root, base_sha, head, dir_, adr_dir, path_renames):
    base_files = list_md_files(root, base_sha, dir_, recursive=True)
    adr_prefix = adr_dir.rstrip("/") + "/"
    base_files = [f for f in base_files if not f.startswith(adr_prefix) and f != adr_dir]

    rename_map = file_rename_map(root, base_sha, head, dir_)

    errors = []
    checked = 0
    for rel in base_files:
        base_text = show_blob(root, base_sha, rel)
        if base_text is None:
            continue
        base_log = extract_section(base_text, RE_DECISION_LOG_HEADING)
        if base_log is None:
            continue  # base に決定ログが無い＝対象外

        if count_headings(base_text, RE_DECISION_LOG_HEADING) >= 2:
            errors.append(
                f"{rel}: `## 決定ログ` 見出しが 2 つ以上ある（base）。"
                "節の境界が一意に決まらないため、1 文書に 1 節だけ許可する"
            )
            checked += 1
            continue

        current_rel = rename_map.get(rel, rel)
        current_text = read_current(root, head, current_rel)
        if current_text is None:
            errors.append(
                f"{rel}: 決定ログを持つ文書が削除されている。"
                "決定ログは append-only で、節を持つ文書の削除はできない"
            )
            checked += 1
            continue

        current_log = extract_section(current_text, RE_DECISION_LOG_HEADING)
        if current_log is None:
            errors.append(
                f"{current_rel}: 決定ログ節ごと消えている（`## 決定ログ` の見出しが見つからない）。"
                "決定ログは append-only で、節の削除・見出しの改名はできない"
            )
            checked += 1
            continue

        if count_headings(current_text, RE_DECISION_LOG_HEADING) >= 2:
            errors.append(
                f"{current_rel}: `## 決定ログ` 見出しが 2 つ以上ある。"
                "節の境界が一意に決まらないため、1 文書に 1 節だけ許可する"
            )
            checked += 1
            continue

        checked += 1
        compare_prefix(current_rel, base_log, current_log, path_renames, errors)

    return checked, errors


# --- 独立ファイル方式 ----------------------------------------------------------


def check_adr_method(root, base_sha, head, adr_dir):
    base_files = [
        f for f in list_md_files(root, base_sha, adr_dir, recursive=False)
        if Path(f).name != "README.md"
    ]
    rename_map = file_rename_map(root, base_sha, head, adr_dir)

    errors = []
    warnings = []
    checked = 0
    status_by_number = {}

    for rel in base_files:
        number = adr_number(Path(rel).name)

        if rel in rename_map:
            errors.append(
                f"{rel}: ADR ファイルが改名されている（新しいパス: {rename_map[rel]}）。"
                "独立ファイル方式はファイルの削除・改名を禁止する"
            )
            checked += 1
            continue

        current_text = read_current(root, head, rel)
        if current_text is None:
            errors.append(
                f"{rel}: ADR ファイルが削除されている。"
                "独立ファイル方式はファイルの削除・改名を禁止する"
            )
            checked += 1
            continue

        base_text = show_blob(root, base_sha, rel)

        base_status_count = count_headings(base_text, RE_STATUS_HEADING)
        current_status_count = count_headings(current_text, RE_STATUS_HEADING)
        if base_status_count != current_status_count:
            warnings.append(
                f"{rel}: `## ステータス` 節の見出しが増減した"
                f"（base: {base_status_count} 個 / 現在: {current_status_count} 個）"
            )

        base_rest = strip_section(base_text, RE_STATUS_HEADING)
        current_rest = strip_section(current_text, RE_STATUS_HEADING)
        if base_rest != current_rest:
            diff = first_diff(base_rest, current_rest)
            idx, b, c = diff
            if len(base_rest) != len(current_rest):
                errors.append(
                    f"{rel}: `## ステータス` 節の外で行の追加・削除がある"
                    f"（base は {len(base_rest)} 行 / 現在は {len(current_rest)} 行）。"
                    f"{idx + 1} 行目相当。"
                    "行数が変わる変更は機械では誤字修正と判定できないため禁止する\n"
                    f"      - base:  {b if b is not None else '(行が無い)'}\n"
                    f"      + 現在:  {c if c is not None else '(行が無い)'}"
                )
                checked += 1
                continue
            warnings.append(
                f"{rel}: `## ステータス` 節の外で内容が変わっている（誤字修正に限る）。"
                f"{idx + 1} 行目相当\n"
                f"      - base:  {b if b is not None else '(行が無い)'}\n"
                f"      + 現在:  {c if c is not None else '(行が無い)'}"
            )

        status_by_number[number] = extract_status_value(current_text)
        checked += 1

    # F5: README との突き合わせは、base に無い新規 ADR も含めた現在の全 ADR を対象にする。
    for name, kind in list_current_dir_entries(root, head, adr_dir):
        if name == "README.md" or kind != "blob" or not name.endswith(".md"):
            continue
        number = adr_number(name)
        if number in status_by_number:
            continue
        current_text = read_current(root, head, f"{adr_dir}/{name}")
        if current_text is not None:
            status_by_number[number] = extract_status_value(current_text)

    return checked, errors, warnings, status_by_number


def check_adr_readme(root, base_sha, head, adr_dir, status_by_number):
    readme_rel = f"{adr_dir.rstrip('/')}/README.md"
    base_text = show_blob(root, base_sha, readme_rel)
    if base_text is None:
        return [], []  # base に一覧が無い→対象外

    errors = []
    warnings = []

    current_text = read_current(root, head, readme_rel)
    if current_text is None:
        errors.append(
            f"{readme_rel}: 一覧 README が削除されている。独立ファイル方式はファイルの削除を禁止する"
        )
        return errors, warnings

    current_rows = {}
    for header, rows in parse_tables(current_text):
        status_idx = next((i for i, h in enumerate(header) if h == "ステータス"), None)
        for cells in rows:
            if cells:
                current_rows[row_key(cells)] = (cells, status_idx)

    for header, rows in parse_tables(base_text):
        status_idx = next((i for i, h in enumerate(header) if h == "ステータス"), None)
        for base_cells in rows:
            if not base_cells:
                continue
            key = row_key(base_cells)
            if key not in current_rows:
                errors.append(
                    f"{readme_rel}: 一覧の行が削除されている（{base_cells[0]}）。"
                    "独立ファイル方式は一覧の行の削除を禁止する"
                )
                continue
            current_cells, _ = current_rows[key]
            for idx in range(max(len(base_cells), len(current_cells))):
                b = base_cells[idx] if idx < len(base_cells) else None
                c = current_cells[idx] if idx < len(current_cells) else None
                if b == c:
                    continue
                if status_idx is not None and idx == status_idx:
                    continue  # ステータス列の変更は許可
                warnings.append(
                    f"{readme_rel}: 一覧の行（{key}）の {idx + 1} 列目が変わっている。"
                    "ステータス列以外の変更は誤字修正に限る\n"
                    f"      - base:  {b}\n      + 現在:  {c}"
                )

    # F5: ステータス列と ADR 本体のステータス節の食い違いは、base に無い新規行も含めた
    # 現在の README の全行について検査する。
    for key, (current_cells, status_idx) in current_rows.items():
        if status_idx is None or status_idx >= len(current_cells):
            continue
        readme_status = current_cells[status_idx]
        adr_status = status_by_number.get(key)
        if adr_status is not None and readme_status != adr_status:
            warnings.append(
                f"{readme_rel}: 一覧のステータス列（{key}）が ADR 本体のステータス節と"
                f"食い違っている（README: {readme_status!r} / ADR: {adr_status!r}）"
            )

    return errors, warnings


def check_adr_dir_layout(root, base_sha, head, adr_dir):
    """独立ファイル方式はフラット配置（`.md` ファイルのみ、サブディレクトリ無し）を
    前提にする。前提から外れるエントリ（README.md を除く）があれば、検査対象外になる
    旨を警告する。base にあったそれらの削除も同様に警告する（検査対象外だったために
    その削除を本来の仕組みでは検出できないため）。
    """

    def irregular_names(entries):
        names = set()
        for name, kind in entries:
            if name == "README.md":
                continue
            if kind != "blob" or not name.endswith(".md"):
                names.add(name)
        return names

    base_irregular = irregular_names(list_dir_tree_entries(root, base_sha, adr_dir))
    current_irregular = irregular_names(list_current_dir_entries(root, head, adr_dir))

    warnings = []
    for name in sorted(current_irregular):
        warnings.append(
            f"{adr_dir}/{name}: 独立ファイル方式が前提とするフラット配置（.md ファイルのみ）"
            "から外れている。検査対象外になる"
        )
    for name in sorted(base_irregular - current_irregular):
        warnings.append(
            f"{adr_dir}/{name}: フラット配置から外れていた（検査対象外の）ファイル・"
            "ディレクトリが削除されている。検査対象外だったため、この削除自体は検出できない"
        )
    return warnings


# --- main ----------------------------------------------------------------------


def resolve_base_ref(root, base_arg):
    if base_arg is not None:
        proc = run_git(root, "rev-parse", "--verify", "--quiet", f"{base_arg}^{{commit}}")
        if proc.returncode != 0:
            return None
        return base_arg
    for candidate in ("origin/main", "main"):
        proc = run_git(root, "rev-parse", "--verify", "--quiet", f"{candidate}^{{commit}}")
        if proc.returncode == 0:
            return candidate
    return None


def main(argv):
    parser = argparse.ArgumentParser(
        prog="check-decision-log.py",
        description="決定ログ（独立ファイル方式・インライン方式）の不変性を機械検査する。",
    )
    parser.add_argument("--dir", default="knowledge", help="インライン方式の対象ディレクトリ（既定: knowledge）")
    parser.add_argument(
        "--adr-dir", default="knowledge/adr",
        help="独立ファイル方式の ADR ディレクトリ（既定: knowledge/adr）",
    )
    parser.add_argument("--base", default=None, help="比較の基準 ref（既定: origin/main、無ければ main）")
    parser.add_argument("--head", default=None, help="比較対象のコミット（省略時は作業ツリーと比較）")
    parser.add_argument("--warn-only", action="store_true", help="違反（error）があっても exit 0 にする")
    args = parser.parse_args(argv)

    root = repo_root()

    base_ref = resolve_base_ref(root, args.base)
    if base_ref is None:
        if args.base is not None:
            print(f"✗ 比較の基準 ref を解決できない: {args.base}", file=sys.stderr)
        else:
            print("✗ 比較の基準 ref が見つからない（origin/main・main のいずれも無い）", file=sys.stderr)
        return 2

    head_for_mb = args.head if args.head else "HEAD"
    mb_proc = run_git(root, "merge-base", head_for_mb, base_ref)
    if mb_proc.returncode != 0 or not mb_proc.stdout.strip():
        print(
            f"✗ merge-base を解決できない（{head_for_mb} と {base_ref}）。"
            "shallow clone や履歴不足の可能性がある",
            file=sys.stderr,
        )
        return 2
    base_sha = mb_proc.stdout.strip()

    head = args.head
    dir_ = args.dir.rstrip("/")
    adr_dir = args.adr_dir.rstrip("/")

    errors = []
    warnings = []

    path_renames = detect_path_renames(root, base_sha, head)
    inline_checked, inline_errors = check_inline_method(root, base_sha, head, dir_, adr_dir, path_renames)
    errors.extend(inline_errors)

    adr_checked = 0
    if path_exists_at(root, base_sha, adr_dir):
        adr_checked, adr_errors, adr_warnings, status_by_number = check_adr_method(
            root, base_sha, head, adr_dir
        )
        errors.extend(adr_errors)
        warnings.extend(adr_warnings)
        readme_errors, readme_warnings = check_adr_readme(
            root, base_sha, head, adr_dir, status_by_number
        )
        errors.extend(readme_errors)
        warnings.extend(readme_warnings)
        warnings.extend(check_adr_dir_layout(root, base_sha, head, adr_dir))

    for w in warnings:
        print(f"⚠ {w}", file=sys.stderr)

    if errors:
        print("", file=sys.stderr)
        for e in errors:
            print(f"✗ {e}", file=sys.stderr)
        print("", file=sys.stderr)
        print(f"✗ 決定ログの不変性違反 {len(errors)} 件（base={base_sha[:7]}）", file=sys.stderr)
        return 0 if args.warn_only else 1

    print(f"✓ 決定ログの不変性を確認（インライン {inline_checked} 本、ADR {adr_checked} 本）")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
