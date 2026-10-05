#!/usr/bin/env python3
"""hve-scripts/check-knowledge.py の回帰テスト。

paddock の `scripts/check-doc-classes.py` が持つ stale 判定の汎用部分（frontmatter
メタデータだけの変更・リネーム・`uses:` ピン留め更新だけの変更をスキップする仕組み、
走査の予算超過・マージコミットの扱い）を移植した `check-knowledge.py` を、使い捨ての
git リポジトリ（fixture）を作って検証する。

`scripts/test-check-doc-classes.py` と同じ「自走式」（`def test_*()` + assert を
末尾の main() が集めて実行する）。pytest は使わない。stdlib のみ。

使い方:
  python3 tests/hve_scripts/test_check_knowledge.py
"""

from __future__ import annotations

import contextlib
import importlib.util
import io
import os
import re
import shutil
import subprocess
import sys
import tempfile
import types
from pathlib import Path

TARGET = Path(__file__).resolve().parents[2] / "hve-scripts" / "check-knowledge.py"

FIRST_ADR = "docs-original/0001-first.md"
WORKFLOW_REL = ".github/workflows/ci.yml"
PIN_OLD = "b" * 40
PIN_NEW = "c" * 40
PIN_RIVAL = "f" * 40

_NOTSET = object()


# --- git ヘルパー -----------------------------------------------------------


def run_git(repo: Path, *args: str) -> str:
    proc = subprocess.run(
        ["git", *args], cwd=repo, capture_output=True, text=True, check=True
    )
    return proc.stdout.strip()


def git_allow_fail(repo: Path, *args: str) -> "subprocess.CompletedProcess[str]":
    """`run_git` と違い失敗を許す（コンフリクトする `git merge` は非 0 を返す）。"""
    return subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True)


def commit_all(repo: Path, message: str) -> str:
    run_git(repo, "add", "-A")
    run_git(repo, "commit", "-q", "-m", message)
    return run_git(repo, "rev-parse", "--short", "HEAD")


def new_repo() -> Path:
    repo = Path(tempfile.mkdtemp(prefix="check-knowledge-test-"))
    run_git(repo, "init", "-q", "-b", "main")
    run_git(repo, "config", "user.email", "test@example.invalid")
    run_git(repo, "config", "user.name", "test")
    run_git(repo, "config", "commit.gpgsign", "false")
    # 改行コードを git に触らせない（グローバル設定の autocrlf/attributesFile の
    # 影響を受けると、CRLF を扱うケースが「nothing to commit」で化ける）。
    run_git(repo, "config", "core.autocrlf", "false")
    run_git(repo, "config", "core.safecrlf", "false")
    (repo / ".gitattributes").write_text("* -text\n", encoding="utf-8")
    (repo / "knowledge").mkdir(parents=True)
    (repo / "docs-original").mkdir(parents=True)
    (repo / FIRST_ADR).write_text("# 0001. 最初の一次資料\n\n本文。\n", encoding="utf-8")
    return repo


def check(repo: Path, *args: str) -> "tuple[int, str]":
    proc = subprocess.run(
        [sys.executable, str(TARGET), *args], cwd=repo, capture_output=True, text=True
    )
    return proc.returncode, proc.stdout + proc.stderr


def read_distilled_sha(repo: Path, rel: str) -> str:
    for line in (repo / rel).read_text(encoding="utf-8").splitlines():
        if line.startswith("distilled_from_sha:"):
            return line.split('"')[1]
    raise AssertionError(f"{rel} に distilled_from_sha が無い")


# --- フィクスチャ文書 ---------------------------------------------------------


def write_doc(
    repo: Path,
    rel: str,
    *,
    title: "object" = _NOTSET,
    status: "str | None" = "Confirmed",
    kind: "str | None" = "knowledge",
    sources: "list[str] | None | object" = _NOTSET,
    distilled_from_sha: "str | None | object" = _NOTSET,
    updated: "str | None" = "2026-10-04",
    body: str = "本文。\n",
) -> None:
    """knowledge 文書を書く。値を `None` にするとその項目を frontmatter から欠落させる。"""
    if title is _NOTSET:
        title = Path(rel).stem
    if sources is _NOTSET:
        sources = []
    if distilled_from_sha is _NOTSET:
        distilled_from_sha = "HEAD"

    lines = ["---"]

    def add_scalar(key: str, value: "str | None") -> None:
        if value is None:
            return
        if value == "" or key in ("distilled_from_sha", "updated"):
            # 空文字列は常にクォートする。`key:`（裸・空）は frontmatter パーサーが
            # ブロックリストの開始（`key:\n  - item`）と区別できず、別の構造に化ける。
            lines.append(f'{key}: "{value}"')
        else:
            lines.append(f"{key}: {value}")

    add_scalar("title", title)
    add_scalar("status", status)
    add_scalar("kind", kind)
    if sources is not None:
        lines.append("sources:")
        for s in sources:
            lines.append(f"  - {s}")
    add_scalar("distilled_from_sha", distilled_from_sha)
    add_scalar("updated", updated)
    lines.append("---")
    lines.append("")
    heading = title if isinstance(title, str) and title else Path(rel).stem
    lines.append(f"# {heading}")
    lines.append("")
    lines.append(body)

    path = repo / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def write_raw_frontmatter_doc(
    repo: Path, rel: str, frontmatter_lines: "list[str]", body: str = "本文。\n"
) -> None:
    """`write_doc` と違い frontmatter 行をそのまま書く（裸の `key:` や旧マップ形式を作るため。
    `write_doc` は空値を常にクォートするので、裸の `key:`（値なし）を作れない）。
    """
    lines = ["---", *frontmatter_lines, "---", "", body]
    path = repo / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def baseline(repo: Path) -> str:
    """1 文書（sources は FIRST_ADR）だけの、error 0 で通る状態を作って sha を返す。"""
    write_doc(repo, "knowledge/a.md", sources=[FIRST_ADR], distilled_from_sha="HEAD")
    sha = commit_all(repo, "baseline")
    write_doc(repo, "knowledge/a.md", sources=[FIRST_ADR], distilled_from_sha=sha)
    return commit_all(repo, "pin sha")


def write_workflow(repo: Path, pin: str = PIN_OLD, comment: str = "ピン留めの説明") -> None:
    path = repo / WORKFLOW_REL
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "name: CI\non: [push]\njobs:\n  build:\n    steps:\n"
        f"      # {comment}\n      - uses: dtolnay/rust-toolchain@{pin}\n",
        encoding="utf-8",
    )


