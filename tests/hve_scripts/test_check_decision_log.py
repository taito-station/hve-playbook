#!/usr/bin/env python3
"""check-decision-log.py の回帰テスト（#27）。

使い捨ての fixture git リポジトリを実際に作り、merge-base 比較まで含めた各分岐の
終了コードを固定する。pytest は使わない自走式（`def test_*()` + assert を末尾の
main() が集めて実行する）。stdlib のみ。

使い方:
  python3 tests/hve_scripts/test_check_decision_log.py
"""

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

TARGET = Path(__file__).resolve().parent.parent.parent / "hve-scripts" / "check-decision-log.py"

LOG_HEADER = (
    "\n---\n\n## 決定ログ\n\n"
    "<!-- この節は append-only です。既存エントリの変更・削除は検出されます。 -->\n\n"
)
ENTRY_A = "### 決定 A\n\n- 決定: A を採用する\n- 理由: テスト用の理由\n"
ENTRY_B = "### 決定 B\n\n- 決定: B を採用する\n- 理由: テスト用の理由その2\n"


def run_git(repo, *args, check=True):
    proc = subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True)
    if check and proc.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed: {proc.stdout}\n{proc.stderr}")
    return proc.stdout.strip()


def commit_all(repo, message):
    run_git(repo, "add", "-A")
    run_git(repo, "commit", "-q", "-m", message)
    return run_git(repo, "rev-parse", "HEAD")


def check(repo, *args):
    proc = subprocess.run(
        [sys.executable, str(TARGET), *args], cwd=repo, capture_output=True, text=True
    )
    return proc.returncode, proc.stdout + proc.stderr


def write_doc(repo, rel, body):
    path = repo / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")


def read_doc(repo, rel):
    return (repo / rel).read_text(encoding="utf-8")


def overwrite(repo, rel, text):
    (repo / rel).write_text(text, encoding="utf-8")


def adr_text(status, body="背景の説明。\n"):
    return (
        "# タイトル\n\n"
        "## ステータス\n\n"
        f"{status}\n\n"
        "## 背景と課題\n\n"
        f"{body}"
    )


def readme_text(rows):
    """rows: [(連番, タイトル, ステータス, 日付), ...]"""
    lines = [
        "# ADR 一覧\n",
        "",
        "| 連番 | タイトル | ステータス | 日付 |",
        "|---|---|---|---|",
    ]
    for num, title, status, date in rows:
        lines.append(f"| [{num}]({num}-doc.md) | {title} | {status} | {date} |")
    return "\n".join(lines) + "\n"


def new_repo():
    """main に素の .gitattributes だけを置き、work ブランチへ移った fixture を返す。"""
    repo = Path(tempfile.mkdtemp(prefix="decision-log-test-"))
    run_git(repo, "init", "-q", "-b", "main")
    run_git(repo, "config", "user.email", "test@example.invalid")
    run_git(repo, "config", "user.name", "test")
    run_git(repo, "config", "commit.gpgsign", "false")
    run_git(repo, "config", "core.autocrlf", "false")
    (repo / ".gitattributes").write_text("* -text\n", encoding="utf-8")
    run_git(repo, "add", "-A")
    run_git(repo, "commit", "-q", "-m", "init")
    return repo


def commit_baseline(repo):
    """積んだ文書を main にコミットし、work ブランチへ切り替える。"""
    commit_all(repo, "baseline")
    run_git(repo, "switch", "-q", "-c", "work")


def land_on_main(repo):
    """作業ブランチの現状を main へ取り込み、次の作業ブランチへ移る。"""
    current = run_git(repo, "rev-parse", "--abbrev-ref", "HEAD")
    run_git(repo, "switch", "-q", "main")
    run_git(repo, "merge", "-q", "--ff-only", current)
    run_git(repo, "switch", "-q", "-c", f"{current}-next")


def poison_diff_config(repo):
    """diff.external / textconv / noprefix / mnemonicPrefix を汚染し、git diff の生出力を偽装させる。"""
    run_git(repo, "config", "diff.external", "false")
    run_git(repo, "config", "diff.noprefix", "true")
    run_git(repo, "config", "diff.mnemonicPrefix", "true")
    (repo / ".gitattributes").write_text("* -text\n*.md diff=hidden\n", encoding="utf-8")
    run_git(repo, "config", "diff.hidden.textconv", "true")


# --- インライン方式: 通過するケース -----------------------------------------


def test_untouched_tree_passes():
    repo = new_repo()
    try:
        write_doc(repo, "knowledge/a.md", "本文の段落。\n" + LOG_HEADER + ENTRY_A)
        commit_baseline(repo)
        code, out = check(repo)
        assert code == 0, out
        assert "✓ 決定ログの不変性を確認" in out, out
        assert "インライン 1 本" in out, out
    finally:
        shutil.rmtree(repo)


def test_new_file_with_decision_log_passes():
    repo = new_repo()
    try:
        write_doc(repo, "knowledge/a.md", "本文。\n" + LOG_HEADER + ENTRY_A)
        commit_baseline(repo)
        write_doc(repo, "knowledge/new.md", "本文。\n" + LOG_HEADER + ENTRY_B)
        commit_all(repo, "新規文書を追加")
        code, out = check(repo)
        assert code == 0, out
        assert "インライン 1 本" in out, f"新規ファイルを検査本数に数えている:\n{out}"
    finally:
        shutil.rmtree(repo)


def test_appended_entry_passes():
    repo = new_repo()
    try:
        write_doc(repo, "knowledge/a.md", "本文。\n" + LOG_HEADER + ENTRY_A)
        commit_baseline(repo)
        overwrite(repo, "knowledge/a.md", read_doc(repo, "knowledge/a.md") + "\n" + ENTRY_B)
        commit_all(repo, "決定ログを追記")
        code, out = check(repo)
        assert code == 0, out
    finally:
        shutil.rmtree(repo)


def test_body_change_outside_decision_log_passes():
    repo = new_repo()
    try:
        write_doc(repo, "knowledge/a.md", "本文の段落。\n" + LOG_HEADER + ENTRY_A)
        commit_baseline(repo)
        text = read_doc(repo, "knowledge/a.md")
        overwrite(repo, "knowledge/a.md", text.replace("本文の段落。", "本文を全面的に書き直した。"))
        commit_all(repo, "本文を改稿")
        code, out = check(repo)
        assert code == 0, out
    finally:
        shutil.rmtree(repo)


def test_document_without_decision_log_passes():
    repo = new_repo()
    try:
        write_doc(repo, "knowledge/plain.md", "決定ログの無い文書。\n")
        commit_baseline(repo)
        overwrite(repo, "knowledge/plain.md", read_doc(repo, "knowledge/plain.md") + "\n追記。\n")
        commit_all(repo, "その文書を書き換える")
        code, out = check(repo)
        assert code == 0, out
        assert "インライン 0 本" in out, f"決定ログ無しの文書を数えている:\n{out}"
    finally:
        shutil.rmtree(repo)


def test_trailing_whitespace_only_change_passes():
    repo = new_repo()
    try:
        write_doc(repo, "knowledge/a.md", "本文。\n" + LOG_HEADER + ENTRY_A)
        commit_baseline(repo)
        text = read_doc(repo, "knowledge/a.md")
        overwrite(repo, "knowledge/a.md", text.replace("- 決定: A を採用する", "- 決定: A を採用する   "))
        commit_all(repo, "行末に空白が入った")
        code, out = check(repo)
        assert code == 0, out
    finally:
        shutil.rmtree(repo)


def test_trailing_blank_lines_removed_passes():
    repo = new_repo()
    try:
        write_doc(repo, "knowledge/a.md", "本文。\n" + LOG_HEADER + ENTRY_A)
        commit_baseline(repo)
        overwrite(repo, "knowledge/a.md", read_doc(repo, "knowledge/a.md") + "\n\n\n")
        commit_all(repo, "末尾に空行を積む")
        land_on_main(repo)
        overwrite(repo, "knowledge/a.md", read_doc(repo, "knowledge/a.md").rstrip() + "\n")
        commit_all(repo, "末尾の空行を消す")
        code, out = check(repo)
        assert code == 0, f"末尾空行の削除で落ちている:\n{out}"
    finally:
        shutil.rmtree(repo)


