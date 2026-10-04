#!/usr/bin/env python3
"""hve-scripts/bump-distilled-sha.py の回帰テスト（#27 タスク 3）。

この道具は **knowledge 文書の frontmatter を書き換える**。壊れたときの被害が「規約の正本を
黙って書き換える」なので、fail-open と誤書き換えの経路を固定する。とくに:

  - checker（`check-knowledge.py`）が STALE 以外の理由で落ちたとき「直すものは無い」と言わない
  - checker が判定不能（exit 2）のときは、部分的な STALE が出力に混じっていても書き込まない
  - frontmatter を持たない文書のコードフェンス内テンプレートを書き換えない
  - 途中で失敗したとき、先行ファイルだけ書き換わった半端な状態を残さない
  - status が Conflict の文書は飛ばす（ADR 0011）
  - 書き込む sha は常にフル 40 桁
  - checker 自身の引数（`--required` 等）が `--` 以降でそのまま転送される

fixture 生成は `test_check_knowledge.py` の関数（`new_repo`・`baseline`・`write_doc`・
`commit_all`・`run_git`・`FIRST_ADR`）を再利用する（同じ形の使い捨て git repo）。

自走式（`def test_*()` を末尾の main() が集めて実行する）。pytest は使わない。stdlib のみ。

使い方:
  python3 tests/hve_scripts/test_bump_distilled_sha.py
"""

from __future__ import annotations

import importlib.util
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCRIPTS_DIR = HERE.parents[1] / "hve-scripts"
TARGET = SCRIPTS_DIR / "bump-distilled-sha.py"
CHECKER = SCRIPTS_DIR / "check-knowledge.py"


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None, path
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# check-knowledge.py のテストが持つ fixture ヘルパーを再利用する（同じ形の使い捨て
# git repo を二重に書かないため）。
_ck = _load("check_knowledge_fixtures", HERE / "test_check_knowledge.py")

new_repo = _ck.new_repo
baseline = _ck.baseline
write_doc = _ck.write_doc
commit_all = _ck.commit_all
run_git = _ck.run_git
FIRST_ADR = _ck.FIRST_ADR

# body_after_frontmatter() 等を直接テストするため、対象スクリプトをモジュールとして読み込む
# （__name__ が "__main__" でないので末尾の sys.exit(main(...)) は実行されない）。
_bump = _load("bump_module_under_test", TARGET) if TARGET.is_file() else None


def run(repo: Path, *args: str) -> "tuple[int, str]":
    proc = subprocess.run(
        [sys.executable, str(TARGET), *args], cwd=repo, capture_output=True, text=True
    )
    return proc.returncode, proc.stdout + proc.stderr


def distilled_of(repo: Path, rel: str) -> str:
    for line in (repo / rel).read_text(encoding="utf-8").splitlines():
        if line.startswith("distilled_from_sha:"):
            return line.split('"')[1]
    return ""


def full_head(repo: Path) -> str:
    return run_git(repo, "rev-parse", "HEAD")


def make_stale(repo: Path) -> str:
    """FIRST_ADR の本文を実質更新し、knowledge/a.md を stale にする（短縮 sha を返す）。"""
    p = repo / FIRST_ADR
    p.write_text(p.read_text(encoding="utf-8") + "\n追記。\n", encoding="utf-8")
    return commit_all(repo, "source を実質更新")


# --- --all-stale / --dry-run の基本動作 ---------------------------------------


def test_all_stale_bumps_target_with_full_sha() -> None:
    repo = new_repo()
    try:
        baseline(repo)
        make_stale(repo)
        full = full_head(repo)
        code, out = run(repo, "--all-stale")
        assert code == 0, out
        assert "knowledge/a.md" in out, out
        written = distilled_of(repo, "knowledge/a.md")
        assert len(written) == 40, f"フル 40 桁で書かれていない: {written!r}"
        assert written == full, out
    finally:
        shutil.rmtree(repo)


