#!/usr/bin/env python3
"""hve-scripts/hooks/ の 2 本の回帰テスト（#27 タスク 4）。

対象:
  - hooks/session-stale-check.sh       SessionStart hook
  - hooks/check-knowledge-impact.py    PostToolUse hook（matcher: Write|Edit）

どちらも**導入先と同じ配置**（`.claude/scripts/hve/`）に `hve-scripts/` 一式を
コピーした fixture リポジトリから呼ぶ。両スクリプトはパスを自分の位置から解決する
契約（`$(dirname "$0")` / `Path(__file__).resolve().parent`）を持つため、リポジトリ内の
元の場所から直接呼んでも解決自体は通ってしまい、配置ズレのバグを検出できない。

session-stale-check.sh は実物の `bump-distilled-sha.py` / `check-knowledge.py` を
そのまま呼ぶ（スタブを使わない）。stale・判定不能（exit 2）は実際の git 履歴で再現する。

自走式（`def test_*()` を末尾の main() が集めて実行する）。pytest は使わない。stdlib のみ。
fixture 生成は `test_check_knowledge.py` の関数（`new_repo`・`write_doc`・`commit_all`・
`run_git`・`FIRST_ADR`）を再利用する。

使い方:
  python3 tests/hve_scripts/test_hooks.py
"""

from __future__ import annotations

import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
HVE_SCRIPTS_SRC = ROOT / "hve-scripts"
SESSION_HOOK_REL = "hooks/session-stale-check.sh"
IMPACT_HOOK_REL = "hooks/check-knowledge-impact.py"


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None, path
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# check-knowledge.py のテストが持つ fixture ヘルパーを再利用する（同じ形の使い捨て
# git repo を二重に書かないため）。
_ck = _load("check_knowledge_fixtures_for_hooks", HERE / "test_check_knowledge.py")
new_repo = _ck.new_repo
write_doc = _ck.write_doc
commit_all = _ck.commit_all
run_git = _ck.run_git
baseline = _ck.baseline
FIRST_ADR = _ck.FIRST_ADR


def _clean_env() -> dict:
    # git hook 経由で呼ばれると GIT_DIR 等が環境に残り、fixture の一時リポジトリ内の
    # git コマンドが別のリポジトリを指してしまう（#645 と同型の罠）。
    env = dict(os.environ)
    for key in ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE"):
        env.pop(key, None)
    return env


def install_hve_scripts(repo: Path) -> Path:
    """導入先と同じ配置（`.claude/scripts/hve/`）に `hve-scripts/` 一式をコピーする。"""
    dest = repo / ".claude" / "scripts" / "hve"
    shutil.copytree(HVE_SCRIPTS_SRC, dest)
    return dest


# --- session-stale-check.sh ---------------------------------------------------


def run_session_hook(cwd: Path, script: Path) -> "tuple[int, str]":
    proc = subprocess.run(
        ["bash", str(script)], cwd=cwd, capture_output=True, text=True, env=_clean_env()
    )
    return proc.returncode, (proc.stdout + proc.stderr).strip()


def test_session_hook_no_stale_is_silent() -> None:
    repo = new_repo()
    try:
        dest = install_hve_scripts(repo)
        baseline(repo)
        code, out = run_session_hook(repo, dest / SESSION_HOOK_REL)
        assert code == 0, out
        assert out == "", out
    finally:
        shutil.rmtree(repo)


def test_session_hook_reports_stale_count_and_usage() -> None:
    repo = new_repo()
    try:
        dest = install_hve_scripts(repo)
        write_doc(repo, "knowledge/a.md", sources=[FIRST_ADR], distilled_from_sha="HEAD")
        write_doc(repo, "knowledge/b.md", sources=[FIRST_ADR], distilled_from_sha="HEAD")
        sha = commit_all(repo, "2 文書を追加")
        write_doc(repo, "knowledge/a.md", sources=[FIRST_ADR], distilled_from_sha=sha)
        write_doc(repo, "knowledge/b.md", sources=[FIRST_ADR], distilled_from_sha=sha)
        commit_all(repo, "sha を pin")
        p = repo / FIRST_ADR
        p.write_text(p.read_text(encoding="utf-8") + "\n追記。\n", encoding="utf-8")
        commit_all(repo, "source を実質更新")

        code, out = run_session_hook(repo, dest / SESSION_HOOK_REL)
        assert code == 0, out
        assert "2 件" in out, out
        assert "bump-distilled-sha.py --all-stale" in out, out
    finally:
        shutil.rmtree(repo)


def test_session_hook_outside_git_repo_is_silent() -> None:
    tmp = Path(tempfile.mkdtemp(prefix="hooks-nogit-"))
    try:
        dest = install_hve_scripts(tmp)
        code, out = run_session_hook(tmp, dest / SESSION_HOOK_REL)
        assert code == 0, out
        assert out == "", out
    finally:
        shutil.rmtree(tmp)


def test_session_hook_indeterminate_bump_reports_one_line() -> None:
    """knowledge/ が無い → checker が判定不能（exit 2）で落ち、hook は 1 行だけ出す。"""
    repo = Path(tempfile.mkdtemp(prefix="hooks-indeterminate-"))
    try:
        run_git(repo, "init", "-q", "-b", "main")
        dest = install_hve_scripts(repo)
        code, out = run_session_hook(repo, dest / SESSION_HOOK_REL)
        assert code == 0, out
        assert out != "", "判定不能のとき 1 行出るはず"
        assert out.count("\n") == 0, f"1 行のはずが複数行: {out!r}"
    finally:
        shutil.rmtree(repo)