def test_section_after_decision_log_can_be_edited():
    repo = new_repo()
    try:
        write_doc(repo, "knowledge/a.md", "本文。\n" + LOG_HEADER + ENTRY_A)
        commit_baseline(repo)
        overwrite(repo, "knowledge/a.md", read_doc(repo, "knowledge/a.md") + "\n## 参考\n\n- リンク集\n")
        commit_all(repo, "参考節を追加")
        land_on_main(repo)
        text = read_doc(repo, "knowledge/a.md")
        overwrite(repo, "knowledge/a.md", text.replace("- リンク集", "- 全面的に書き直したリンク集"))
        commit_all(repo, "参考節を改稿")
        code, out = check(repo)
        assert code == 0, f"決定ログの外の節の編集で落ちている:\n{out}"
    finally:
        shutil.rmtree(repo)


def test_decision_log_heading_in_code_fence_is_ignored():
    repo = new_repo()
    try:
        write_doc(
            repo,
            "knowledge/guide.md",
            "書き方の見本:\n\n```markdown\n## 決定ログ\n\n### 見本のエントリ\n```\n",
        )
        commit_baseline(repo)
        land_on_main(repo)
        text = read_doc(repo, "knowledge/guide.md")
        overwrite(repo, "knowledge/guide.md", text.replace("### 見本のエントリ", "### 見本を差し替えた"))
        commit_all(repo, "見本を差し替える")
        code, out = check(repo)
        assert code == 0, out
        assert "インライン 0 本" in out, f"フェンス内の見出しを節として拾っている:\n{out}"
    finally:
        shutil.rmtree(repo)


def test_empty_decision_log_with_comment_only_passes():
    comment_only_log = (
        "\n---\n\n## 決定ログ\n\n"
        "<!-- この節は append-only です。 -->\n\n"
        "<!-- 関連する決定は別ファイルの決定ログに記録されている -->\n"
    )
    repo = new_repo()
    try:
        write_doc(repo, "knowledge/empty-log.md", "仕様本文。\n" + comment_only_log)
        commit_baseline(repo)
        land_on_main(repo)
        text = read_doc(repo, "knowledge/empty-log.md")
        overwrite(repo, "knowledge/empty-log.md", text.replace("仕様本文。", "仕様を全面改稿。"))
        commit_all(repo, "本文だけ改稿")
        code, out = check(repo)
        assert code == 0, f"コメントのみの決定ログで落ちている:\n{out}"
    finally:
        shutil.rmtree(repo)


def test_path_rename_in_decision_log_passes():
    repo = new_repo()
    try:
        (repo / "docs/old-data").mkdir(parents=True)
        (repo / "docs/old-data/note.md").write_text("# note\n", encoding="utf-8")
        entry_with_link = (
            "### パスリネームのテスト\n\n"
            "- 決定: [資料](../../docs/old-data/note.md) を参照\n"
            "- 理由: docs/old-data/ に一次資料を置いた\n"
        )
        write_doc(repo, "knowledge/a.md", "本文。\n" + LOG_HEADER + entry_with_link)
        commit_baseline(repo)
        land_on_main(repo)

        run_git(repo, "mv", "docs/old-data", "docs/new-data")
        text = read_doc(repo, "knowledge/a.md")
        overwrite(repo, "knowledge/a.md", text.replace("old-data", "new-data"))
        commit_all(repo, "old-data → new-data にリネーム")

        code, out = check(repo)
        assert code == 0, f"パスリネームのみの変更で落ちている:\n{out}"
    finally:
        shutil.rmtree(repo)


def test_dir_rename_with_full_path_link_passes():
    """F4: 置換ペアはディレクトリの改名前後の full path のみ。末尾成分だけのペアを
    作らなくても、リンクが改名後の full path を書いていれば置換で一致する。
    """
    repo = new_repo()
    try:
        (repo / "knowledge/old").mkdir(parents=True)
        (repo / "knowledge/old/a.md").write_text("# note\n", encoding="utf-8")
        entry_with_link = (
            "### パスリネームのテスト\n\n"
            "- 決定: [資料](knowledge/old/a.md) を参照\n"
            "- 理由: knowledge/old/ に資料を置いた\n"
        )
        write_doc(repo, "knowledge/b.md", "本文。\n" + LOG_HEADER + entry_with_link)
        commit_baseline(repo)
        land_on_main(repo)

        run_git(repo, "mv", "knowledge/old", "knowledge/new")
        text = read_doc(repo, "knowledge/b.md")
        overwrite(repo, "knowledge/b.md", text.replace("knowledge/old/a.md", "knowledge/new/a.md"))
        commit_all(repo, "knowledge/old → knowledge/new へリンクを追従させる")

        code, out = check(repo)
        assert code == 0, f"ディレクトリ改名に伴う full path リンクの追従が通らない:\n{out}"
    finally:
        shutil.rmtree(repo)


def test_recursive_subdirectory_doc_is_checked():
    repo = new_repo()
    try:
        write_doc(repo, "knowledge/sub/dir/nested.md", "本文。\n" + LOG_HEADER + ENTRY_A)
        commit_baseline(repo)
        text = read_doc(repo, "knowledge/sub/dir/nested.md")
        overwrite(repo, "knowledge/sub/dir/nested.md", text.replace("A を採用する", "A' を採用する"))
        commit_all(repo, "サブディレクトリの決定ログを改変")
        code, out = check(repo)
        assert code == 1, f"再帰でサブディレクトリを検出できていない:\n{out}"
        assert "knowledge/sub/dir/nested.md" in out, out
    finally:
        shutil.rmtree(repo)


# --- インライン方式: 落ちるケース ---------------------------------------------


def test_modified_entry_is_error():
    repo = new_repo()
    try:
        write_doc(repo, "knowledge/a.md", "本文。\n" + LOG_HEADER + ENTRY_A)
        commit_baseline(repo)
        text = read_doc(repo, "knowledge/a.md")
        overwrite(repo, "knowledge/a.md", text.replace("A を採用する", "A' を採用する"))
        commit_all(repo, "既存の決定を書き換える")
        code, out = check(repo)
        assert code == 1, f"既存エントリの改変を検出できていない:\n{out}"
        assert "既存エントリが変更されている" in out, out
        assert "knowledge/a.md" in out, out
    finally:
        shutil.rmtree(repo)


def test_deleted_entry_is_error():
    repo = new_repo()
    try:
        write_doc(repo, "knowledge/a.md", "本文。\n" + LOG_HEADER + ENTRY_A + "\n" + ENTRY_B)
        commit_baseline(repo)
        land_on_main(repo)
        write_doc(repo, "knowledge/a.md", "本文。\n" + LOG_HEADER + ENTRY_A)
        commit_all(repo, "2 件目を削除")
        code, out = check(repo)
        assert code == 1, f"エントリ削除を検出できていない:\n{out}"
        assert "既存エントリが削除されている" in out, out
    finally:
        shutil.rmtree(repo)


def test_deleted_section_is_error():
    repo = new_repo()
    try:
        write_doc(repo, "knowledge/a.md", "本文。\n" + LOG_HEADER + ENTRY_A)
        commit_baseline(repo)
        write_doc(repo, "knowledge/a.md", "本文。\n")
        commit_all(repo, "決定ログ節を削除")
        code, out = check(repo)
        assert code == 1, f"節の削除を検出できていない:\n{out}"
        assert "決定ログ節ごと消えている" in out, out
    finally:
        shutil.rmtree(repo)


def test_renamed_heading_is_error():
    repo = new_repo()
    try:
        write_doc(repo, "knowledge/a.md", "本文。\n" + LOG_HEADER + ENTRY_A)
        commit_baseline(repo)
        text = read_doc(repo, "knowledge/a.md")
        overwrite(repo, "knowledge/a.md", text.replace("## 決定ログ", "## 決定の記録"))
        commit_all(repo, "見出しを改名")
        code, out = check(repo)
        assert code == 1, f"見出しの改名を検出できていない:\n{out}"
        assert "決定ログ節ごと消えている" in out, out
    finally:
        shutil.rmtree(repo)