def test_dry_run_does_not_write() -> None:
    repo = new_repo()
    try:
        baseline(repo)
        before = distilled_of(repo, "knowledge/a.md")
        make_stale(repo)
        code, out = run(repo, "--all-stale", "--dry-run")
        assert code == 0, out
        assert "（dry-run）" in out, out
        assert distilled_of(repo, "knowledge/a.md") == before, "dry-run で書き換わった"
    finally:
        shutil.rmtree(repo)


def test_no_stale_reports_nothing_to_do() -> None:
    repo = new_repo()
    try:
        baseline(repo)
        code, out = run(repo, "--all-stale")
        assert code == 0, out
        assert "STALE な文書は無い" in out, out
    finally:
        shutil.rmtree(repo)


# --- checker の他の error / 判定不能（exit 2） ---------------------------------


def test_checker_failure_is_not_reported_as_no_stale() -> None:
    """checker が STALE 以外の理由（exit 1）で落ちているのに「直すものは無い」と言わない。"""
    repo = new_repo()
    try:
        sha = baseline(repo)
        before = distilled_of(repo, "knowledge/a.md")
        write_doc(repo, "knowledge/b.md", status=None, sources=[FIRST_ADR], distilled_from_sha=sha)
        commit_all(repo, "status を欠落させた文書を追加")
        code, out = run(repo, "--all-stale")
        assert code == 1, out
        assert "STALE 以外の理由で落ちている" in out, out
        assert distilled_of(repo, "knowledge/a.md") == before, "落ちたのに書き換えた"
    finally:
        shutil.rmtree(repo)


def test_checker_rc2_stops_fail_closed() -> None:
    """checker が判定不能（exit 2）のとき、部分的な STALE があっても書き込まずに止まる。"""
    repo = new_repo()
    try:
        baseline(repo)
        before = distilled_of(repo, "knowledge/a.md")
        code, out = run(repo, "--all-stale", "--", "--dir", "does-not-exist")
        assert code == 2, out
        assert "判定不能" in out, out
        assert distilled_of(repo, "knowledge/a.md") == before, "fail-closed なのに書き換えた"
    finally:
        shutil.rmtree(repo)


def test_other_errors_are_not_reported_as_resolved() -> None:
    """STALE と他の error が同居するとき、bump 後に 0 を返して「解消した」と読ませない。"""
    repo = new_repo()
    try:
        baseline(repo)
        make_stale(repo)
        sha_now = distilled_of(repo, "knowledge/a.md")
        write_doc(
            repo, "knowledge/a.md",
            sources=["docs-original/9999-nope.md", FIRST_ADR],
            distilled_from_sha=sha_now,
        )
        commit_all(repo, "存在しない source を足す（別の error）")
        code, out = run(repo, "--all-stale")
        assert code == 1, out
        assert "STALE 以外の error も残っている" in out, out
    finally:
        shutil.rmtree(repo)


# --- checker 引数の転送 --------------------------------------------------------


def test_checker_args_are_forwarded() -> None:
    """`--` 以降の引数が checker（check-knowledge.py）にそのまま転送される。"""
    repo = new_repo()
    try:
        sha = baseline(repo)
        write_doc(repo, "knowledge/b.md", kind=None, sources=[FIRST_ADR], distilled_from_sha=sha)
        commit_all(repo, "kind を欠落させた文書を追加")

        # 転送なし: b.md の kind 欠落が他の error として残り、STALE 0 件のまま fail-closed
        code, out = run(repo, "--all-stale")
        assert code == 1, out
        assert "STALE 以外の理由で落ちている" in out, out

        # 転送あり: --required で kind を外すと b.md はエラーにならず、STALE も無いので 0
        code, out = run(
            repo, "--all-stale", "--", "--required",
            "title,status,sources,distilled_from_sha,updated",
        )
        assert code == 0, out
        assert "STALE な文書は無い" in out, out
    finally:
        shutil.rmtree(repo)


