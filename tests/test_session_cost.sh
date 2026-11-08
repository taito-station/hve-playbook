#!/bin/bash
# scripts/session-cost.py の料金キー解決と、セッション JSONL の探索を固定する検査
#
# 実行: bash tests/test_session_cost.sh
#
# 前方一致の解決がキーの並び順に依存すると、新モデルの追加で旧料金に落ちる
# (例: claude-opus-5-5 が claude-opus-5 や claude-opus-4 に解決される)。
# 代表的なモデル ID と、期待するキー・入出力単価の対応を固定する。
# 期待値は公表価格 (https://platform.claude.com/docs/en/about-claude/pricing) から転記する。
#
# --auto-detect の探索 (Issue #110): worktree の cwd (`.claude` を含む) と、
# 並走セッションと project ディレクトリを共有するときに、自分のセッションの JSONL を選ぶこと。
# HOME を一時ディレクトリに向けて実行する (~/.claude/projects を書き換えない)。

set -u
SCRIPT="${SESSION_COST_SCRIPT:-$(cd "$(dirname "$0")/.." && pwd)/scripts/session-cost.py}"

python3 - "$SCRIPT" <<'EOF'
import importlib.util
import sys

spec = importlib.util.spec_from_file_location("session_cost", sys.argv[1])
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

# (モデル ID, 期待キー, 既知扱いか, input, output, cache_write, cache_read)
CASES = [
    ("claude-opus-5-5", "claude-opus-5-5", True, 4.0, 20.0, 5.0, 0.20),
    ("claude-opus-5", "claude-opus-5", True, 5.0, 25.0, 6.25, 0.50),
    ("claude-opus-4-8", "claude-opus-4-8", True, 5.0, 25.0, 6.25, 0.50),
    ("claude-opus-4-7", "claude-opus-4-7", True, 5.0, 25.0, 6.25, 0.50),
    ("claude-opus-4-6", "claude-opus-4-6", True, 5.0, 25.0, 6.25, 0.50),
    ("claude-opus-4-5-20251101", "claude-opus-4-5", True, 5.0, 25.0, 6.25, 0.50),
    ("claude-opus-4-1-20250805", "claude-opus-4", True, 15.0, 75.0, 18.75, 1.50),
    ("claude-sonnet-5", "claude-sonnet-5", True, 2.0, 10.0, 2.50, 0.20),
    ("claude-sonnet-4-6", "claude-sonnet-4", True, 3.0, 15.0, 3.75, 0.30),
    ("claude-haiku-4-5-20251001", "claude-haiku-4", True, 1.0, 5.0, 1.25, 0.10),
    ("claude-fable-5-1", "claude-fable-5-1", True, 10.0, 50.0, 12.50, 0.25),
    ("claude-fable-5", "claude-fable-5", True, 10.0, 50.0, 12.50, 1.0),
    ("claude-mythos-5-1", "claude-mythos-5-1", True, 10.0, 50.0, 12.50, 0.25),
    ("claude-mythos-5", "claude-mythos-5", True, 10.0, 50.0, 12.50, 1.0),
    ("<synthetic>", "claude-opus-5", False, 5.0, 25.0, 6.25, 0.50),
]

fail = 0
for model, key, known, inp, out, cw, cr in CASES:
    got_key, got_known = m.resolve_pricing_key(model)
    price = m.PRICING[got_key]
    ok = (got_key, got_known) == (key, known) and (price["input"], price["output"], price["cache_write"], price["cache_read"]) == (inp, out, cw, cr)
    print(f"[{'PASS' if ok else 'FAIL'}] {model} -> {got_key} known={got_known} {price['input']}/{price['output']}/{price['cache_write']}/{price['cache_read']}")
    fail |= not ok

# 並び順に依存しないこと: キー順を逆にしても同じ解決になる
m.PRICING = dict(reversed(list(m.PRICING.items())))
for model, key, known, *_ in CASES:
    if m.resolve_pricing_key(model) != (key, known):
        print(f"[FAIL] キー順を逆にすると {model} の解決が変わる")
        fail = 1