def test_fullwidth_space_in_heading_is_not_recognized_as_decision_log():
    """G14: `## 決定ログ` 見出しの区切りは半角スペース・タブだけ。全角空白に変わると
    見出しとして認識されず（見た目は似ているが Markdown の見出しとして機能しない）、
    節が消えたものとして扱う。"""
    repo = new_repo()
    try:
        write_doc(repo, "knowledge/a.md", "本文。\n" + LOG_HEADER + ENTRY_A)
        commit_baseline(repo)
        text = read_doc(repo, "knowledge/a.md")
        overwrite(repo, "knowledge/a.md", text.replace("## 決定ログ", "##　決定ログ"))
        commit_all(repo, "見出しの区切りを全角空白にする")
        code, out = check(repo)
        assert code == 1, f"全角空白の見出しをそのまま通してしまっている:\n{out}"
        assert "決定ログ節ごと消えている" in out, out
    finally:
        shutil.rmtree(repo)


def test_duplicate_decision_log_heading_in_base_unrelated_change_passes_with_warning():
    """G19: base で既に `## 決定ログ` 見出しが重複していた場合、無関係な変更だけなら
    通る（base の重複は警告にとどめ、新たなエラーとして扱わない）。"""
    repo = new_repo()
    try:
        duplicated = "本文。\n" + LOG_HEADER + ENTRY_A + "\n## 決定ログ\n\n" + ENTRY_B
        write_doc(repo, "knowledge/a.md", duplicated)
        commit_baseline(repo)
        text = read_doc(repo, "knowledge/a.md")
        overwrite(repo, "knowledge/a.md", text.replace("本文。", "本文（改稿）。"))
        commit_all(repo, "本文だけ改稿する（重複見出しはそのまま）")
        code, out = check(repo)
        assert code == 0, f"base で既に重複していた見出しを新規エラーとして扱っている:\n{out}"
        assert "⚠" in out and "knowledge/a.md" in out, f"base の重複を警告していない:\n{out}"
    finally:
        shutil.rmtree(repo)


def test_duplicate_decision_log_heading_in_base_resolved_in_current_passes_with_warning():
    """G19: base で重複していた `## 決定ログ` 見出しが、現在の変更で単一に解消されて
    いれば通る（base の重複は警告のみで、exit code に影響しない）。

    `extract_section()` は見出しが複数あると最後の出現を基準に節を切り出すため、ここ
    では「見出しがうっかり連続して 2 回書かれている（間に本来のエントリが無い）」形の
    重複で検証する。これなら余分な見出し行を取り除くだけで、節の内容自体は base と
    現在で変わらない。
    """
    repo = new_repo()
    try:
        comment = "<!-- この節は append-only です。既存エントリの変更・削除は検出されます。 -->\n\n"
        duplicated = "本文。\n\n---\n\n## 決定ログ\n\n## 決定ログ\n\n" + comment + ENTRY_A
        write_doc(repo, "knowledge/a.md", duplicated)
        commit_baseline(repo)
        resolved = "本文。\n\n---\n\n## 決定ログ\n\n" + comment + ENTRY_A
        write_doc(repo, "knowledge/a.md", resolved)
        commit_all(repo, "うっかり連続していた見出しを一つに統合する")
        code, out = check(repo)
        assert code == 0, f"base の重複が現在で解消されたのに通らない:\n{out}"
        assert "⚠" in out, f"base の重複を警告していない:\n{out}"
    finally:
        shutil.rmtree(repo)


def test_new_document_with_duplicate_decision_log_heading_is_error():
    """G19: base に無い新規文書で `## 決定ログ` 見出しが重複していれば error にする
    （新規文書は append-only 検査の対象外だが、見出しの重複は新規文書でも許可しない）。"""
    repo = new_repo()
    try:
        write_doc(repo, "knowledge/a.md", "本文。\n" + LOG_HEADER + ENTRY_A)
        commit_baseline(repo)
        duplicated = "新規文書。\n" + LOG_HEADER + ENTRY_A + "\n## 決定ログ\n\n" + ENTRY_B
        write_doc(repo, "knowledge/new.md", duplicated)
        commit_all(repo, "重複した見出しを持つ新規文書を追加する")
        code, out = check(repo)
        assert code == 1, f"新規文書の見出し重複を検出できていない:\n{out}"
        assert "knowledge/new.md" in out, out
    finally:
        shutil.rmtree(repo)


def test_duplicate_decision_log_heading_added_in_current_is_error():
    repo = new_repo()
    try:
        write_doc(repo, "knowledge/a.md", "本文。\n" + LOG_HEADER + ENTRY_A)
        commit_baseline(repo)
        text = read_doc(repo, "knowledge/a.md")
        overwrite(repo, "knowledge/a.md", text + "\n## 決定ログ\n\n" + ENTRY_B)
        commit_all(repo, "決定ログ見出しをもう一つ追加")
        code, out = check(repo)
        assert code == 1, f"現在側で増えた `## 決定ログ` 見出しの重複を検出できていない:\n{out}"
        assert "knowledge/a.md" in out, out
    finally:
        shutil.rmtree(repo)


def test_inserted_entry_at_head_is_error():
    repo = new_repo()
    try:
        write_doc(repo, "knowledge/a.md", "本文。\n" + LOG_HEADER + ENTRY_A)
        commit_baseline(repo)
        write_doc(repo, "knowledge/a.md", "本文。\n" + LOG_HEADER + ENTRY_B + "\n" + ENTRY_A)
        commit_all(repo, "先頭へ挿入")
        code, out = check(repo)
        assert code == 1, f"先頭への挿入を検出できていない:\n{out}"
        assert "既存エントリが変更されている" in out, out
    finally:
        shutil.rmtree(repo)


def test_content_change_with_path_rename_is_error():
    repo = new_repo()
    try:
        (repo / "docs/old-data").mkdir(parents=True)
        (repo / "docs/old-data/note.md").write_text("# note\n", encoding="utf-8")
        entry_with_link = (
            "### パスリネームのテスト\n\n"
            "- 決定: [資料](../../docs/old-data/note.md) を参照\n"
            "- 理由: テスト用の理由\n"
        )
        write_doc(repo, "knowledge/a.md", "本文。\n" + LOG_HEADER + entry_with_link)
        commit_baseline(repo)
        land_on_main(repo)

        run_git(repo, "mv", "docs/old-data", "docs/new-data")
        text = read_doc(repo, "knowledge/a.md")
        text = text.replace("old-data", "new-data").replace("テスト用の理由", "書き換えた理由")
        overwrite(repo, "knowledge/a.md", text)
        commit_all(repo, "リネーム＋内容変更")

        code, out = check(repo)
        assert code == 1, f"パスリネーム以外の変更を見逃している:\n{out}"
        assert "既存エントリが変更されている" in out, out
    finally:
        shutil.rmtree(repo)


def test_dir_rename_does_not_allow_suffix_only_substring_change():
    """F4: `src/v1` → `src/v2` の改名からは `src/v1`/`src/v2` の full path ペアしか
    作らない。末尾成分だけのペア（`v1`→`v2`）を禁止し、本文中の「v1」「v2」のような
    無関係な置換を許容しないことを確認する。
    """
    repo = new_repo()
    try:
        (repo / "src/v1").mkdir(parents=True)
        (repo / "src/v1/impl.md").write_text("# impl v1\n" + ("x" * 200) + "\n", encoding="utf-8")
        entry = (
            "### 実装方式の選定\n\n"
            "- 決定: 方式 v1 を採用する\n"
            "- 理由: テスト用の理由\n"
        )
        write_doc(repo, "knowledge/a.md", "本文。\n" + LOG_HEADER + entry)
        commit_baseline(repo)
        land_on_main(repo)

        run_git(repo, "mv", "src/v1", "src/v2")
        text = read_doc(repo, "knowledge/a.md")
        overwrite(repo, "knowledge/a.md", text.replace("方式 v1 を採用する", "方式 v2 を採用する"))
        commit_all(repo, "src/v1 → src/v2 のリネームと同時に決定を書き換える")

        code, out = check(repo)
        assert code == 1, f"ディレクトリ改名を理由に本文の書き換えまで許容している:\n{out}"
        assert "既存エントリが変更されている" in out, out
    finally:
        shutil.rmtree(repo)