# --- Conflict（解消待ち）は bump しない -----------------------------------------


def test_conflict_status_is_skipped_not_bumped() -> None:
    repo = new_repo()
    try:
        sha = baseline(repo)
        make_stale(repo)  # 本来なら stale になる状態を作る
        write_doc(repo, "knowledge/a.md", status="Conflict", sources=[FIRST_ADR], distilled_from_sha=sha)
        commit_all(repo, "Conflict へ変更")
        before = distilled_of(repo, "knowledge/a.md")
        code, out = run(repo, "knowledge/a.md")
        assert code == 0, out
        assert "解消待ちのため飛ばした" in out, out
        assert distilled_of(repo, "knowledge/a.md") == before, "Conflict の文書を書き換えた"
    finally:
        shutil.rmtree(repo)


def test_conflict_is_skipped_even_when_explicitly_named_with_other_targets() -> None:
    """Conflict の文書と通常の文書を同時に指定しても、通常の文書は bump される。"""
    repo = new_repo()
    try:
        sha = baseline(repo)
        write_doc(repo, "knowledge/b.md", status="Conflict", sources=[FIRST_ADR], distilled_from_sha=sha)
        commit_all(repo, "Conflict な b.md を追加")
        make_stale(repo)
        full = full_head(repo)
        before_b = distilled_of(repo, "knowledge/b.md")
        code, out = run(repo, "knowledge/a.md", "knowledge/b.md")
        assert code == 0, out
        assert "knowledge/b.md: 解消待ちのため飛ばした" in out, out
        assert distilled_of(repo, "knowledge/a.md") == full, out
        assert distilled_of(repo, "knowledge/b.md") == before_b, "Conflict の文書を書き換えた"
    finally:
        shutil.rmtree(repo)


# --- 本文テンプレート・frontmatter 欠落の扱い ----------------------------------


def test_frontmatter_only_is_rewritten() -> None:
    """本文（フェンス内のテンプレート例）は書き換えない。"""
    repo = new_repo()
    try:
        baseline(repo)
        path = repo / "knowledge/a.md"
        path.write_text(
            path.read_text(encoding="utf-8")
            + '\n```yaml\ndistilled_from_sha: "<short-sha>"\n```\n',
            encoding="utf-8",
        )
        commit_all(repo, "テンプレ例を足す")
        full = full_head(repo)
        code, out = run(repo, "knowledge/a.md")
        assert code == 0, out
        assert distilled_of(repo, "knowledge/a.md") == full, out
        assert '"<short-sha>"' in path.read_text(encoding="utf-8"), "本文のテンプレを書き換えた"
    finally:
        shutil.rmtree(repo)


def test_file_without_frontmatter_is_refused() -> None:
    repo = new_repo()
    try:
        baseline(repo)
        (repo / "knowledge/plain.md").write_text(
            '# 規約\n\n```yaml\ndistilled_from_sha: "<short-sha>"\n```\n', encoding="utf-8"
        )
        code, out = run(repo, "knowledge/plain.md")
        assert code == 1, out
        assert "distilled_from_sha の行が無い" in out, out
        assert '"<short-sha>"' in (repo / "knowledge/plain.md").read_text(encoding="utf-8")
    finally:
        shutil.rmtree(repo)


def test_body_template_after_frontmatter_without_sha_is_refused() -> None:
    """frontmatter に sha 行が無く、本文のフェンス内にだけ見本がある場合を弾く。"""
    repo = new_repo()
    try:
        baseline(repo)
        (repo / "knowledge/tmpl.md").write_text(
            '---\nstatus: Confirmed\nkind: knowledge\n---\n\n'
            '# テンプレ\n\n```yaml\ndistilled_from_sha: "<short-sha>"\n```\n',
            encoding="utf-8",
        )
        code, out = run(repo, "knowledge/tmpl.md")
        assert code == 1, out
        assert "distilled_from_sha の行が無い" in out, out
        body = (repo / "knowledge/tmpl.md").read_text(encoding="utf-8")
        assert '"<short-sha>"' in body, "本文のテンプレを書き換えた"
    finally:
        shutil.rmtree(repo)