def workflow_baseline(repo: Path) -> str:
    """a.md が sources に WORKFLOW_REL を持ち、error 0 で通る状態を作る。"""
    sha = baseline(repo)
    write_workflow(repo)
    write_doc(repo, "knowledge/a.md", sources=[WORKFLOW_REL, FIRST_ADR], distilled_from_sha=sha)
    added = commit_all(repo, "ワークフローを source にする")
    write_doc(repo, "knowledge/a.md", sources=[WORKFLOW_REL, FIRST_ADR], distilled_from_sha=added)
    commit_all(repo, "追従")
    assert check(repo)[0] == 0, "前提: ここでは error 0 で通る"
    return added


def load_checker(repo: Path) -> "types.ModuleType":
    """check-knowledge.py をモジュールとして読み込み、`_ROOT` を fixture に向ける。

    予算超過・git 失敗の注入テストは `last_content_change` を直接叩く必要があり、
    テストごとに読み込み直す（`lru_cache` のキーにリポジトリを含まないため、
    モジュールを共有すると別の一時リポの結果を引いてしまう）。
    """
    spec = importlib.util.spec_from_file_location("check_knowledge_under_test", TARGET)
    assert spec is not None and spec.loader is not None, TARGET
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module._ROOT = repo
    return module


# --- 基本の正常系・必須項目 ---------------------------------------------------


def test_valid_fixture_passes() -> None:
    repo = new_repo()
    try:
        baseline(repo)
        code, out = check(repo)
        assert code == 0, out
        assert "✓" in out, out
    finally:
        shutil.rmtree(repo)


def test_missing_required_field_is_error() -> None:
    repo = new_repo()
    try:
        sha = baseline(repo)
        write_doc(repo, "knowledge/a.md", status=None,
                  sources=[FIRST_ADR], distilled_from_sha=sha)
        commit_all(repo, "status を欠落させる")
        code, out = check(repo)
        assert code == 1, out
        assert "knowledge/a.md: 必須項目 status が無い" in out, out
    finally:
        shutil.rmtree(repo)


def test_empty_string_required_field_is_error() -> None:
    """値が空文字列（キーはあるが空）の場合も必須項目違反として検出する。"""
    repo = new_repo()
    try:
        sha = baseline(repo)
        write_doc(repo, "knowledge/a.md", kind="", sources=[FIRST_ADR], distilled_from_sha=sha)
        commit_all(repo, "kind を空にする")
        code, out = check(repo)
        assert code == 1, out
        assert "knowledge/a.md: 必須項目 kind が空" in out, out
    finally:
        shutil.rmtree(repo)


def test_custom_required_list_is_honored() -> None:
    """--required を絞ると、絞った項目以外は欠落していても error にならない。"""
    repo = new_repo()
    try:
        sha = baseline(repo)
        write_doc(repo, "knowledge/a.md", status=None,
                  sources=[FIRST_ADR], distilled_from_sha=sha)
        commit_all(repo, "status を欠落させる")
        code, out = check(repo, "--required", "sources,distilled_from_sha")
        assert code == 0, out
        assert "必須項目" not in out, out
    finally:
        shutil.rmtree(repo)


# --- F1/F3: 空リスト（裸の key:）・distilled_from_sha の形式 -------------------


def test_bare_distilled_from_sha_is_empty_error() -> None:
    """裸の `distilled_from_sha:`（値なし）は parser 上は空リストになるが「空」として検出する。"""
    repo = new_repo()
    try:
        baseline(repo)
        write_raw_frontmatter_doc(
            repo, "knowledge/b.md",
            [
                "title: b",
                "status: Confirmed",
                "kind: knowledge",
                "sources:",
                f"  - {FIRST_ADR}",
                "distilled_from_sha:",
                'updated: "2026-10-04"',
            ],
        )
        commit_all(repo, "distilled_from_sha を裸で書く")
        code, out = check(repo)
        assert code == 1, out
        assert "knowledge/b.md: 必須項目 distilled_from_sha が空" in out, out
        assert "形式が不正" not in out, out
    finally:
        shutil.rmtree(repo)


def test_bare_title_is_empty_error() -> None:
    """裸の `title:`（値なし）も同様に「空」として検出する。"""
    repo = new_repo()
    try:
        sha = baseline(repo)
        write_raw_frontmatter_doc(
            repo, "knowledge/b.md",
            [
                "title:",
                "status: Confirmed",
                "kind: knowledge",
                "sources:",
                f"  - {FIRST_ADR}",
                f'distilled_from_sha: "{sha}"',
                'updated: "2026-10-04"',
            ],
        )
        commit_all(repo, "title を裸で書く")
        code, out = check(repo)
        assert code == 1, out
        assert "knowledge/b.md: 必須項目 title が空" in out, out
    finally:
        shutil.rmtree(repo)


def test_old_map_format_distilled_from_sha_is_error() -> None:
    """旧標準の source ごとのマップ形式（ADR 0014 で廃止）は形式エラーにする。"""
    repo = new_repo()
    try:
        baseline(repo)
        write_raw_frontmatter_doc(
            repo, "knowledge/b.md",
            [
                "title: b",
                "status: Confirmed",
                "kind: knowledge",
                "sources:",
                f"  - {FIRST_ADR}",
                "distilled_from_sha:",
                f"  {FIRST_ADR}: abcdef1234567890",
                'updated: "2026-10-04"',
            ],
        )
        commit_all(repo, "distilled_from_sha を旧マップ形式で書く")
        code, out = check(repo)
        assert code == 1, out
        assert "distilled_from_sha の形式が不正" in out, out
        assert "ADR 0014" in out, out
        assert "必須項目 distilled_from_sha が空" not in out, out
    finally:
        shutil.rmtree(repo)


def test_list_format_distilled_from_sha_is_error() -> None:
    """`distilled_from_sha` が list 形式（ブロックリスト）でも形式エラーにする。"""
    repo = new_repo()
    try:
        baseline(repo)
        write_raw_frontmatter_doc(
            repo, "knowledge/b.md",
            [
                "title: b",
                "status: Confirmed",
                "kind: knowledge",
                "sources:",
                f"  - {FIRST_ADR}",
                "distilled_from_sha:",
                "  - abcdef1",
                'updated: "2026-10-04"',
            ],
        )
        commit_all(repo, "distilled_from_sha を list 形式で書く")
        code, out = check(repo)
        assert code == 1, out
        assert "distilled_from_sha の形式が不正" in out, out
    finally:
        shutil.rmtree(repo)