def test_file_move_top_level_dir_rename_does_not_allow_prose_substitution():
    """G2: 単一ファイルの移動由来の末尾成分だけのトークン（`/` を含まない）は、直後に
    `/` が続かない地の文の一致（例: 「正本は docs」）には当てない。"""
    repo = new_repo()
    try:
        (repo / "docs").mkdir(parents=True)
        (repo / "docs/x.md").write_text("# x\n", encoding="utf-8")
        entry = (
            "### 正本の選定\n\n"
            "- 決定: 正本は docs とする\n"
            "- 理由: テスト用の理由\n"
        )
        write_doc(repo, "knowledge/a.md", "本文。\n" + LOG_HEADER + entry)
        commit_baseline(repo)
        land_on_main(repo)

        run_git(repo, "mv", "docs/x.md", "knowledge/x.md")
        text = read_doc(repo, "knowledge/a.md")
        overwrite(repo, "knowledge/a.md", text.replace("正本は docs とする", "正本は knowledge とする"))
        commit_all(repo, "docs/x.md を knowledge/x.md へ移動し、地の文も書き換える")

        code, out = check(repo)
        assert code == 1, f"単一ファイル移動由来のトークンで地の文の書き換えまで通してしまっている:\n{out}"
        assert "既存エントリが変更されている" in out, out
    finally:
        shutil.rmtree(repo)


def test_dir_rename_with_spaces_does_not_allow_prose_substitution():
    """G2: ディレクトリ名に空白を含む改名でも、地の文の書き換えまでは許容しない
    （空白を含むトークンでも境界判定・エスケープが正しく働くことの確認）。"""
    repo = new_repo()
    try:
        (repo / "docs/raw data").mkdir(parents=True)
        (repo / "docs/raw data/note.md").write_text("# note\n", encoding="utf-8")
        entry = (
            "### 資料の置き場所\n\n"
            "- 決定: 資料は raw data に置く\n"
            "- 理由: テスト用の理由\n"
        )
        write_doc(repo, "knowledge/a.md", "本文。\n" + LOG_HEADER + entry)
        commit_baseline(repo)
        land_on_main(repo)

        run_git(repo, "mv", "docs/raw data", "docs/clean data")
        text = read_doc(repo, "knowledge/a.md")
        overwrite(repo, "knowledge/a.md", text.replace("資料は raw data に置く", "資料は clean data に置く"))
        commit_all(repo, "docs/raw data → docs/clean data のリネームと同時に決定を書き換える")

        code, out = check(repo)
        assert code == 1, f"空白を含むディレクトリ名への改名を理由に地の文の書き換えまで許容している:\n{out}"
        assert "既存エントリが変更されている" in out, out
    finally:
        shutil.rmtree(repo)


def test_relative_link_leaf_rename_follows_via_suffix_pair():
    """G2: ディレクトリの末尾成分だけのリネームでも、相対リンクの途中に出てくる
    ディレクトリ名（末尾成分）を追従させる（復活させた末尾成分ペア）。"""
    repo = new_repo()
    try:
        (repo / "assets/original-docs").mkdir(parents=True)
        (repo / "assets/original-docs/a.md").write_text("# a\n", encoding="utf-8")
        entry = (
            "### 資料リンクのテスト\n\n"
            "- 決定: [資料](../original-docs/a.md) を参照\n"
            "- 理由: テスト用の理由\n"
        )
        write_doc(repo, "knowledge/b.md", "本文。\n" + LOG_HEADER + entry)
        commit_baseline(repo)
        land_on_main(repo)

        run_git(repo, "mv", "assets/original-docs", "assets/docs-original")
        text = read_doc(repo, "knowledge/b.md")
        overwrite(repo, "knowledge/b.md", text.replace("../original-docs/a.md", "../docs-original/a.md"))
        commit_all(repo, "assets/original-docs → assets/docs-original へリンクを追従させる")

        code, out = check(repo)
        assert code == 0, f"末尾成分のリネームに伴う相対リンクの追従が通らない:\n{out}"
    finally:
        shutil.rmtree(repo)


def test_full_path_after_double_dash_follows_rename():
    """G2 回帰: `-- docs/original-docs` のような記法内の full path も、ディレクトリ
    改名に正しく追従する（末尾成分ペアを復活させても full path 側の挙動は変えていない
    ことの確認）。"""
    repo = new_repo()
    try:
        (repo / "docs/original-docs").mkdir(parents=True)
        (repo / "docs/original-docs/a.md").write_text("# a\n", encoding="utf-8")
        entry = (
            "### 移動コマンドの記録\n\n"
            "- 決定: `git mv -- docs/original-docs docs/archived-docs` で移動する\n"
            "- 理由: テスト用の理由\n"
        )
        write_doc(repo, "knowledge/c.md", "本文。\n" + LOG_HEADER + entry)
        commit_baseline(repo)
        land_on_main(repo)

        run_git(repo, "mv", "docs/original-docs", "docs/archived-docs")
        text = read_doc(repo, "knowledge/c.md")
        overwrite(
            repo, "knowledge/c.md",
            text.replace(
                "docs/original-docs docs/archived-docs",
                "docs/archived-docs docs/archived-docs",
            ),
        )
        commit_all(repo, "リネームに合わせて記述を追従させる")

        code, out = check(repo)
        assert code == 0, f"-- を伴う full path への追従が通らない:\n{out}"
    finally:
        shutil.rmtree(repo)


def test_dir_rename_into_own_subdirectory_follows_full_path():
    """3 巡目レビュー: `docs/v1` → `docs/v1/legacy` のようにサブディレクトリへ移動する
    改名でも、full path のペアが `docs/v1` → `docs/v1/legacy` として正しく作られ、
    full path のリンクが追従する（旧実装は末尾成分ペアを `v1` → `legacy` として作って
    しまい、無関係な地の文への誤爆の種になっていた）。"""
    repo = new_repo()
    try:
        (repo / "docs/v1").mkdir(parents=True)
        (repo / "docs/v1/a.md").write_text("# a\n", encoding="utf-8")
        entry = (
            "### 資料リンクのテスト\n\n"
            "- 決定: [資料](../../docs/v1/a.md) を参照\n"
            "- 理由: テスト用の理由\n"
        )
        write_doc(repo, "knowledge/b.md", "本文。\n" + LOG_HEADER + entry)
        commit_baseline(repo)
        land_on_main(repo)

        (repo / "docs/v1/legacy").mkdir(parents=True)
        run_git(repo, "mv", "docs/v1/a.md", "docs/v1/legacy/a.md")
        text = read_doc(repo, "knowledge/b.md")
        overwrite(repo, "knowledge/b.md", text.replace("docs/v1/a.md", "docs/v1/legacy/a.md"))
        commit_all(repo, "docs/v1/a.md を docs/v1/legacy/ へ移動する")

        code, out = check(repo)
        assert code == 0, f"サブディレクトリへの移動に伴う full path の追従が通らない:\n{out}"
    finally:
        shutil.rmtree(repo)


def test_nested_dir_rename_follows_full_path_from_leaf_file():
    """3 巡目レビュー: 改名対象の `src/old` 配下に、実際にリネームされるファイル
    （`src/old/sub/z.md`）が 2 階層下にしか無い場合でも、`src/old` → `src/new` の
    full path ペアが作られ、`src/old` 直下への（実在しなくてもよい）リンク参照も
    追従する（旧実装はリネームされたファイルの直上ディレクトリ（`sub`）からしか
    ペアを作らず、`src/old/sub` → `src/new/sub` にしかならないため、`src/old` 直下
    への参照には効かず error になっていた）。"""
    repo = new_repo()
    try:
        (repo / "src/old/sub").mkdir(parents=True)
        (repo / "src/old/sub/z.md").write_text("# z\n", encoding="utf-8")
        entry = (
            "### 資料リンクのテスト\n\n"
            "- 決定: [資料](../../src/old/readme.md) を参照\n"
            "- 理由: テスト用の理由\n"
        )
        write_doc(repo, "knowledge/b.md", "本文。\n" + LOG_HEADER + entry)
        commit_baseline(repo)
        land_on_main(repo)

        run_git(repo, "mv", "src/old", "src/new")
        text = read_doc(repo, "knowledge/b.md")
        overwrite(repo, "knowledge/b.md", text.replace("src/old/readme.md", "src/new/readme.md"))
        commit_all(repo, "src/old → src/new のリネームに伴いリンクを追従させる")

        code, out = check(repo)
        assert code == 0, f"ファイルの 2 階層上のディレクトリ改名への追従が通らない:\n{out}"
    finally:
        shutil.rmtree(repo)