def test_duplicate_distilled_lines_are_refused() -> None:
    """checker は最後の行、bump は最初の行を見る。放置すると bump しても STALE が消えない。"""
    repo = new_repo()
    try:
        baseline(repo)
        path = repo / "knowledge/a.md"
        text = path.read_text(encoding="utf-8")
        dup = 'distilled_from_sha: "deadbee"\nupdated:'
        path.write_text(text.replace("updated:", dup, 1), encoding="utf-8")
        code, out = run(repo, "knowledge/a.md")
        assert code == 1, out
        assert "distilled_from_sha が 2 行ある" in out, out
    finally:
        shutil.rmtree(repo)


def test_missing_file_aborts_before_writing() -> None:
    """途中で落ちるとき、先行ファイルだけ書き換わった半端な状態を残さない。"""
    repo = new_repo()
    try:
        baseline(repo)
        before = distilled_of(repo, "knowledge/a.md")
        code, out = run(repo, "knowledge/a.md", "knowledge/nope.md")
        assert code == 1, out
        assert "ファイルが無い" in out, out
        assert distilled_of(repo, "knowledge/a.md") == before, "abort 前に書き換えた"
    finally:
        shutil.rmtree(repo)


# --- --sha / 引数の検証 --------------------------------------------------------


def test_sha_option_requires_a_value() -> None:
    repo = new_repo()
    try:
        baseline(repo)
        before = distilled_of(repo, "knowledge/a.md")
        code, out = run(repo, "--sha", "--dry-run", "knowledge/a.md")
        assert code == 2, out
        assert "--sha に値が無い" in out, out
        assert distilled_of(repo, "knowledge/a.md") == before, out
    finally:
        shutil.rmtree(repo)


def test_unresolvable_sha_is_rejected() -> None:
    repo = new_repo()
    try:
        baseline(repo)
        before = distilled_of(repo, "knowledge/a.md")
        code, out = run(repo, "--sha", "zzzzzzz", "knowledge/a.md")
        assert code == 2, out
        assert "解決できない" in out, out
        assert distilled_of(repo, "knowledge/a.md") == before, out
    finally:
        shutil.rmtree(repo)


def test_sha_option_writes_resolved_full_sha() -> None:
    """`--sha HEAD` を literal で書くと stale 判定が恒久的に無効化されるので、解決結果を書く。"""
    repo = new_repo()
    try:
        baseline(repo)
        full = full_head(repo)
        code, out = run(repo, "--sha", "HEAD", "knowledge/a.md")
        assert code == 0, out
        written = distilled_of(repo, "knowledge/a.md")
        assert written != "HEAD", f"可変参照をそのまま書いた: {written}"
        assert len(written) == 40, f"フル 40 桁で書かれていない: {written!r}"
        assert written == full, out
    finally:
        shutil.rmtree(repo)


def test_no_args_is_fail_closed() -> None:
    repo = new_repo()
    try:
        baseline(repo)
        code, out = run(repo)
        assert code == 2, out
        assert "引数が無い" in out, out
    finally:
        shutil.rmtree(repo)


# --- updated は触らない ---------------------------------------------------------


def test_updated_is_not_touched() -> None:
    """`updated` は人が判断して進める。道具が勝手に動かさない。"""
    repo = new_repo()
    try:
        baseline(repo)
        before = (repo / "knowledge/a.md").read_text(encoding="utf-8")
        make_stale(repo)
        code, out = run(repo, "--all-stale")
        assert code == 0, out
        after = (repo / "knowledge/a.md").read_text(encoding="utf-8")
        assert 'updated: "2026-10-04"' in after, after
        assert before != after, "sha が変わっていない"
    finally:
        shutil.rmtree(repo)