def test_distilled_from_sha_mutable_ref_is_error() -> None:
    """`HEAD` / `main` のような可変参照は stale 判定を無効化するので error にする。"""
    repo = new_repo()
    try:
        baseline(repo)
        for bad in ("HEAD", "main"):
            write_doc(repo, "knowledge/b.md", sources=[FIRST_ADR], distilled_from_sha=bad)
            commit_all(repo, f"distilled_from_sha を {bad} にする")
            code, out = check(repo)
            assert code == 1, out
            assert "sha 形式でない" in out, out
    finally:
        shutil.rmtree(repo)


def test_distilled_from_sha_invalid_hex_format_is_error() -> None:
    """大文字 16 進・6 桁（7 桁未満）は正規表現に合わないので error にする。"""
    repo = new_repo()
    try:
        baseline(repo)
        for bad in ("ABCDEF1", "abcdef"):
            write_doc(repo, "knowledge/b.md", sources=[FIRST_ADR], distilled_from_sha=bad)
            commit_all(repo, f"distilled_from_sha を {bad} にする")
            code, out = check(repo)
            assert code == 1, out
            assert "sha 形式でない" in out, out
    finally:
        shutil.rmtree(repo)


def test_distilled_from_sha_seven_and_forty_digit_hex_pass() -> None:
    """7 桁・40 桁の小文字 16 進は正規表現に合うので通る（境界値）。"""
    repo = new_repo()
    try:
        baseline(repo)
        full_sha = run_git(repo, "rev-parse", "HEAD")
        write_doc(repo, "knowledge/a.md", sources=[FIRST_ADR], distilled_from_sha=full_sha[:7])
        commit_all(repo, "7 桁の sha にする")
        code, out = check(repo)
        assert code == 0, out

        full_sha2 = run_git(repo, "rev-parse", "HEAD")
        write_doc(repo, "knowledge/a.md", sources=[FIRST_ADR], distilled_from_sha=full_sha2)
        commit_all(repo, "40 桁の sha にする")
        code, out = check(repo)
        assert code == 0, out
    finally:
        shutil.rmtree(repo)


# --- sources の実在・正規形・大文字小文字 ------------------------------------


def test_missing_source_file_is_error() -> None:
    repo = new_repo()
    try:
        sha = baseline(repo)
        write_doc(repo, "knowledge/a.md", sources=["docs-original/9999-nope.md"],
                  distilled_from_sha=sha)
        commit_all(repo, "実在しない source を指す")
        code, out = check(repo)
        assert code == 1, out
        assert "sources のパスが実在しない" in out, out
    finally:
        shutil.rmtree(repo)


def test_noncanonical_source_is_error() -> None:
    repo = new_repo()
    try:
        sha = baseline(repo)
        write_doc(repo, "knowledge/a.md", sources=["./" + FIRST_ADR], distilled_from_sha=sha)
        commit_all(repo, "非正規形の source を指す")
        code, out = check(repo)
        assert code == 1, out
        assert "sources は正規形で書く" in out, out
    finally:
        shutil.rmtree(repo)


def test_absolute_source_path_is_error() -> None:
    repo = new_repo()
    try:
        sha = baseline(repo)
        write_doc(repo, "knowledge/a.md", sources=["/etc/hosts"], distilled_from_sha=sha)
        commit_all(repo, "絶対パスの source を指す")
        code, out = check(repo)
        assert code == 1, out
        assert "リポジトリ相対パスで書く" in out, out
    finally:
        shutil.rmtree(repo)


def test_parent_traversal_source_is_error() -> None:
    repo = new_repo()
    try:
        sha = baseline(repo)
        write_doc(repo, "knowledge/a.md", sources=["docs-original/../docs-original/0001-first.md"],
                  distilled_from_sha=sha)
        commit_all(repo, "親ディレクトリ参照の source を指す")
        code, out = check(repo)
        assert code == 1, out
        assert "リポジトリ相対パスで書く" in out, out
    finally:
        shutil.rmtree(repo)


def test_source_case_mismatch_is_error() -> None:
    repo = new_repo()
    try:
        sha = baseline(repo)
        write_doc(repo, "knowledge/a.md", sources=["docs-original/0001-FIRST.md"],
                  distilled_from_sha=sha)
        commit_all(repo, "大文字小文字違いの source を指す")
        code, out = check(repo)
        assert code == 1, out
        if (repo / "docs-original/0001-FIRST.md").exists():
            # 大文字小文字を区別しない FS（macOS）。区別する FS では実在しない側に落ちる。
            assert "sources の大文字小文字が実ファイルと違う" in out, out
        else:
            assert "sources のパスが実在しない" in out, out
    finally:
        shutil.rmtree(repo)


def test_source_symlink_outside_repo_is_error() -> None:
    """F14/G5: symlink はリポジトリの外を指していても error にする。"""
    repo = new_repo()
    outside_dir = Path(tempfile.mkdtemp(prefix="check-knowledge-outside-"))
    try:
        sha = baseline(repo)
        outside_file = outside_dir / "secret.md"
        outside_file.write_text("外部ファイル\n", encoding="utf-8")
        link = repo / "docs-original" / "escape.md"
        os.symlink(outside_file, link)
        write_doc(repo, "knowledge/a.md", sources=["docs-original/escape.md"],
                  distilled_from_sha=sha)
        commit_all(repo, "symlink で外部ファイルを source にする")
        code, out = check(repo)
        assert code == 1, out
        assert "sources にシンボリックリンクは使えない" in out, out
    finally:
        shutil.rmtree(repo)
        shutil.rmtree(outside_dir, ignore_errors=True)


