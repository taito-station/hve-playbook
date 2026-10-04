#!/usr/bin/env python3
"""決定ログ（knowledge/ の append-only な決定の記録）の不変性を機械検査する（#27）。

`rules/hve/artifact-management.md`「決定ログの不変性」が定める 2 方式を、方式の宣言
なしに自動判定して検査する:

- **独立ファイル方式（既定）**: `--adr-dir`（既定 `knowledge/adr`）が base コミット時点
  で存在するリポジトリに適用する。base にあった ADR ファイル（README.md を除く）は
  削除・改名を禁止し、`## ステータス` 節を除いた全文の一致を求める（節の外の変更は
  機械では誤字修正か判定できないため error ではなく警告にする）。一覧 `README.md` は
  base にあった行の削除を禁止し、ステータス列以外の変更を警告、ステータス列の変更は
  許可する（ただし ADR 本体のステータス節の値と食い違えば警告）。
- **インライン方式**: `--dir`（既定 `knowledge`）配下を再帰的に見て、base 側で
  `## 決定ログ` 見出し（コードフェンスの外）を持つ `.md` を対象にする。base 時点の
  節の内容が、現在の節の先頭に一致する（prefix）ことだけを求める。末尾への追記だけが
  許され、既存行の変更・削除・途中への挿入・節や文書そのものの削除は error になる。
  ディレクトリの付け替えに伴う、節内のパス参照の置換は許容する。

比較は `git merge-base <head> <base-ref>`（既定 `<base-ref>` = `origin/main`、無ければ
`main`）を基準に行う。`--head <commit>` を渡すとそのコミットの内容と比較し、渡さない
ときは作業ツリー（未コミットの変更を含む）と比較する。merge-base が解決できない
（ref が無い・shallow clone で履歴が足りない等）ときは、違反の有無を判定できないので
exit 2 にする（違反なしとして通さない）。

git の出力は `-c core.quotePath=false -c diff.noprefix=false -c diff.mnemonicPrefix=false`
で固定し、diff を使う箇所は `--no-ext-diff --no-textconv --no-color --text` を付ける。
内容の比較は `git diff` の文字列出力ではなく `git show <commit>:<path>`（または作業
ツリーのバイト列）を読んで行うため、`diff.external` / textconv の設定に影響されない。
リネーム検出（`-M`）は、インライン方式のディレクトリ付け替えの許容判定と、独立ファイル
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
    """`<commit>:<rel>` の内容を返す。存在しなければ None。"""
    proc = subprocess.run(
        ["git", *GIT_CONFIG_ARGS, "show", f"{commit}:{rel}"],
        cwd=str(root),
        capture_output=True,
    )
    if proc.returncode != 0:
        return None
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
    proc = run_git(root, "ls-tree", commit, "--", rel)
    return bool(proc.stdout.strip())


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

    返り値は (旧文字列, 新文字列) のリスト（長い順）。base の行に適用して現在の行と
    一致すれば「パスリネームのみの変更」と判定できる。相対リンク（``../old-dir/``）に
    対応するため、共通プレフィックスを除いた末尾コンポーネントも置換ペアに含める。
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

    subs = []
    seen = set()
    for old_dir, new_dir in sorted(dir_renames):
        if (old_dir, new_dir) not in seen:
            subs.append((old_dir, new_dir))
            seen.add((old_dir, new_dir))
        old_parts = old_dir.split("/")
        new_parts = new_dir.split("/")
        common = 0
        for o, n in zip(old_parts, new_parts):
            if o == n:
                common += 1
            else:
                break
        if common < len(old_parts) and common < len(new_parts):
            old_suffix = "/".join(old_parts[common:])
            new_suffix = "/".join(new_parts[common:])
            if old_suffix != new_suffix and (old_suffix, new_suffix) not in seen:
                subs.append((old_suffix, new_suffix))
                seen.add((old_suffix, new_suffix))

    subs.sort(key=lambda p: len(p[0]), reverse=True)
    return subs


def apply_renames(line, renames):
    result = line
    for old, new in renames:
        result = result.replace(old, new)
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
        base_rest = strip_section(base_text, RE_STATUS_HEADING)
        current_rest = strip_section(current_text, RE_STATUS_HEADING)
        if base_rest != current_rest:
            diff = first_diff(base_rest, current_rest)
            if diff is not None:
                idx, b, c = diff
                warnings.append(
                    f"{rel}: `## ステータス` 節の外で内容が変わっている（誤字修正に限る）。"
                    f"{idx + 1} 行目相当\n"
                    f"      - base:  {b if b is not None else '(行が無い)'}\n"
                    f"      + 現在:  {c if c is not None else '(行が無い)'}"
                )

        status_by_number[number] = extract_status_value(current_text)
        checked += 1

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
            if status_idx is not None and status_idx < len(current_cells):
                readme_status = current_cells[status_idx]
                adr_status = status_by_number.get(key)
                if adr_status is not None and readme_status != adr_status:
                    warnings.append(
                        f"{readme_rel}: 一覧のステータス列（{key}）が ADR 本体のステータス節と"
                        f"食い違っている（README: {readme_status!r} / ADR: {adr_status!r}）"
                    )

    return errors, warnings


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