# --- CRLF / 空値 ----------------------------------------------------------------


def test_crlf_document_is_bumped_in_place() -> None:
    """CRLF の文書でも frontmatter を見つけ、改行コードを壊さない。"""
    repo = new_repo()
    try:
        baseline(repo)
        path = repo / "knowledge/a.md"
        with path.open(encoding="utf-8", newline="") as f:
            lf_text = f.read()
        with path.open("w", encoding="utf-8", newline="") as f:
            f.write(lf_text.replace("\n", "\r\n"))
        commit_all(repo, "CRLF へ変換")
        full = full_head(repo)
        code, out = run(repo, "knowledge/a.md")
        assert code == 0, out
        with path.open(encoding="utf-8", newline="") as f:
            after = f.read()
        assert f'distilled_from_sha: "{full}"' in after, after[:200]
        assert after.count("\n") == after.count("\r\n") > 0, "改行コードが LF へ正規化された"
    finally:
        shutil.rmtree(repo)


def test_empty_value_gets_a_space_after_colon() -> None:
    """値が空の行を bump しても YAML として壊れた `key:"v"` を書かない。"""
    repo = new_repo()
    try:
        baseline(repo)
        path = repo / "knowledge/a.md"
        text = path.read_text(encoding="utf-8")
        path.write_text(
            re.sub(r'^distilled_from_sha: ".*"$', "distilled_from_sha:", text, count=1, flags=re.M),
            encoding="utf-8",
        )
        code, out = run(repo, "knowledge/a.md")
        assert code == 0, out
        after = path.read_text(encoding="utf-8")
        assert 'distilled_from_sha: "' in after, after[:200]
        assert 'distilled_from_sha:"' not in after, "コロン直後に空白が無い"
    finally:
        shutil.rmtree(repo)


# --- body_after_frontmatter() 単体 -----------------------------------------------


def test_body_after_frontmatter_basic() -> None:
    assert _bump is not None, "対象スクリプトが見つからないのでモジュールを読めていない"
    with_fm = '---\nstatus: Confirmed\nupdated: "2026-01-01"\n---\n\n# Title\n\n本文。\n'
    assert _bump.body_after_frontmatter(with_fm) == '---\n\n# Title\n\n本文。\n'
    without_fm = "# Title\n\n本文のみ。\n"
    assert _bump.body_after_frontmatter(without_fm) == without_fm


# --- 形骸化検出（distilled_from_sha だけ進めて本文が変わっていない） --------------


def test_stale_bump_without_body_change_warns_of_atrophy() -> None:
    repo = new_repo()
    try:
        baseline(repo)
        make_stale(repo)
        code, out = run(repo, "--all-stale")
        assert code == 0, out
        assert "⚠ knowledge/a.md" in out, out
        assert "形骸化" in out, out
    finally:
        shutil.rmtree(repo)


def test_stale_bump_with_body_change_does_not_warn() -> None:
    repo = new_repo()
    try:
        baseline(repo)
        make_stale(repo)
        path = repo / "knowledge/a.md"
        path.write_text(
            path.read_text(encoding="utf-8").replace("本文。", "本文を人手で更新した。"),
            encoding="utf-8",
        )
        commit_all(repo, "本文も更新")
        code, out = run(repo, "--all-stale")
        assert code == 0, out
        assert "⚠ knowledge/a.md" not in out, out
    finally:
        shutil.rmtree(repo)


def test_dryrun_does_not_warn_atrophy() -> None:
    repo = new_repo()
    try:
        baseline(repo)
        make_stale(repo)
        code, out = run(repo, "--all-stale", "--dry-run")
        assert code == 0, out
        assert "⚠" not in out, out
    finally:
        shutil.rmtree(repo)