def test_source_symlink_inside_repo_is_error() -> None:
    """G5: symlink の解決先がリポジトリの中（実在するファイル）でも error にする。

    stale 判定（last_content_change）はリンクのパスではなく指し先の履歴を追えない
    ため、リポジトリ内を指す symlink も免除しない。
    """
    repo = new_repo()
    try:
        sha = baseline(repo)
        link = repo / "docs-original" / "inside-link.md"
        os.symlink(repo / FIRST_ADR, link)
        write_doc(repo, "knowledge/a.md", sources=["docs-original/inside-link.md"],
                  distilled_from_sha=sha)
        commit_all(repo, "リポジトリ内を指す symlink を source にする")
        code, out = check(repo)
        assert code == 1, out
        assert "sources にシンボリックリンクは使えない。実体のパスを書く" in out, out
    finally:
        shutil.rmtree(repo)


# --- 空 sources ---------------------------------------------------------------


def test_empty_sources_is_error_by_default() -> None:
    repo = new_repo()
    try:
        baseline(repo)
        write_doc(repo, "knowledge/b.md", sources=[], distilled_from_sha=None)
        commit_all(repo, "sources が空の文書を追加")
        code, out = check(repo)
        assert code == 1, out
        assert "knowledge/b.md: sources が空（由来を辿れない）" in out, out
    finally:
        shutil.rmtree(repo)


def test_empty_sources_allowed_with_decision_log_flag() -> None:
    repo = new_repo()
    try:
        baseline(repo)
        write_doc(repo, "knowledge/b.md", sources=[], distilled_from_sha=None,
                  body="## 決定ログ\n\n内容は省略。\n")
        commit_all(repo, "決定ログのみの文書を追加")
        code, out = check(repo, "--allow-empty-sources-with-decision-log")
        assert code == 0, out
        assert "sources が空" not in out, out
        assert "必須項目 distilled_from_sha" not in out, out
        assert "必須項目 sources" not in out, out
    finally:
        shutil.rmtree(repo)


def test_flag_does_not_exempt_sources_without_sha() -> None:
    """免除は sources と sha が揃って空のときだけ。sources があって sha が無ければ error。"""
    repo = new_repo()
    try:
        baseline(repo)
        write_doc(repo, "knowledge/b.md", sources=[FIRST_ADR], distilled_from_sha=None,
                  body="## 決定ログ\n\n内容は省略。\n")
        commit_all(repo, "sources だけある文書を追加")
        code, out = check(repo, "--allow-empty-sources-with-decision-log")
        assert code == 1, out
        assert "sources があるのに distilled_from_sha が無い" in out, out
    finally:
        shutil.rmtree(repo)


def test_flag_without_decision_log_heading_still_errors() -> None:
    """フラグを付けても `## 決定ログ` 見出しが無ければ免除されない。"""
    repo = new_repo()
    try:
        baseline(repo)
        write_doc(repo, "knowledge/b.md", sources=[], distilled_from_sha=None)
        commit_all(repo, "決定ログ見出しが無い文書を追加")
        code, out = check(repo, "--allow-empty-sources-with-decision-log")
        assert code == 1, out
        assert "sources が空" in out, out
    finally:
        shutil.rmtree(repo)


def test_decision_log_heading_with_multiple_spaces_or_tab_is_recognized() -> None:
    """G14: 見出し判定を check-decision-log.py に揃え、`##` と `決定ログ` の間の
    空白が 1 個の半角スペースに限らなくても認識する。
    """
    repo = new_repo()
    try:
        baseline(repo)
        write_doc(repo, "knowledge/b.md", sources=[], distilled_from_sha=None,
                  body="##  決定ログ\n\n内容は省略。\n")
        commit_all(repo, "決定ログ見出しの空白を 2 個にする")
        code, out = check(repo, "--allow-empty-sources-with-decision-log")
        assert code == 0, out
        assert "sources が空" not in out, out
    finally:
        shutil.rmtree(repo)


def test_decision_log_heading_inside_fence_is_ignored() -> None:
    """コードフェンス内の `## 決定ログ` は見出しとして数えない（免除されない）。"""
    repo = new_repo()
    try:
        baseline(repo)
        write_doc(repo, "knowledge/b.md", sources=[], distilled_from_sha=None,
                  body="```markdown\n## 決定ログ\n```\n")
        commit_all(repo, "フェンス内にだけ見出しがある文書を追加")
        code, out = check(repo, "--allow-empty-sources-with-decision-log")
        assert code == 1, out
        assert "sources が空" in out, out
    finally:
        shutil.rmtree(repo)


# --- Conflict（解消待ち） -----------------------------------------------------


def test_conflict_status_is_pending_not_error() -> None:
    repo = new_repo()
    try:
        baseline(repo)
        p = repo / FIRST_ADR
        p.write_text(p.read_text(encoding="utf-8") + "\n追記。\n", encoding="utf-8")
        commit_all(repo, "source を実質更新")
        sha_before = read_distilled_sha(repo, "knowledge/a.md")
        write_doc(repo, "knowledge/a.md", status="Conflict",
                  sources=[FIRST_ADR], distilled_from_sha=sha_before)
        commit_all(repo, "Conflict へ変更")
        code, out = check(repo)
        assert code == 0, out
        assert "STALE" not in out, out
        assert "解消待ち 1 件" in out, out
        assert "解消待ち: knowledge/a.md（status: Conflict）" in out, out
    finally:
        shutil.rmtree(repo)


def test_conflict_does_not_suppress_source_existence_check() -> None:
    """Conflict でも sources の実在検査は独立して効く（stale だけが免除される）。"""
    repo = new_repo()
    try:
        baseline(repo)
        write_doc(repo, "knowledge/a.md", status="Conflict",
                  sources=["docs-original/9999-nope.md"], distilled_from_sha="deadbeef")
        commit_all(repo, "Conflict だが sources が壊れている")
        code, out = check(repo)
        assert code == 1, out
        assert "sources のパスが実在しない" in out, out
    finally:
        shutil.rmtree(repo)


def test_summary_shows_zero_pending_count() -> None:
    repo = new_repo()
    try:
        baseline(repo)
        code, out = check(repo)
        assert code == 0, out
        assert "解消待ち 0 件" in out, out
    finally:
        shutil.rmtree(repo)


# --- 再帰・除外 ----------------------------------------------------------------