# --- check-knowledge-impact.py ------------------------------------------------


def write_knowledge_doc(repo: Path, rel: str, sources: "list[str]") -> None:
    path = repo / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = ["---", "title: fixture", "status: Confirmed", "kind: knowledge"]
    if sources:
        lines.append("sources:")
        lines.extend(f"  - {s}" for s in sources)
    else:
        lines.append("sources: []")
    lines += [
        'distilled_from_sha: "abc1234"',
        'updated: "2026-10-04"',
        "---",
        "",
        "# fixture",
        "",
        "本文。",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def new_impact_repo() -> Path:
    repo = Path(tempfile.mkdtemp(prefix="hooks-impact-"))
    run_git(repo, "init", "-q", "-b", "main")
    (repo / "docs-original").mkdir(parents=True)
    (repo / "qa").mkdir(parents=True)
    (repo / "knowledge" / "adr").mkdir(parents=True)
    (repo / "docs-original/foo.md").write_text("# 一次資料\n\n本文。\n", encoding="utf-8")
    (repo / "qa/QA-foo.md").write_text("# 質問票\n\n本文。\n", encoding="utf-8")
    write_knowledge_doc(repo, "knowledge/a.md", sources=["docs-original/foo.md"])
    write_knowledge_doc(repo, "knowledge/b.md", sources=["qa/QA-foo.md"])
    write_knowledge_doc(repo, "knowledge/no-sources.md", sources=[])
    (repo / "knowledge/adr/0001-example.md").write_text(
        "---\ntitle: ADR\nstatus: Accepted\n---\n\n# 0001. example\n", encoding="utf-8"
    )
    (repo / "knowledge/README.md").write_text("# knowledge 一覧\n", encoding="utf-8")
    (repo / "unrelated.md").write_text("# 無関係\n", encoding="utf-8")
    return repo


def run_impact_hook(repo: Path, script: Path, stdin_data: str) -> "tuple[int, str]":
    proc = subprocess.run(
        [sys.executable, str(script)],
        cwd=repo,
        input=stdin_data,
        capture_output=True,
        text=True,
        env=_clean_env(),
    )
    return proc.returncode, proc.stdout.strip()


def edit_payload(file_path: str) -> str:
    return json.dumps({"tool_name": "Edit", "tool_input": {"file_path": file_path}})


def test_impact_hook_source_edit_lists_affected_knowledge() -> None:
    repo = new_impact_repo()
    try:
        dest = install_hve_scripts(repo)
        code, out = run_impact_hook(
            repo, dest / IMPACT_HOOK_REL, edit_payload("docs-original/foo.md")
        )
        assert code == 0, out
        decision = json.loads(out)
        assert "knowledge/a.md" in decision["systemMessage"], out
        assert decision["hookSpecificOutput"]["hookEventName"] == "PostToolUse", out
        assert decision["hookSpecificOutput"]["additionalContext"], out
    finally:
        shutil.rmtree(repo)


def test_impact_hook_direct_knowledge_edit_warns_sot_reversal() -> None:
    repo = new_impact_repo()
    try:
        dest = install_hve_scripts(repo)
        code, out = run_impact_hook(repo, dest / IMPACT_HOOK_REL, edit_payload("knowledge/a.md"))
        assert code == 0, out
        decision = json.loads(out)
        assert "SoT" in decision["systemMessage"], out
        assert decision["hookSpecificOutput"]["hookEventName"] == "PostToolUse", out
        assert decision["hookSpecificOutput"]["additionalContext"], out
    finally:
        shutil.rmtree(repo)


def test_impact_hook_adr_is_excluded() -> None:
    repo = new_impact_repo()
    try:
        dest = install_hve_scripts(repo)
        code, out = run_impact_hook(
            repo, dest / IMPACT_HOOK_REL, edit_payload("knowledge/adr/0001-example.md")
        )
        assert code == 0, out
        assert out == "", out
    finally:
        shutil.rmtree(repo)


def test_impact_hook_readme_is_excluded() -> None:
    repo = new_impact_repo()
    try:
        dest = install_hve_scripts(repo)
        code, out = run_impact_hook(repo, dest / IMPACT_HOOK_REL, edit_payload("knowledge/README.md"))
        assert code == 0, out
        assert out == "", out
    finally:
        shutil.rmtree(repo)


def test_impact_hook_unrelated_file_is_silent() -> None:
    repo = new_impact_repo()
    try:
        dest = install_hve_scripts(repo)
        code, out = run_impact_hook(repo, dest / IMPACT_HOOK_REL, edit_payload("unrelated.md"))
        assert code == 0, out
        assert out == "", out
    finally:
        shutil.rmtree(repo)


def test_impact_hook_malformed_input_exits_zero() -> None:
    repo = new_impact_repo()
    try:
        dest = install_hve_scripts(repo)
        code, out = run_impact_hook(repo, dest / IMPACT_HOOK_REL, "{not valid json")
        assert code == 0, out
    finally:
        shutil.rmtree(repo)


def main() -> int:
    tests = [(n, f) for n, f in sorted(globals().items()) if n.startswith("test_") and callable(f)]
    passed = 0
    failed = 0
    print("hooks 回帰テスト")
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