def test_file_moved_into_new_subdirectory_of_parent_follows_full_path():
    """3 巡目レビュー: `knowledge/x.md` → `knowledge/archive/x.md` のように、親
    ディレクトリの下へ新設したサブディレクトリへ移動する改名でも、`knowledge` →
    `knowledge/archive` の full path ペアが作られてリンクが追従する。"""
    repo = new_repo()
    try:
        write_doc(repo, "knowledge/x.md", "# x\n")
        entry = (
            "### 資料リンクのテスト\n\n"
            "- 決定: [資料](knowledge/x.md) を参照\n"
            "- 理由: テスト用の理由\n"
        )
        write_doc(repo, "knowledge/b.md", "本文。\n" + LOG_HEADER + entry)
        commit_baseline(repo)
        land_on_main(repo)

        (repo / "knowledge/archive").mkdir(parents=True)
        run_git(repo, "mv", "knowledge/x.md", "knowledge/archive/x.md")
        text = read_doc(repo, "knowledge/b.md")
        overwrite(repo, "knowledge/b.md", text.replace("knowledge/x.md", "knowledge/archive/x.md"))
        commit_all(repo, "knowledge/x.md を knowledge/archive/ へ移動する")

        code, out = check(repo)
        assert code == 0, f"親ディレクトリ配下への新設サブディレクトリ移動への追従が通らない:\n{out}"
    finally:
        shutil.rmtree(repo)


def test_dir_rename_into_subdirectory_does_not_allow_leaf_only_link_rewrite():
    """3 巡目レビュー: `docs/v1` → `docs/v1/legacy` の移動からは末尾成分だけのペア
    （`v1` → `legacy`）を作らない。相対リンクの末尾成分だけを書き換えた
    `](../v1/b.md)` → `](../legacy/b.md)` は、実際には存在しない改名の追従を主張して
    いるだけなので error にする（旧実装はファイル直上のディレクトリ名から末尾成分
    ペアを作ってしまい、この誤った書き換えを素通りさせていた）。full path への参照は
    混ぜず、末尾成分だけの参照を単独で検証する（full path ペアとの置換順序に由来する
    副作用で見かけ上 error になる偽陽性を避けるため）。"""
    repo = new_repo()
    try:
        (repo / "docs/v1").mkdir(parents=True)
        (repo / "docs/v1/a.md").write_text("# a\n", encoding="utf-8")
        entry = (
            "### 資料リンクのテスト\n\n"
            "- 決定: [関連資料](../v1/b.md) を参照\n"
            "- 理由: テスト用の理由\n"
        )
        write_doc(repo, "knowledge/c.md", "本文。\n" + LOG_HEADER + entry)
        commit_baseline(repo)
        land_on_main(repo)

        (repo / "docs/v1/legacy").mkdir(parents=True)
        run_git(repo, "mv", "docs/v1/a.md", "docs/v1/legacy/a.md")
        text = read_doc(repo, "knowledge/c.md")
        # 実際に改名されたのは a.md で b.md は無関係。末尾成分だけを誤って書き換える。
        overwrite(repo, "knowledge/c.md", text.replace("../v1/b.md", "../legacy/b.md"))
        commit_all(repo, "b.md へのリンクだけ誤って書き換える")

        code, out = check(repo)
        assert code == 1, f"存在しない改名を主張する末尾成分だけの書き換えを通してしまっている:\n{out}"
        assert "既存エントリが変更されている" in out, out
    finally:
        shutil.rmtree(repo)


def test_inline_file_deletion_is_error():
    repo = new_repo()
    try:
        write_doc(repo, "knowledge/a.md", "本文。\n" + LOG_HEADER + ENTRY_A)
        commit_baseline(repo)
        (repo / "knowledge/a.md").unlink()
        commit_all(repo, "決定ログを持つ文書を削除")
        code, out = check(repo)
        assert code == 1, f"文書の削除を検出できていない:\n{out}"
        assert "削除されている" in out, out
    finally:
        shutil.rmtree(repo)


def test_violation_reports_both_sides():
    repo = new_repo()
    try:
        write_doc(repo, "knowledge/a.md", "本文。\n" + LOG_HEADER + ENTRY_A)
        commit_baseline(repo)
        text = read_doc(repo, "knowledge/a.md")
        overwrite(repo, "knowledge/a.md", text.replace("A を採用する", "A' を採用する"))
        commit_all(repo, "既存の決定を書き換える")
        code, out = check(repo)
        assert code == 1, out
        assert "- base:" in out and "+ 現在:" in out, f"差分の両側が出ていない:\n{out}"
        assert "A を採用する" in out and "A' を採用する" in out, out
    finally:
        shutil.rmtree(repo)


def test_japanese_filename_inline():
    repo = new_repo()
    try:
        write_doc(repo, "knowledge/決定記録.md", "本文。\n" + LOG_HEADER + ENTRY_A)
        commit_baseline(repo)
        text = read_doc(repo, "knowledge/決定記録.md")
        overwrite(repo, "knowledge/決定記録.md", text.replace("A を採用する", "A' を採用する"))
        commit_all(repo, "日本語ファイル名の決定ログを改変")
        code, out = check(repo)
        assert code == 1, out
        assert "決定記録.md" in out, out
    finally:
        shutil.rmtree(repo)


def test_diff_config_overrides_do_not_hide_violations():
    repo = new_repo()
    try:
        write_doc(repo, "knowledge/a.md", "本文。\n" + LOG_HEADER + ENTRY_A)
        commit_baseline(repo)
        poison_diff_config(repo)
        overwrite(repo, "knowledge/a.md", read_doc(repo, "knowledge/a.md").replace("A を採用する", "A' を採用する"))
        commit_all(repo, "決定を書き換える（diff 設定を汚染済み）")
        code, out = check(repo)
        assert code == 1, f"diff 設定の汚染で検出が隠れている:\n{out}"
        assert "既存エントリが変更されている" in out, out
    finally:
        shutil.rmtree(repo)


# --- 独立ファイル方式 ---------------------------------------------------------


def test_adr_regular_supersede_passes():
    repo = new_repo()
    try:
        write_doc(repo, "knowledge/adr/0001-first.md", adr_text("Accepted — 2026-01-01"))
        write_doc(
            repo,
            "knowledge/adr/README.md",
            readme_text([("0001", "最初の決定", "Accepted", "2026-01-01")]),
        )
        commit_baseline(repo)

        write_doc(repo, "knowledge/adr/0002-second.md", adr_text("Accepted — 2026-02-01"))
        status_text = (
            "Superseded by 0002-second — 2026-02-01\n\n"
            "- 有効な部分: なし\n- 失効した部分: すべて"
        )
        overwrite(repo, "knowledge/adr/0001-first.md", adr_text(status_text))
        overwrite(
            repo,
            "knowledge/adr/README.md",
            readme_text(
                [
                    ("0001", "最初の決定", "Superseded by 0002-second", "2026-01-01"),
                    ("0002", "次の決定", "Accepted", "2026-02-01"),
                ]
            ),
        )
        commit_all(repo, "ADR 0001 を正規に supersede する")

        code, out = check(repo)
        assert code == 0, out
        assert "ADR 1 本" in out, out
    finally:
        shutil.rmtree(repo)


def test_adr_body_change_outside_status_is_warn_exit0():
    repo = new_repo()
    try:
        write_doc(repo, "knowledge/adr/0001-first.md", adr_text("Accepted — 2026-01-01"))
        commit_baseline(repo)
        text = read_doc(repo, "knowledge/adr/0001-first.md")
        overwrite(repo, "knowledge/adr/0001-first.md", text.replace("背景の説明。", "背景の説明を誤字修正した。"))
        commit_all(repo, "背景の説明を修正")
        code, out = check(repo)
        assert code == 0, f"ステータス節の外の変更で exit 0 になっていない:\n{out}"
        assert "⚠" in out, f"WARN が出ていない:\n{out}"
    finally:
        shutil.rmtree(repo)