def test_recursive_scan_and_exclude() -> None:
    repo = new_repo()
    try:
        sha = baseline(repo)
        # サブディレクトリの文書も再帰で検査する
        write_doc(repo, "knowledge/sub/nested.md", title=None,
                  sources=[FIRST_ADR], distilled_from_sha=sha)
        # 既定の除外対象（adr/・README.md）は壊れていても無視される
        (repo / "knowledge/adr").mkdir(parents=True, exist_ok=True)
        (repo / "knowledge/adr/0001-x.md").write_text("壊れた ADR\n", encoding="utf-8")
        (repo / "knowledge/README.md").write_text("壊れた README\n", encoding="utf-8")
        commit_all(repo, "再帰対象とデフォルト除外を追加")
        code, out = check(repo)
        assert code == 1, out
        assert "knowledge/sub/nested.md: 必須項目 title が無い" in out, out
        assert "adr/0001-x.md" not in out, out
        assert "knowledge/README.md" not in out, out
    finally:
        shutil.rmtree(repo)


def test_custom_exclude_pattern_is_honored() -> None:
    repo = new_repo()
    try:
        baseline(repo)
        write_doc(repo, "knowledge/draft/wip.md", title=None,
                  sources=[], distilled_from_sha=None)
        commit_all(repo, "除外対象にする文書を追加")
        code, out = check(repo, "--exclude", "draft/")
        assert code == 0, out
        assert "draft/wip.md" not in out, out
    finally:
        shutil.rmtree(repo)


def test_missing_target_directory_exits_2() -> None:
    """F19: `--dir` を明示指定してそれが無い場合は従来どおり exit 2。"""
    repo = new_repo()
    try:
        baseline(repo)
        code, out = check(repo, "--dir", "does-not-exist")
        assert code == 2, out
    finally:
        shutil.rmtree(repo)


def test_default_dir_missing_exits_zero_with_zero_targets() -> None:
    """F19: `--dir` を明示しなかったとき、既定の knowledge/ が無ければ対象 0 本で exit 0。"""
    repo = new_repo()
    try:
        shutil.rmtree(repo / "knowledge")
        code, out = check(repo)
        assert code == 0, out
        assert "0 本" in out, out
        assert "knowledge/ が無いので対象なし" in out, out
    finally:
        shutil.rmtree(repo)


# --- shallow clone / --warn-only / 短縮 sha -----------------------------------


def test_shallow_clone_exits_2() -> None:
    repo = new_repo()
    shallow_dir = Path(tempfile.mkdtemp(prefix="check-knowledge-shallow-"))
    try:
        baseline(repo)
        p = repo / FIRST_ADR
        p.write_text(p.read_text(encoding="utf-8") + "\n追記。\n", encoding="utf-8")
        commit_all(repo, "2 つ目のコミット")
        dest = shallow_dir / "clone"
        subprocess.run(
            ["git", "clone", "-q", "--depth", "1", f"file://{repo}", str(dest)],
            capture_output=True, text=True, check=True,
        )
        assert run_git(dest, "rev-parse", "--is-shallow-repository") == "true"
        code, out = check(dest)
        assert code == 2, out
        assert "fetch-depth: 0" in out, out
    finally:
        shutil.rmtree(repo)
        shutil.rmtree(shallow_dir, ignore_errors=True)


def test_warn_only_downgrades_errors_to_exit_zero() -> None:
    repo = new_repo()
    try:
        sha = baseline(repo)
        write_doc(repo, "knowledge/a.md", sources=["docs-original/9999-nope.md"],
                  distilled_from_sha=sha)
        commit_all(repo, "実在しない source")
        code, out = check(repo, "--warn-only")
        assert code == 0, out
        assert "sources のパスが実在しない" in out, out
        assert "--warn-only のため 0 で終了する" in out, out
    finally:
        shutil.rmtree(repo)


def test_warn_only_does_not_downgrade_shallow_exit() -> None:
    repo = new_repo()
    shallow_dir = Path(tempfile.mkdtemp(prefix="check-knowledge-shallow-warn-"))
    try:
        baseline(repo)
        p = repo / FIRST_ADR
        p.write_text(p.read_text(encoding="utf-8") + "\n追記。\n", encoding="utf-8")
        commit_all(repo, "2 つ目のコミット")
        dest = shallow_dir / "clone"
        subprocess.run(
            ["git", "clone", "-q", "--depth", "1", f"file://{repo}", str(dest)],
            capture_output=True, text=True, check=True,
        )
        code, out = check(dest, "--warn-only")
        assert code == 2, f"--warn-only で判定不能まで 0 に落としている: {out}"
    finally:
        shutil.rmtree(repo)
        shutil.rmtree(shallow_dir, ignore_errors=True)


def test_short_sha_is_accepted() -> None:
    repo = new_repo()
    try:
        baseline(repo)
        full_sha = run_git(repo, "rev-parse", "HEAD")
        short_sha = full_sha[:8]
        write_doc(repo, "knowledge/a.md", sources=[FIRST_ADR], distilled_from_sha=short_sha)
        commit_all(repo, "短縮 sha を使う")
        code, out = check(repo)
        assert code == 0, out
    finally:
        shutil.rmtree(repo)


def test_unresolvable_sha_on_full_clone_is_error() -> None:
    """full clone で distilled_from_sha を解決できないのは（shallow ではないので）error。"""
    repo = new_repo()
    try:
        baseline(repo)
        write_doc(repo, "knowledge/a.md", sources=[FIRST_ADR], distilled_from_sha="deadbee")
        commit_all(repo, "解決できない sha にする")
        code, out = check(repo)
        assert code == 1, out
        assert "を解決できない" in out, out
    finally:
        shutil.rmtree(repo)


def test_distilled_from_sha_resolving_to_same_named_ref_is_error() -> None:
    """G6: 書いた値と同名の tag・branch に解決された場合は error にする。

    7 桁の hex に見える値をそのまま tag 名にできる（`rev-parse --verify` は ref 名も
    受け付けるため）。tag の指す commit が無関係なら、解決したフル sha は書いた値で
    始まらない。
    """
    repo = new_repo()
    try:
        baseline(repo)
        run_git(repo, "tag", "abc1234", "HEAD")
        write_doc(repo, "knowledge/b.md", sources=[FIRST_ADR], distilled_from_sha="abc1234")
        commit_all(repo, "distilled_from_sha を tag と同名にする")
        code, out = check(repo)
        assert code == 1, out
        assert "distilled_from_sha が同名の ref（tag・branch）に解決された" in out, out
    finally:
        shutil.rmtree(repo)