def clone_repo(repo: Path) -> Path:
    """repo の現在の全 ref を「push 後の新しい clone」として再現する。

    `--no-local` を付けないと、同一ファイルシステム上の clone は objects を
    ハードリンクで丸ごと持ち込み、squash・rebase で外れた孤立コミットまで
    残ってしまう（本当の push + 新規 clone では reachable なオブジェクトしか
    転送されない）。
    """
    clone_dir = Path(tempfile.mkdtemp(prefix="bump-clone-"))
    subprocess.run(
        ["git", "clone", "--no-local", "-q", str(repo), str(clone_dir)],
        check=True, capture_output=True,
    )
    return clone_dir


def run_checker(repo: Path, *args: str) -> "tuple[int, str]":
    proc = subprocess.run(
        [sys.executable, str(CHECKER), *args], cwd=repo, capture_output=True, text=True
    )
    return proc.returncode, proc.stdout + proc.stderr


def test_unresolvable_old_sha_skips_atrophy_check() -> None:
    """旧 distilled_from_sha が git で解決できない場合は警告もエラーも出ない。"""
    repo = new_repo()
    try:
        baseline(repo)
        path = repo / "knowledge/a.md"
        text = path.read_text(encoding="utf-8")
        path.write_text(
            re.sub(r'distilled_from_sha: ".*"', 'distilled_from_sha: "deadbee"', text, count=1),
            encoding="utf-8",
        )
        commit_all(repo, "distilled_from_sha を壊れた値に")
        code, out = run(repo, "knowledge/a.md")
        assert code == 0, out
        assert "⚠" not in out, out
        assert distilled_of(repo, "knowledge/a.md") not in ("", "deadbee"), out
    finally:
        shutil.rmtree(repo)


# --- --follow-rewritten（squash・rebase 後の sha 追従。ADR 0014） ---------------


def test_follow_rewritten_bumps_after_squash() -> None:
    """squash で distilled_from_sha の指すコミットが履歴から外れても、source が変わって
    いなければ追従され、push 後の新しい clone でも check-knowledge.py が通る。
    """
    repo = new_repo()
    try:
        base = baseline(repo)
        # 「main で source が更新」
        p = repo / FIRST_ADR
        p.write_text(p.read_text(encoding="utf-8") + "\n追記。\n", encoding="utf-8")
        commit_all(repo, "source を更新")
        # 「ブランチで本文を直して bump」
        a = repo / "knowledge/a.md"
        a.write_text(
            a.read_text(encoding="utf-8").replace("本文。", "本文を更新した。"), encoding="utf-8"
        )
        commit_all(repo, "本文を更新")
        code, out = run(repo, "knowledge/a.md")
        assert code == 0, out
        old_sha = distilled_of(repo, "knowledge/a.md")
        commit_all(repo, "sha 追従")

        # squash: base 以降のコミットを 1 つにまとめる
        run_git(repo, "reset", "--soft", base)
        run_git(repo, "commit", "-q", "-m", "squash")
        squashed = full_head(repo)
        assert distilled_of(repo, "knowledge/a.md") == old_sha, "squash で sha 値自体は変わらない"

        code, out = run(repo, "--follow-rewritten", base)
        assert code == 0, out
        assert f"knowledge/a.md: {old_sha} → {squashed}" in out, out
        assert distilled_of(repo, "knowledge/a.md") == squashed

        # bump() はファイルを書くだけでコミットしない。実運用（create-pr/review-pr）
        # と同じく「sha 追従コミット」を積んでから push 相当の clone を取る。
        commit_all(repo, "squash 後の sha 追従")

        clone = clone_repo(repo)
        try:
            ccode, cout = run_checker(clone)
            assert ccode == 0, cout
        finally:
            shutil.rmtree(clone)
    finally:
        shutil.rmtree(repo)