def test_adr_body_decision_rewritten_same_line_is_warn():
    """F8: 行数が変わらない（同じ行の中の）書き換えは、決定の書き換えであっても
    機械では誤字修正と区別できないため WARN のまま。"""
    repo = new_repo()
    try:
        write_doc(
            repo, "knowledge/adr/0001-first.md",
            adr_text("Accepted — 2026-01-01", body="方式 v1 を採用する。\n"),
        )
        commit_baseline(repo)
        overwrite(
            repo, "knowledge/adr/0001-first.md",
            adr_text("Accepted — 2026-01-01", body="方式 v2 を採用する。\n"),
        )
        commit_all(repo, "決定を同じ行の中で書き換える")
        code, out = check(repo)
        assert code == 0, f"同じ行内の書き換えが exit 0 にならない:\n{out}"
        assert "⚠" in out, f"WARN が出ていない:\n{out}"
    finally:
        shutil.rmtree(repo)


def test_adr_body_line_added_outside_status_is_error():
    """F8: `## ステータス` 節の外で行が増えるのは誤字修正の形ではない。error にする。"""
    repo = new_repo()
    try:
        write_doc(
            repo, "knowledge/adr/0001-first.md",
            adr_text("Accepted — 2026-01-01", body="行1。\n"),
        )
        commit_baseline(repo)
        overwrite(
            repo, "knowledge/adr/0001-first.md",
            adr_text("Accepted — 2026-01-01", body="行1。\n行2を追加。\n"),
        )
        commit_all(repo, "背景に行を追加")
        code, out = check(repo)
        assert code == 1, f"ステータス節の外への行追加が error になっていない:\n{out}"
        assert "行の追加・削除" in out, out
    finally:
        shutil.rmtree(repo)


def test_adr_body_line_removed_outside_status_is_error():
    """F8: `## ステータス` 節の外で行が減るのも誤字修正の形ではない。error にする。"""
    repo = new_repo()
    try:
        write_doc(
            repo, "knowledge/adr/0001-first.md",
            adr_text("Accepted — 2026-01-01", body="行1。\n行2。\n"),
        )
        commit_baseline(repo)
        overwrite(
            repo, "knowledge/adr/0001-first.md",
            adr_text("Accepted — 2026-01-01", body="行1。\n"),
        )
        commit_all(repo, "背景の行を削除")
        code, out = check(repo)
        assert code == 1, f"ステータス節の外の行削除が error になっていない:\n{out}"
        assert "行の追加・削除" in out, out
    finally:
        shutil.rmtree(repo)


def test_adr_body_two_separate_same_position_replacements_are_both_warned():
    """G1: 別々の位置で行数が変わらない置き換えが複数あれば、両方を警告として表示する
    （difflib の opcode 単位で、equal 以外の区間すべてを検査する）。"""
    repo = new_repo()
    try:
        write_doc(
            repo, "knowledge/adr/0001-first.md",
            adr_text("Accepted — 2026-01-01", body="行1。\n行2。\n行3。\n"),
        )
        commit_baseline(repo)
        overwrite(
            repo, "knowledge/adr/0001-first.md",
            adr_text("Accepted — 2026-01-01", body="行1改。\n行2。\n行3改。\n"),
        )
        commit_all(repo, "2 か所を同じ行数で置き換える")
        code, out = check(repo)
        assert code == 0, f"行数が変わらない複数置換が exit 0 にならない:\n{out}"
        assert "行1。" in out and "行1改。" in out, f"1 か所目の差分が表示されていない:\n{out}"
        assert "行3。" in out and "行3改。" in out, f"2 か所目の差分が表示されていない:\n{out}"
    finally:
        shutil.rmtree(repo)


def test_adr_body_delete_and_insert_elsewhere_same_total_length_is_error():
    """G1: 総行数が同じでも、1 行削除＋別の位置への 1 行追加（対応が取れない変更）は
    difflib では delete/insert の opcode になり error にする。"""
    repo = new_repo()
    try:
        write_doc(
            repo, "knowledge/adr/0001-first.md",
            adr_text("Accepted — 2026-01-01", body="行1。\n行2。\n行3。\n"),
        )
        commit_baseline(repo)
        overwrite(
            repo, "knowledge/adr/0001-first.md",
            adr_text("Accepted — 2026-01-01", body="行2。\n行3。\n行4追加。\n"),
        )
        commit_all(repo, "先頭を削除し末尾に別の行を追加する")
        code, out = check(repo)
        assert code == 1, f"総行数が同じ削除＋挿入を見逃している:\n{out}"
        assert "行の追加・削除" in out, out
    finally:
        shutil.rmtree(repo)


def test_adr_deleted_is_error():
    repo = new_repo()
    try:
        write_doc(repo, "knowledge/adr/0001-first.md", adr_text("Accepted — 2026-01-01"))
        commit_baseline(repo)
        (repo / "knowledge/adr/0001-first.md").unlink()
        commit_all(repo, "ADR を削除")
        code, out = check(repo)
        assert code == 1, out
        assert "削除されている" in out, out
    finally:
        shutil.rmtree(repo)


def test_adr_renamed_is_error():
    repo = new_repo()
    try:
        write_doc(repo, "knowledge/adr/0001-first.md", adr_text("Accepted — 2026-01-01"))
        commit_baseline(repo)
        run_git(repo, "mv", "knowledge/adr/0001-first.md", "knowledge/adr/0001-first-renamed.md")
        commit_all(repo, "ADR を改名")
        code, out = check(repo)
        assert code == 1, out
        assert "改名されている" in out, out
    finally:
        shutil.rmtree(repo)


def test_adr_status_heading_count_change_is_warn():
    """F7: `## ステータス` 見出しの数が base と現在で変わったら警告する。"""
    repo = new_repo()
    try:
        write_doc(repo, "knowledge/adr/0001-first.md", adr_text("Accepted — 2026-01-01"))
        commit_baseline(repo)
        text = read_doc(repo, "knowledge/adr/0001-first.md")
        overwrite(
            repo, "knowledge/adr/0001-first.md",
            text + "\n## ステータス\n\n二重に生えた節\n",
        )
        commit_all(repo, "ステータス節見出しをもう一つ追加")
        code, out = check(repo)
        assert "見出しが増減した" in out, f"ステータス節見出しの増減を検出できていない:\n{out}"
    finally:
        shutil.rmtree(repo)


def test_adr_status_section_note_added_is_warn_not_error():
    """G3: `## ステータス` 節内のステータス値の行（節内最初の非空行）以外への追記は
    警告にとどめる（supersede の経緯等の追記を許容するため error にしない）。"""
    repo = new_repo()
    try:
        write_doc(repo, "knowledge/adr/0001-first.md", adr_text("Accepted — 2026-01-01"))
        commit_baseline(repo)
        overwrite(
            repo, "knowledge/adr/0001-first.md",
            adr_text("Accepted — 2026-01-01\n\n- 補足: 運用開始後に確認済み"),
        )
        commit_all(repo, "ステータス節に補足を追記する")
        code, out = check(repo)
        assert code == 0, f"ステータス節内の追記が error になっている:\n{out}"
        assert "⚠" in out and "ステータス" in out, f"ステータス節の変化を警告していない:\n{out}"
    finally:
        shutil.rmtree(repo)


def test_adr_status_section_note_removed_is_warn_not_error():
    """G3: `## ステータス` 節内のステータス値の行以外の削除も警告にとどめる。"""
    repo = new_repo()
    try:
        write_doc(
            repo, "knowledge/adr/0001-first.md",
            adr_text("Accepted — 2026-01-01\n\n- 補足: 運用開始後に確認済み"),
        )
        commit_baseline(repo)
        overwrite(repo, "knowledge/adr/0001-first.md", adr_text("Accepted — 2026-01-01"))
        commit_all(repo, "ステータス節の補足を削除する")
        code, out = check(repo)
        assert code == 0, f"ステータス節内の削除が error になっている:\n{out}"
        assert "⚠" in out and "ステータス" in out, f"ステータス節の変化を警告していない:\n{out}"
    finally:
        shutil.rmtree(repo)