def test_invalid_format_distilled_from_sha_does_not_double_report() -> None:
    """G15: 形式が不正な値は「形式不正」と「解決できない」を二重報告しない。"""
    repo = new_repo()
    try:
        baseline(repo)
        write_doc(repo, "knowledge/b.md", sources=[FIRST_ADR], distilled_from_sha="ABCDEF1")
        commit_all(repo, "distilled_from_sha を不正な形式にする")
        code, out = check(repo)
        assert code == 1, out
        assert "sha 形式でない" in out, out
        assert "を解決できない" not in out, out
    finally:
        shutil.rmtree(repo)


def test_help_flag_exits_zero() -> None:
    repo = new_repo()
    try:
        baseline(repo)
        assert check(repo, "-h")[0] == 0
        assert check(repo, "--help")[0] == 0
    finally:
        shutil.rmtree(repo)


def test_unknown_argument_exits_2() -> None:
    repo = new_repo()
    try:
        baseline(repo)
        code, out = check(repo, "--no-such-flag")
        assert code == 2, out
    finally:
        shutil.rmtree(repo)


# --- STALE 行の書式（パース契約） ---------------------------------------------


def test_stale_line_format() -> None:
    repo = new_repo()
    try:
        baseline(repo)
        p = repo / FIRST_ADR
        p.write_text(p.read_text(encoding="utf-8") + "\n追記。\n", encoding="utf-8")
        commit_all(repo, "source を実質更新")
        code, out = check(repo)
        assert code == 1, out
        pattern = re.compile(
            r"✗ knowledge/a\.md: STALE ← docs-original/0001-first\.md が "
            r"distilled_from_sha\([0-9a-f]+\) より後に更新されている"
            r"（[0-9a-f]{7}）。差分マージして sha/日付を更新する"
        )
        assert pattern.search(out), out
    finally:
        shutil.rmtree(repo)


# --- stale 判定: リネーム・メタデータ -----------------------------------------


def test_rename_only_is_not_stale() -> None:
    """**最重要**: パス移動のみのコミットを stale と見なさない。"""
    repo = new_repo()
    try:
        baseline(repo)
        run_git(repo, "mv", FIRST_ADR, "docs-original/0001-moved.md")
        commit_all(repo, "パス移動のみ（内容不変）")
        sha_before = read_distilled_sha(repo, "knowledge/a.md")
        write_doc(repo, "knowledge/a.md", sources=["docs-original/0001-moved.md"],
                  distilled_from_sha=sha_before)
        commit_all(repo, "sources のパスを追従")
        code, out = check(repo)
        assert code == 0, out
        assert "STALE" not in out, f"rename-only を stale と誤判定した:\n{out}"
    finally:
        shutil.rmtree(repo)


def test_rename_chain_is_not_stale() -> None:
    """リネームが 2 回以上重なっても stale と誤判定しない。"""
    repo = new_repo()
    try:
        baseline(repo)
        for old, new in [("0001-first.md", "0001-r1.md"), ("0001-r1.md", "0001-r2.md")]:
            run_git(repo, "mv", f"docs-original/{old}", f"docs-original/{new}")
            commit_all(repo, f"パス移動のみ {old} -> {new}")
        sha_before = read_distilled_sha(repo, "knowledge/a.md")
        write_doc(repo, "knowledge/a.md", sources=["docs-original/0001-r2.md"],
                  distilled_from_sha=sha_before)
        commit_all(repo, "sources のパスを追従")
        code, out = check(repo)
        assert code == 0, out
        assert "STALE" not in out, f"2 段のリネームを stale と誤判定した:\n{out}"
        assert "履歴が無く" not in out, f"履歴を辿れなくなっている:\n{out}"
    finally:
        shutil.rmtree(repo)


def test_quoted_filename_source_is_still_detected_as_stale() -> None:
    """G7: `"` を含むファイル名でも終点一致が外れず STALE を検出する。

    `-z` なしの `git show --name-status` は `core.quotePath=false` でも二重引用符や
    バックスラッシュを含むファイル名を C クォートするため、素朴な文字列比較では
    `path_status` が一致を見つけられず、stale 判定が「履歴が無い」警告に落ちてしまう。
    """
    repo = new_repo()
    try:
        rel = 'docs-original/q"x.md'
        (repo / rel).write_text("内容\n", encoding="utf-8")
        commit_all(repo, "二重引用符を含む source を追加")
        sha = run_git(repo, "rev-parse", "HEAD")
        write_doc(repo, "knowledge/a.md", sources=[rel], distilled_from_sha=sha)
        commit_all(repo, "pin sha")
        assert check(repo)[0] == 0, "前提: ここでは stale でない"

        p = repo / rel
        p.write_text(p.read_text(encoding="utf-8") + "追記。\n", encoding="utf-8")
        commit_all(repo, "source を実質更新")
        code, out = check(repo)
        assert code == 1, out
        assert "STALE" in out, f"二重引用符を含むファイル名で stale 判定が外れた:\n{out}"
        assert "履歴が無く" not in out, out
    finally:
        shutil.rmtree(repo)


def test_frontmatter_only_change_in_source_is_not_stale() -> None:
    """source の frontmatter メタデータだけが変わった場合は stale にしない。"""
    repo = new_repo()
    try:
        baseline(repo)
        src = repo / FIRST_ADR
        body = src.read_text(encoding="utf-8")
        src.write_text('---\nstatus: Confirmed\ntags: [D01]\n---\n\n' + body, encoding="utf-8")
        sha = commit_all(repo, "source に frontmatter を付ける")
        write_doc(repo, "knowledge/a.md", sources=[FIRST_ADR], distilled_from_sha=sha)
        commit_all(repo, "pin sha")
        assert check(repo)[0] == 0, "前提: ここでは stale でない"

        src.write_text(
            src.read_text(encoding="utf-8").replace("tags: [D01]", "tags: [D01, D02]"),
            encoding="utf-8",
        )
        commit_all(repo, "source の tags だけ変更")
        code, out = check(repo)
        assert code == 0, out
        assert "STALE" not in out, f"frontmatter のみの変更を stale と誤判定した:\n{out}"
    finally:
        shutil.rmtree(repo)