def test_follow_rewritten_bumps_after_rebase() -> None:
    """rebase で distilled_from_sha の指すコミットが入れ替わっても追従される。"""
    repo = new_repo()
    try:
        baseline(repo)
        run_git(repo, "checkout", "-q", "-b", "feature")
        p = repo / FIRST_ADR
        p.write_text(p.read_text(encoding="utf-8") + "\n追記。\n", encoding="utf-8")
        commit_all(repo, "source を更新")
        a = repo / "knowledge/a.md"
        a.write_text(
            a.read_text(encoding="utf-8").replace("本文。", "本文を更新した。"), encoding="utf-8"
        )
        commit_all(repo, "本文を更新")
        code, out = run(repo, "knowledge/a.md")
        assert code == 0, out
        old_sha = distilled_of(repo, "knowledge/a.md")
        commit_all(repo, "sha 追従")

        run_git(repo, "checkout", "-q", "main")
        (repo / "dummy.txt").write_text("main 側の進捗\n", encoding="utf-8")
        commit_all(repo, "main を進める")

        run_git(repo, "checkout", "-q", "feature")
        run_git(repo, "rebase", "main")
        rebased = full_head(repo)
        assert distilled_of(repo, "knowledge/a.md") == old_sha, "rebase で sha 値自体は変わらない"

        code, out = run(repo, "--follow-rewritten", "main")
        assert code == 0, out
        assert f"knowledge/a.md: {old_sha} → {rebased}" in out, out
        assert distilled_of(repo, "knowledge/a.md") == rebased
    finally:
        shutil.rmtree(repo)


def test_follow_rewritten_refuses_when_source_changed_after_old_sha() -> None:
    """旧 sha のあとに source が変わっている場合は追従しない（本当の stale を隠さない）。"""
    repo = new_repo()
    try:
        base = baseline(repo)
        a = repo / "knowledge/a.md"
        a.write_text(
            a.read_text(encoding="utf-8").replace("本文。", "本文を更新した。"), encoding="utf-8"
        )
        commit_all(repo, "本文を更新")
        code, out = run(repo, "knowledge/a.md")
        assert code == 0, out
        old_sha = distilled_of(repo, "knowledge/a.md")
        commit_all(repo, "sha 追従")

        # bump の後に source を変える
        p = repo / FIRST_ADR
        p.write_text(p.read_text(encoding="utf-8") + "\n追記。\n", encoding="utf-8")
        commit_all(repo, "bump 後に source を更新")

        run_git(repo, "reset", "--soft", base)
        run_git(repo, "commit", "-q", "-m", "squash")
        assert distilled_of(repo, "knowledge/a.md") == old_sha

        code, out = run(repo, "--follow-rewritten", base)
        assert code == 1, out
        assert "旧 sha のあとに source が変わっている" in out, out
        assert distilled_of(repo, "knowledge/a.md") == old_sha, "追従すべきでないのに書き換えた"
    finally:
        shutil.rmtree(repo)


def test_follow_rewritten_refuses_when_old_sha_is_unresolvable() -> None:
    """旧 distilled_from_sha がローカルで解決できない場合は追従しない。"""
    repo = new_repo()
    try:
        base = baseline(repo)
        a = repo / "knowledge/a.md"
        text = a.read_text(encoding="utf-8")
        fake_sha = "0" * 40
        a.write_text(
            re.sub(r'distilled_from_sha: ".*"', f'distilled_from_sha: "{fake_sha}"', text, count=1),
            encoding="utf-8",
        )
        commit_all(repo, "distilled_from_sha を存在しない sha にする")

        code, out = run(repo, "--follow-rewritten", base)
        assert code == 1, out
        assert "旧 sha が見つからないため追従できない" in out, out
        assert distilled_of(repo, "knowledge/a.md") == fake_sha
    finally:
        shutil.rmtree(repo)