def test_adr_dir_subdirectory_is_warn():
    """F9: `--adr-dir` 配下にサブディレクトリがあれば、検査対象外になる旨を警告する。"""
    repo = new_repo()
    try:
        write_doc(repo, "knowledge/adr/0001-first.md", adr_text("Accepted — 2026-01-01"))
        (repo / "knowledge/adr/legacy").mkdir(parents=True)
        (repo / "knowledge/adr/legacy/note.md").write_text("# old\n", encoding="utf-8")
        commit_baseline(repo)
        code, out = check(repo)
        assert code == 0, out
        assert "legacy" in out and "⚠" in out, f"サブディレクトリの存在を警告していない:\n{out}"
    finally:
        shutil.rmtree(repo)


def test_adr_dir_non_md_file_is_warn():
    """F9: `--adr-dir` 配下に `.md` 以外のファイル（README.md を除く）があれば警告する。"""
    repo = new_repo()
    try:
        write_doc(repo, "knowledge/adr/0001-first.md", adr_text("Accepted — 2026-01-01"))
        write_doc(repo, "knowledge/adr/notes.txt", "メモ\n")
        commit_baseline(repo)
        code, out = check(repo)
        assert code == 0, out
        assert "notes.txt" in out, f".md 以外のファイルを警告していない:\n{out}"
    finally:
        shutil.rmtree(repo)


def test_adr_dir_irregular_file_deleted_is_warn():
    """F9: base にあった検査対象外ファイルの削除も警告する（検査対象外のため検出できない旨）。"""
    repo = new_repo()
    try:
        write_doc(repo, "knowledge/adr/0001-first.md", adr_text("Accepted — 2026-01-01"))
        write_doc(repo, "knowledge/adr/notes.txt", "メモ\n")
        commit_baseline(repo)
        (repo / "knowledge/adr/notes.txt").unlink()
        commit_all(repo, "対象外ファイルを削除")
        code, out = check(repo)
        assert code == 0, out
        assert "notes.txt" in out, f"対象外ファイルの削除を警告していない:\n{out}"
    finally:
        shutil.rmtree(repo)


def test_gitignored_untracked_file_in_adr_dir_is_not_warned():
    """G16: 作業ツリーと比べるとき、`--adr-dir` 配下の一覧は追跡済みファイルと
    `.gitignore` の対象外の未追跡ファイルだけにする。`.gitignore` 対象の未追跡ファイル
    （`.DS_Store` 等）はノイズとして警告しない。"""
    repo = new_repo()
    try:
        write_doc(repo, "knowledge/adr/0001-first.md", adr_text("Accepted — 2026-01-01"))
        write_doc(repo, ".gitignore", ".DS_Store\n")
        commit_baseline(repo)
        (repo / "knowledge/adr/.DS_Store").write_text("ds\n", encoding="utf-8")
        code, out = check(repo)
        assert code == 0, out
        assert ".DS_Store" not in out, f".gitignore 対象のファイルを警告している:\n{out}"
    finally:
        shutil.rmtree(repo)


def test_readme_row_deleted_is_error():
    repo = new_repo()
    try:
        write_doc(repo, "knowledge/adr/0001-first.md", adr_text("Accepted — 2026-01-01"))
        write_doc(repo, "knowledge/adr/0002-second.md", adr_text("Accepted — 2026-02-01"))
        write_doc(
            repo,
            "knowledge/adr/README.md",
            readme_text(
                [
                    ("0001", "最初の決定", "Accepted", "2026-01-01"),
                    ("0002", "次の決定", "Accepted", "2026-02-01"),
                ]
            ),
        )
        commit_baseline(repo)
        overwrite(
            repo,
            "knowledge/adr/README.md",
            readme_text([("0001", "最初の決定", "Accepted", "2026-01-01")]),
        )
        commit_all(repo, "README から 0002 の行を削除")
        code, out = check(repo)
        assert code == 1, out
        assert "一覧の行が削除されている" in out, out
    finally:
        shutil.rmtree(repo)


def test_readme_non_status_cell_change_is_warn():
    repo = new_repo()
    try:
        write_doc(repo, "knowledge/adr/0001-first.md", adr_text("Accepted — 2026-01-01"))
        write_doc(
            repo,
            "knowledge/adr/README.md",
            readme_text([("0001", "最初の決定", "Accepted", "2026-01-01")]),
        )
        commit_baseline(repo)
        overwrite(
            repo,
            "knowledge/adr/README.md",
            readme_text([("0001", "最初の決定（誤字修正）", "Accepted", "2026-01-01")]),
        )
        commit_all(repo, "README のタイトル列を修正")
        code, out = check(repo)
        assert code == 0, out
        assert "⚠" in out and "列目が変わっている" in out, out
    finally:
        shutil.rmtree(repo)


def test_readme_status_mismatch_with_adr_is_warn():
    repo = new_repo()
    try:
        write_doc(repo, "knowledge/adr/0001-first.md", adr_text("Accepted — 2026-01-01"))
        write_doc(
            repo,
            "knowledge/adr/README.md",
            readme_text([("0001", "最初の決定", "Accepted", "2026-01-01")]),
        )
        commit_baseline(repo)
        overwrite(
            repo,
            "knowledge/adr/README.md",
            readme_text([("0001", "最初の決定", "Deprecated", "2026-01-01")]),
        )
        commit_all(repo, "README のステータスだけ書き換える")
        code, out = check(repo)
        assert code == 0, out
        assert "食い違っている" in out, out
    finally:
        shutil.rmtree(repo)


def test_readme_status_mismatch_with_new_adr_is_warn():
    """F5: base に無い新規 ADR についても、README のステータス列と ADR 本体の
    ステータス節の食い違いを検出する。"""
    repo = new_repo()
    try:
        write_doc(repo, "knowledge/adr/0001-first.md", adr_text("Accepted — 2026-01-01"))
        write_doc(
            repo, "knowledge/adr/README.md",
            readme_text([("0001", "最初の決定", "Accepted", "2026-01-01")]),
        )
        commit_baseline(repo)

        write_doc(repo, "knowledge/adr/0002-second.md", adr_text("Proposed — 2026-02-01"))
        overwrite(
            repo, "knowledge/adr/README.md",
            readme_text(
                [
                    ("0001", "最初の決定", "Accepted", "2026-01-01"),
                    ("0002", "次の決定", "Accepted", "2026-02-01"),
                ]
            ),
        )
        commit_all(repo, "新規 ADR を Proposed で追加、README は Accepted と書く")

        code, out = check(repo)
        assert code == 0, out
        assert "食い違っている" in out, f"新規 ADR との食い違いを検出できていない:\n{out}"
    finally:
        shutil.rmtree(repo)


def test_both_methods_combined():
    repo = new_repo()
    try:
        write_doc(repo, "knowledge/a.md", "本文。\n" + LOG_HEADER + ENTRY_A)
        write_doc(repo, "knowledge/adr/0001-first.md", adr_text("Accepted — 2026-01-01"))
        write_doc(
            repo,
            "knowledge/adr/README.md",
            readme_text([("0001", "最初の決定", "Accepted", "2026-01-01")]),
        )
        commit_baseline(repo)

        overwrite(repo, "knowledge/a.md", read_doc(repo, "knowledge/a.md") + "\n" + ENTRY_B)
        write_doc(repo, "knowledge/adr/0002-second.md", adr_text("Accepted — 2026-02-01"))
        overwrite(
            repo,
            "knowledge/adr/0001-first.md",
            adr_text("Superseded by 0002-second — 2026-02-01"),
        )
        overwrite(
            repo,
            "knowledge/adr/README.md",
            readme_text(
                [
                    ("0001", "最初の決定", "Superseded by 0002-second", "2026-01-01"),
                    ("0002", "次の決定", "Accepted", "2026-02-01"),
                ]
            ),
        )
        commit_all(repo, "両方式とも正規の更新")

        code, out = check(repo)
        assert code == 0, out
        assert "インライン 1 本" in out and "ADR 1 本" in out, out
    finally:
        shutil.rmtree(repo)


# --- base/head の解決 ---------------------------------------------------------