def test_status_change_in_source_is_stale() -> None:
    """`status` は METADATA_KEYS から意図的に外している（下流に伝えるべき信号）。"""
    repo = new_repo()
    try:
        baseline(repo)
        src = repo / FIRST_ADR
        body = src.read_text(encoding="utf-8")
        src.write_text("---\nstatus: Confirmed\nkind: original\n---\n\n" + body, encoding="utf-8")
        sha = commit_all(repo, "source に frontmatter を付ける")
        write_doc(repo, "knowledge/a.md", sources=[FIRST_ADR], distilled_from_sha=sha)
        commit_all(repo, "pin sha")
        assert check(repo)[0] == 0, "前提: ここでは stale でない"

        src.write_text(
            "---\nstatus: Conflict\nkind: original\n---\n\n" + body, encoding="utf-8"
        )
        commit_all(repo, "source の status だけを Conflict にする")
        code, out = check(repo)
        assert code == 1, f"status の変更は stale にするべき: {out}"
        assert "STALE" in out, out
    finally:
        shutil.rmtree(repo)


def test_body_change_is_stale() -> None:
    repo = new_repo()
    try:
        baseline(repo)
        p = repo / FIRST_ADR
        p.write_text(p.read_text(encoding="utf-8") + "\n本文の追記。\n", encoding="utf-8")
        commit_all(repo, "本文を変更")
        code, out = check(repo)
        assert code == 1, out
        assert "STALE" in out, f"本文の変更を検出できていない:\n{out}"
    finally:
        shutil.rmtree(repo)


def test_untracked_source_is_warning_not_error() -> None:
    """履歴を辿れない source は判定不能。黙って通す（fail-open）のではなく可視化する。"""
    repo = new_repo()
    try:
        sha = baseline(repo)
        (repo / "docs-original/9999-untracked.md").write_text("# 未コミット\n", encoding="utf-8")
        write_doc(repo, "knowledge/a.md",
                  sources=[FIRST_ADR, "docs-original/9999-untracked.md"], distilled_from_sha=sha)
        code, out = check(repo)
        assert code == 0, f"判定不能は error にしない: {out}"
        assert "履歴が無く" in out, out
    finally:
        shutil.rmtree(repo)


# --- stale 判定: `uses:` ピン留めだけの変更 ------------------------------------


def test_pin_hex_only_change_is_not_stale() -> None:
    repo = new_repo()
    try:
        workflow_baseline(repo)
        write_workflow(repo, pin=PIN_NEW)
        commit_all(repo, "ピンを更新")
        code, out = check(repo)
        assert code == 0, out
        assert "STALE" not in out, f"ピン hex のみの更新を stale と誤判定した:\n{out}"
    finally:
        shutil.rmtree(repo)


def test_pin_comment_only_change_is_stale() -> None:
    """対照: hex が動かない変更（注記だけ）は免除しない。"""
    repo = new_repo()
    try:
        workflow_baseline(repo)
        write_workflow(repo, comment="注記だけ書き換え")
        commit_all(repo, "注記だけ変更")
        code, out = check(repo)
        assert code == 1, out
        assert "STALE" in out, f"hex 不変の注記変更を免除してしまっている:\n{out}"
    finally:
        shutil.rmtree(repo)


def test_pin_change_in_non_workflow_yml_is_stale() -> None:
    """対照: ワークフロー以外の `.yml` は例外の対象外。"""
    repo = new_repo()
    try:
        sha = baseline(repo)
        rel = "deployments/compose.yml"
        (repo / rel).parent.mkdir(parents=True, exist_ok=True)
        (repo / rel).write_text(
            f"services:\n  a:\n    steps:\n      - uses: actions/checkout@{PIN_OLD}\n",
            encoding="utf-8",
        )
        write_doc(repo, "knowledge/a.md", sources=[rel, FIRST_ADR], distilled_from_sha=sha)
        added = commit_all(repo, "compose.yml を source にする")
        write_doc(repo, "knowledge/a.md", sources=[rel, FIRST_ADR], distilled_from_sha=added)
        commit_all(repo, "追従")
        assert check(repo)[0] == 0, "前提: ここでは stale でない"

        (repo / rel).write_text(
            (repo / rel).read_text(encoding="utf-8").replace(PIN_OLD, PIN_NEW),
            encoding="utf-8",
        )
        commit_all(repo, "compose.yml のピン形の行を更新")
        code, out = check(repo)
        assert code == 1, out
        assert "STALE" in out, f"ワークフロー以外の .yml を免除してしまっている:\n{out}"
    finally:
        shutil.rmtree(repo)


# --- stale 判定: マージコミット ------------------------------------------------


def test_evil_merge_is_detected_as_content_change() -> None:
    """マージ自身だけが内容を変える evil merge を stale 判定が見落とさない。"""
    repo = new_repo()
    try:
        workflow_baseline(repo)
        base = run_git(repo, "rev-parse", "--abbrev-ref", "HEAD")

        run_git(repo, "checkout", "-q", "-b", "side")
        write_workflow(repo, pin=PIN_NEW)
        commit_all(repo, "side: ピン更新のみ")
        run_git(repo, "checkout", "-q", base)
        write_workflow(repo, pin=PIN_RIVAL)
        commit_all(repo, "base: ピン更新のみ")

        conflicted = git_allow_fail(repo, "merge", "side")
        assert conflicted.returncode != 0, "前提: 同じ行を両側で変えたのでコンフリクトする"
        write_workflow(repo, pin=PIN_NEW, comment="解決時に書き換えた注記")
        merge = commit_all(repo, "evil merge")
        assert len(run_git(repo, "rev-parse", f"{merge}^@").split()) == 2, "前提: 2 親のマージ"

        code, out = check(repo)
        assert code == 1, f"evil merge が見落とされた:\n{out}"
        assert "STALE" in out and merge[:7] in out, out
    finally:
        shutil.rmtree(repo)


def test_merge_taking_one_side_is_attributed_to_ancestor() -> None:
    """片親の内容をそのまま採るマージは、マージではなく祖先コミットに帰属する。"""
    repo = new_repo()
    try:
        baseline(repo)
        base = run_git(repo, "rev-parse", "--abbrev-ref", "HEAD")
        run_git(repo, "checkout", "-q", "-b", "side")
        (repo / FIRST_ADR).write_text("# 0001\n\nside が作った内容\n", encoding="utf-8")
        side = commit_all(repo, "side change")
        run_git(repo, "checkout", "-q", base)
        (repo / "unrelated.md").write_text("x\n", encoding="utf-8")
        first_parent = commit_all(repo, "unrelated")
        run_git(repo, "merge", "-q", "side", "-m", "merge taking side")
        merge = run_git(repo, "rev-parse", "--short", "HEAD")
        write_doc(repo, "knowledge/a.md", sources=[FIRST_ADR], distilled_from_sha=first_parent)
        commit_all(repo, "a.md を first_parent 時点に固定")
        code, out = check(repo)
        assert code == 1, out
        assert side[:7] in out, f"祖先ではなくマージに帰属した:\n{out}"
        assert merge[:7] not in out, f"マージに帰属した:\n{out}"
    finally:
        shutil.rmtree(repo)