def test_follow_rewritten_noop_when_sha_is_ancestor_of_head() -> None:
    """distilled_from_sha が HEAD の祖先のままなら何もしない。"""
    repo = new_repo()
    try:
        base = baseline(repo)
        a = repo / "knowledge/a.md"
        a.write_text(
            a.read_text(encoding="utf-8").replace("本文。", "本文を更新した。"), encoding="utf-8"
        )
        commit_all(repo, "本文を更新（sha はまだ古いまま、祖先関係は保たれる）")
        before = distilled_of(repo, "knowledge/a.md")

        code, out = run(repo, "--follow-rewritten", base)
        assert code == 0, out
        assert "追従が要る文書は無い" in out, out
        assert distilled_of(repo, "knowledge/a.md") == before
    finally:
        shutil.rmtree(repo)


def test_follow_rewritten_skips_files_not_changed_in_diff() -> None:
    """PR（base...HEAD）で変えていない文書は対象外。"""
    repo = new_repo()
    try:
        base = baseline(repo)
        extra = repo / "docs-original" / "extra.md"
        extra.write_text("追加資料\n", encoding="utf-8")
        commit_all(repo, "a.md と無関係なファイルを追加")

        code, out = run(repo, "--follow-rewritten", base)
        assert code == 0, out
        assert "追従が要る文書は無い" in out, out
        assert "knowledge/a.md" not in out, out
    finally:
        shutil.rmtree(repo)


def test_follow_rewritten_skips_conflict_status() -> None:
    """status が Conflict の文書は既存どおり飛ばす（bump しない）。"""
    repo = new_repo()
    try:
        base = baseline(repo)
        write_doc(
            repo, "knowledge/a.md", status="Conflict", sources=[FIRST_ADR],
            distilled_from_sha="0" * 40,
        )
        commit_all(repo, "Conflict へ変更")
        before = distilled_of(repo, "knowledge/a.md")

        code, out = run(repo, "--follow-rewritten", base)
        assert code == 0, out
        assert "knowledge/a.md: 解消待ちのため飛ばした" in out, out
        assert "追従が要る文書は無い" in out, out
        assert distilled_of(repo, "knowledge/a.md") == before
    finally:
        shutil.rmtree(repo)


def test_follow_rewritten_dry_run_does_not_write() -> None:
    repo = new_repo()
    try:
        base = baseline(repo)
        a = repo / "knowledge/a.md"
        a.write_text(
            a.read_text(encoding="utf-8").replace("本文。", "本文を更新した。"), encoding="utf-8"
        )
        commit_all(repo, "本文を更新")
        code, out = run(repo, "knowledge/a.md")
        assert code == 0, out
        old_sha = distilled_of(repo, "knowledge/a.md")
        commit_all(repo, "sha 追従")

        run_git(repo, "reset", "--soft", base)
        run_git(repo, "commit", "-q", "-m", "squash")

        code, out = run(repo, "--follow-rewritten", base, "--dry-run")
        assert code == 0, out
        assert "（dry-run）" in out, out
        assert distilled_of(repo, "knowledge/a.md") == old_sha, "dry-run で書き換わった"
    finally:
        shutil.rmtree(repo)


def test_follow_rewritten_rejects_combination_with_other_target_args() -> None:
    repo = new_repo()
    try:
        base = baseline(repo)
        before = distilled_of(repo, "knowledge/a.md")

        code, out = run(repo, "--follow-rewritten", base, "knowledge/a.md")
        assert code == 2, out
        assert "併用できない" in out, out

        code, out = run(repo, "--follow-rewritten", base, "--all-stale")
        assert code == 2, out

        code, out = run(repo, "--follow-rewritten", base, "--sha", base)
        assert code == 2, out

        assert distilled_of(repo, "knowledge/a.md") == before
    finally:
        shutil.rmtree(repo)


def main() -> int:
    if not TARGET.is_file():
        print(f"テスト対象が見つからない: {TARGET}", file=sys.stderr)
        return 1
    tests = [(n, f) for n, f in sorted(globals().items()) if n.startswith("test_") and callable(f)]
    passed = 0
    failed = 0
    print("bump-distilled-sha.py 回帰テスト")
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