def test_corrupt_blob_is_not_mistaken_for_missing_path_exits_2():
    """F13: `git show` が壊れたオブジェクトで失敗しても、パス自体は
    `git cat-file -e` で存在が確認できる。この場合は「存在しない」と誤判定せず
    exit 2（判定不能）にする。"""
    repo = new_repo()
    try:
        write_doc(repo, "knowledge/adr/0001-first.md", adr_text("Accepted — 2026-01-01"))
        commit_baseline(repo)
        base_sha = run_git(repo, "rev-parse", "HEAD")

        blob_sha = run_git(repo, "rev-parse", f"{base_sha}:knowledge/adr/0001-first.md")
        obj_path = repo / ".git" / "objects" / blob_sha[:2] / blob_sha[2:]
        assert obj_path.is_file(), f"loose object が見つからない: {obj_path}"
        os.chmod(obj_path, 0o644)
        obj_path.write_bytes(b"garbage, not a valid git object")

        write_doc(repo, "knowledge/adr/0002-second.md", adr_text("Accepted — 2026-02-01"))
        commit_all(repo, "ADR を追加")

        code, out = check(repo)
        assert code == 2, f"壊れたオブジェクトを「存在しない」と誤判定している:\n{out}"
    finally:
        shutil.rmtree(repo)


def _delete_blob_object(repo, blob_sha):
    obj_path = repo / ".git" / "objects" / blob_sha[:2] / blob_sha[2:]
    assert obj_path.is_file(), f"loose object が見つからない: {obj_path}"
    obj_path.unlink()


def test_deleted_blob_object_in_adr_method_exits_2():
    """G12: base の ADR の blob オブジェクトが（ツリーには残るが）物理的に無くなって
    いる場合、`git ls-tree` でパス自体の存在は確認できるので「存在しない」と誤判定
    せず、内容読み取りの失敗を判定不能として exit 2 にする
    （修正前は独立ファイル方式が AttributeError で落ちていた）。"""
    repo = new_repo()
    try:
        write_doc(repo, "knowledge/adr/0001-first.md", adr_text("Accepted — 2026-01-01"))
        commit_baseline(repo)
        base_sha = run_git(repo, "rev-parse", "HEAD")

        write_doc(repo, "knowledge/adr/0002-second.md", adr_text("Accepted — 2026-02-01"))
        commit_all(repo, "ADR を追加する")

        blob_sha = run_git(repo, "rev-parse", f"{base_sha}:knowledge/adr/0001-first.md")
        _delete_blob_object(repo, blob_sha)

        code, out = check(repo)
        assert code == 2, f"blob オブジェクトの欠落を「存在しない」と誤判定している:\n{out}"
    finally:
        shutil.rmtree(repo)


def test_deleted_blob_object_in_inline_method_exits_2():
    """G12: インライン方式でも、base の blob オブジェクトの物理的な欠落は exit 2 に
    する（修正前は「文書が存在しない」と誤判定して黒く通過していた）。"""
    repo = new_repo()
    try:
        write_doc(repo, "knowledge/a.md", "本文。\n" + LOG_HEADER + ENTRY_A)
        commit_baseline(repo)
        base_sha = run_git(repo, "rev-parse", "HEAD")

        write_doc(repo, "knowledge/other.md", "別の本文。\n")
        commit_all(repo, "別の文書を追加する")

        blob_sha = run_git(repo, "rev-parse", f"{base_sha}:knowledge/a.md")
        _delete_blob_object(repo, blob_sha)

        code, out = check(repo)
        assert code == 2, f"blob オブジェクトの欠落を「存在しない」と誤判定している:\n{out}"
    finally:
        shutil.rmtree(repo)


def test_invalid_base_ref_exits_2():
    repo = new_repo()
    try:
        write_doc(repo, "knowledge/a.md", "本文。\n")
        commit_baseline(repo)
        code, out = check(repo, "--base", "does-not-exist")
        assert code == 2, out
    finally:
        shutil.rmtree(repo)


def test_shallow_clone_exits_2():
    """共通祖先が両ブランチの tip から 1 コミット以上離れていれば、depth=1 の shallow
    clone はその祖先を取得しない（tip 自体は各ブランチの最新 1 件しか取らないため）。
    """
    repo = new_repo()
    shallow = None
    try:
        write_doc(repo, "knowledge/a.md", "本文。\n")
        commit_all(repo, "c1")
        write_doc(repo, "knowledge/a.md", "本文2。\n")
        commit_all(repo, "c2-共通祖先")
        run_git(repo, "switch", "-q", "-c", "work")
        write_doc(repo, "knowledge/a.md", "本文3（work）。\n")
        commit_all(repo, "c3-work")
        run_git(repo, "switch", "-q", "main")
        write_doc(repo, "knowledge/other.md", "本文4（main）。\n")
        commit_all(repo, "c4-main")

        # ローカルパスへの clone は --depth を無視する（"use file:// instead" 警告）ため、
        # file:// URL を明示して実際に shallow にする。
        shallow = Path(tempfile.mkdtemp(prefix="decision-log-shallow-"))
        subprocess.run(
            ["git", "clone", "-q", "--depth", "1", "--no-single-branch", f"file://{repo}", str(shallow)],
            check=True,
            capture_output=True,
        )
        code, out = check(shallow, "--base", "origin/main", "--head", "origin/work")
        assert code == 2, out
    finally:
        shutil.rmtree(repo)
        if shallow is not None and shallow.exists():
            shutil.rmtree(shallow)


def test_uncommitted_change_detected_without_head():
    repo = new_repo()
    try:
        write_doc(repo, "knowledge/a.md", "本文。\n" + LOG_HEADER + ENTRY_A)
        commit_baseline(repo)
        overwrite(repo, "knowledge/a.md", read_doc(repo, "knowledge/a.md").replace("A を採用する", "A' を採用する"))
        code, out = check(repo)
        assert code == 1, f"未コミットの変更が検出されない:\n{out}"
        code2, out2 = check(repo, "--head", "HEAD")
        assert code2 == 0, f"--head HEAD は未コミットの変更を見るべきではない:\n{out2}"
    finally:
        shutil.rmtree(repo)


def test_head_argument_matches_working_tree_after_commit():
    repo = new_repo()
    try:
        write_doc(repo, "knowledge/a.md", "本文。\n" + LOG_HEADER + ENTRY_A)
        commit_baseline(repo)
        overwrite(repo, "knowledge/a.md", read_doc(repo, "knowledge/a.md").replace("A を採用する", "A' を採用する"))
        head_sha = commit_all(repo, "既存の決定を書き換える")
        code, out = check(repo)
        assert code == 1, out
        code2, out2 = check(repo, "--head", head_sha)
        assert code2 == 1, out2
    finally:
        shutil.rmtree(repo)


def test_warn_only_downgrades_error_exit_code():
    repo = new_repo()
    try:
        write_doc(repo, "knowledge/a.md", "本文。\n" + LOG_HEADER + ENTRY_A)
        commit_baseline(repo)
        overwrite(repo, "knowledge/a.md", read_doc(repo, "knowledge/a.md").replace("A を採用する", "A' を採用する"))
        commit_all(repo, "既存の決定を書き換える")
        code, out = check(repo)
        assert code == 1, out
        code2, out2 = check(repo, "--warn-only")
        assert code2 == 0, out2
        assert "既存エントリが変更されている" in out2, out2
    finally:
        shutil.rmtree(repo)


def main() -> int:
    if not TARGET.is_file():
        print(f"テスト対象が見つからない: {TARGET}", file=sys.stderr)
        return 1
    tests = [(n, f) for n, f in sorted(globals().items()) if n.startswith("test_") and callable(f)]
    failures = 0
    print("check-decision-log.py 回帰テスト")
    for name, fn in tests:
        try:
            fn()
            print(f"  ✓ {name}")
        except AssertionError as exc:
            print(f"  ✗ {name}: {exc}", file=sys.stderr)
            failures += 1
        except Exception as exc:  # noqa: BLE001 - テスト実行時の想定外は全部落とす
            print(f"  ✗ {name}: 想定外の例外 {exc!r}", file=sys.stderr)
            failures += 1
    print("")
    if failures:
        print(f"✗ {failures} / {len(tests)} 件が失敗した (PASS={len(tests) - failures} FAIL={failures})", file=sys.stderr)
        return 1
    print(f"✓ 全 {len(tests)} ケース通過 (PASS={len(tests)} FAIL=0)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