def test_merge_base_failure_is_error_not_stale_line() -> None:
    """G13: `merge-base --is-ancestor` が 0（祖先）/1（祖先でない）以外で終了したら、
    STALE 行の書式ではなく判定不能の error にする（bump-distilled-sha.py 等の
    後続スクリプトが STALE 行として誤ってパースし、誤って sha を進めるのを防ぐ）。
    """
    repo = new_repo()
    try:
        m = load_checker(repo)
        baseline(repo)
        original_git = m.git

        def fake_git(*args: str) -> "subprocess.CompletedProcess[str]":
            if args[:2] == ("merge-base", "--is-ancestor"):
                return subprocess.CompletedProcess(args, 128, stdout="", stderr="致命的: テスト用")
            return original_git(*args)

        m.git = fake_git
        p = repo / FIRST_ADR
        p.write_text(p.read_text(encoding="utf-8") + "\n追記。\n", encoding="utf-8")
        commit_all(repo, "source を実質更新")
        out = io.StringIO()
        cwd = Path.cwd()
        try:
            os.chdir(repo)
            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
                code = m.main([])
        finally:
            os.chdir(cwd)
        text = out.getvalue()
        assert code == 1, text
        assert "STALE" not in text, f"merge-base の異常終了を STALE 行にしてしまっている:\n{text}"
        assert "祖先判定ができない" in text, text
    finally:
        shutil.rmtree(repo)


# --- 走査の予算（ページ・リネーム）と git 失敗の扱い ---------------------------


def test_page_budget_exhaustion_is_reported_as_aborted() -> None:
    """ページ予算を使い切ったら ScanAborted を返す（None＝履歴が無い とは別物）。"""
    repo = new_repo()
    try:
        m = load_checker(repo)
        write_workflow(repo)
        commit_all(repo, "ワークフローを追加")
        write_workflow(repo, comment="説明を実質変更")
        commit_all(repo, "説明を実質変更")
        for i in range(6):
            write_workflow(repo, pin=f"{i:040x}", comment="説明を実質変更")
            commit_all(repo, f"ピン更新 {i}")
        got = m.last_content_change(WORKFLOW_REL, limit=2, max_pages=2)
        assert isinstance(got, m.ScanAborted), f"打ち切りを履歴の尽きと混同している: {got!r}"
        assert "max_pages" in got.reason, got.reason
    finally:
        shutil.rmtree(repo)


def test_rename_budget_exhaustion_is_reported_as_aborted() -> None:
    """リネーム予算の上限で打ち切ったときも ScanAborted（None に混ぜない）。"""
    repo = new_repo()
    try:
        m = load_checker(repo)
        write_workflow(repo)
        commit_all(repo, "ワークフローを追加")
        first = ".github/workflows/ci-1.yml"
        second = ".github/workflows/ci-2.yml"
        run_git(repo, "mv", WORKFLOW_REL, first)
        commit_all(repo, "1 回目の改名（内容不変）")
        run_git(repo, "mv", first, second)
        commit_all(repo, "2 回目の改名（内容不変）")
        got = m.last_content_change(second, limit=5, max_renames=1)
        assert isinstance(got, m.ScanAborted), f"リネーム上限の打ち切りを None に混ぜている: {got!r}"
        assert "max_renames" in got.reason, got.reason
    finally:
        shutil.rmtree(repo)


def test_rename_within_budget_still_finds_change() -> None:
    """境界の対照: 予算内のリネームは打ち切らず、改名前の内容変更まで辿る。"""
    repo = new_repo()
    try:
        m = load_checker(repo)
        write_workflow(repo)
        commit_all(repo, "ワークフローを追加")
        write_workflow(repo, comment="説明を実質変更")
        commit_all(repo, "説明を実質変更")
        real = run_git(repo, "rev-parse", "HEAD")
        moved = ".github/workflows/ci-1.yml"
        run_git(repo, "mv", WORKFLOW_REL, moved)
        commit_all(repo, "1 回だけ改名（内容不変）")
        got = m.last_content_change(moved, limit=5, max_renames=2)
        assert got == real, f"予算内のリネームで打ち切っている: {got!r}"
    finally:
        shutil.rmtree(repo)


def test_aborted_scan_is_reported_as_error_not_warning() -> None:
    """走査の未完遂は error（warning に落とすと fail-open が一段外側で再現する）。"""
    repo = new_repo()
    try:
        m = load_checker(repo)
        baseline(repo)
        m.last_content_change = lambda *a, **k: m.ScanAborted("テスト用の打ち切り")
        cwd = Path.cwd()
        out = io.StringIO()
        try:
            os.chdir(repo)
            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
                code = m.main([])
        finally:
            os.chdir(cwd)
        text = out.getvalue()
        assert code == 1, f"走査の未完遂が error になっていない（exit {code}）:\n{text}"
        assert "テスト用の打ち切り" in text, text
        assert "履歴が無く" not in text, f"打ち切りを履歴の尽きと同じ文言で流している:\n{text}"
    finally:
        shutil.rmtree(repo)


def main() -> int:
    if not TARGET.is_file():
        print(f"テスト対象が見つからない: {TARGET}", file=sys.stderr)
        return 1
    tests = [(n, f) for n, f in sorted(globals().items()) if n.startswith("test_") and callable(f)]
    passed = 0
    failed = 0
    print("check-knowledge.py 回帰テスト")
    for name, fn in tests:
        try:
            fn()
            print(f"  ✓ {name}")
            passed += 1
        except AssertionError as exc:
            print(f"  ✗ {name}: {exc}", file=sys.stderr)
            failed += 1
        except Exception as exc:  # noqa: BLE001 - テスト実行時の想定外は全部落とす
            print(f"  ✗ {name}: 想定外の例外 {exc!r}", file=sys.stderr)
            failed += 1
    print("")
    print(f"PASS={passed} FAIL={failed}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