if not fail:
    print("[PASS] キー順に依存しない")

sys.exit(1 if fail else 0)
EOF
rc_pricing=$?

python3 - "$SCRIPT" <<'EOF'
import os
import subprocess
import sys
import tempfile
from pathlib import Path

script = sys.argv[1]
fail = 0


def check(name, ok, detail=""):
    global fail
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f" ({detail})" if detail and not ok else ""))
    fail |= not ok


def enc(path):
    # Claude Code の project ディレクトリ名: 英数字以外を - に置き換える
    return "".join(c if c.isascii() and c.isalnum() else "-" for c in path)


def write_jsonl(path, lines, mtime):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join("{}\n" for _ in range(lines)), encoding="utf-8")
    os.utime(path, (mtime, mtime))


def run(home, cwd, session_id=None):
    env = {k: v for k, v in os.environ.items() if k != "CLAUDE_CODE_SESSION_ID"}
    env["HOME"] = str(home)
    if session_id is not None:
        env["CLAUDE_CODE_SESSION_ID"] = session_id
    marker = Path(home) / "marker"
    if marker.exists():
        marker.unlink()
    r = subprocess.run(
        [sys.executable, script, "--auto-detect", "--snapshot", str(marker)],
        cwd=cwd, env=env, capture_output=True, text=True,
    )
    lines = int(marker.read_text()) if marker.exists() else None
    return r, lines


with tempfile.TemporaryDirectory() as tmp:
    tmp = Path(os.path.realpath(tmp))
    home = tmp / "home"
    projects = home / ".claude" / "projects"
    primary = tmp / "repo"
    worktree = primary / ".claude" / "worktrees" / "issue-1"
    worktree.mkdir(parents=True)

    # 1. worktree の cwd: `.claude` も - にしたディレクトリから見つける
    write_jsonl(projects / enc(str(worktree)) / "wt.jsonl", 3, 1000)
    r, lines = run(home, worktree)
    check("worktree の cwd でセッション JSONL を見つける", lines == 3, r.stderr.strip())

    # 2. primary の cwd: 従来どおり、cwd のディレクトリの最新の JSONL
    write_jsonl(projects / enc(str(primary)) / "old.jsonl", 5, 1000)
    write_jsonl(projects / enc(str(primary)) / "mine.jsonl", 7, 2000)
    r, lines = run(home, primary)
    check("primary の cwd で最新の JSONL を選ぶ (回帰)", lines == 7, r.stderr.strip())

    # 3. session ID があれば、より新しい並走セッションの JSONL より自分のものを選ぶ
    write_jsonl(projects / enc(str(primary)) / "other.jsonl", 9, 3000)
    r, lines = run(home, primary, "mine")
    check("session ID の JSONL を、より新しい並走セッションの JSONL より優先する", lines == 7, r.stderr.strip())

    # 4. session ID の JSONL は cwd と別の project ディレクトリにあっても見つける
    r, lines = run(home, worktree, "mine")
    check("session ID の JSONL を cwd と別の project ディレクトリから見つける", lines == 7, r.stderr.strip())

    # 5. session ID の JSONL が無ければ cwd のディレクトリに戻る
    r, lines = run(home, worktree, "absent-id")
    check("session ID の JSONL が無ければ cwd のディレクトリの最新を使う", lines == 3, r.stderr.strip())

    # 6. 見つからないときは、探した session ID とディレクトリを警告に出して exit 0
    lost = tmp / "lost"
    lost.mkdir()
    r, lines = run(home, lost, "absent-id")
    ok = (r.returncode == 0 and lines is None and "absent-id" in r.stderr
          and str(projects / enc(str(lost))) in r.stderr)
    check("見つからないときは探した場所を警告に出す", ok, f"rc={r.returncode} stderr={r.stderr.strip()}")

sys.exit(1 if fail else 0)
EOF
rc_detect=$?

echo "==================================="
if [ "$rc_pricing" -eq 0 ] && [ "$rc_detect" -eq 0 ]; then
    echo "ALL TESTS PASSED"
    exit 0
fi
echo "SOME TESTS FAILED"
exit 1
