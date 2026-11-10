#!/usr/bin/env python3
"""Claude Code セッション JSONL からトークン使用量と費用を集計する。"""

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# 出典: https://platform.claude.com/docs/en/about-claude/pricing（2026-09-26 確認）。
# cache_write は 5 分キャッシュ書込。キーはモデル ID の前方一致で、最も長く一致したキーを使う。
# Opus 5.5 / Fable 5.1 / Mythos 5.1 の cache_read は公表どおり 0.1x ではない（0.05x / 0.025x）。
_OPUS_45_PLUS = {"input": 5.0, "output": 25.0, "cache_write": 6.25, "cache_read": 0.50}
PRICING = {
    "claude-fable-5-1": {"input": 10.0, "output": 50.0, "cache_write": 12.50, "cache_read": 0.25},
    "claude-mythos-5-1": {"input": 10.0, "output": 50.0, "cache_write": 12.50, "cache_read": 0.25},
    "claude-fable-5": {"input": 10.0, "output": 50.0, "cache_write": 12.50, "cache_read": 1.0},
    "claude-mythos-5": {"input": 10.0, "output": 50.0, "cache_write": 12.50, "cache_read": 1.0},
    "claude-opus-5-5": {"input": 4.0, "output": 20.0, "cache_write": 5.0, "cache_read": 0.20},
    "claude-opus-5": _OPUS_45_PLUS,
    "claude-opus-4-8": _OPUS_45_PLUS,
    "claude-opus-4-7": _OPUS_45_PLUS,
    "claude-opus-4-6": _OPUS_45_PLUS,
    "claude-opus-4-5": _OPUS_45_PLUS,
    "claude-opus-4": {"input": 15.0, "output": 75.0, "cache_write": 18.75, "cache_read": 1.50},
    "claude-sonnet-5": {"input": 2.0, "output": 10.0, "cache_write": 2.50, "cache_read": 0.20},
    "claude-sonnet-4": {"input": 3.0, "output": 15.0, "cache_write": 3.75, "cache_read": 0.30},
    "claude-haiku-4": {"input": 1.0, "output": 5.0, "cache_write": 1.25, "cache_read": 0.10},
}
DEFAULT_PRICING_KEY = "claude-opus-5"

PROJECTS_DIR = Path.home() / ".claude" / "projects"
# glob に渡すので、.. や * を含む値は使わない
SESSION_ID_PATTERN = re.compile(r"[A-Za-z0-9-]+")


def encode_project_dir(cwd: str) -> str:
    # Claude Code は英数字以外をすべて - にする（worktree の `.claude` は `-claude` になる）
    return re.sub(r"[^A-Za-z0-9]", "-", cwd)


def latest_file(paths: List[Path]) -> Optional[Path]:
    files = [p for p in paths if p.is_file()]
    return max(files, key=lambda p: p.stat().st_mtime) if files else None


def find_session_file_by_id(session_id: str) -> Optional[Path]:
    # EnterWorktree で入ったセッションの JSONL は cwd と別の project ディレクトリにもありうるので、全体から探す
    if not SESSION_ID_PATTERN.fullmatch(session_id):
        return None
    return latest_file(list(PROJECTS_DIR.glob(f"*/{session_id}.jsonl")))


def find_latest_session_file(cwd: str) -> Optional[Path]:
    project_dir = PROJECTS_DIR / encode_project_dir(cwd)
    if not project_dir.is_dir():
        return None
    return latest_file(list(project_dir.glob("*.jsonl")))


def resolve_pricing_key(model: str) -> Tuple[str, bool]:
    matches = [key for key in PRICING if model.startswith(key)]
    if matches:
        return max(matches, key=len), True
    return DEFAULT_PRICING_KEY, False


def aggregate(path: Path, start_line: int = 0) -> Tuple[Dict[str, Dict[str, int]], int]:
    stats: Dict[str, Dict[str, int]] = {}
    total_lines = 0
    with path.open("r", encoding="utf-8") as f:
        for i, raw_line in enumerate(f):
            total_lines = i + 1
            if i < start_line:
                continue
            line = raw_line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            if obj.get("type") != "assistant":
                continue
            message = obj.get("message") or {}
            usage = message.get("usage")
            model = message.get("model")
            if not usage or not model:
                continue
            entry = stats.setdefault(model, {
                "requests": 0,
                "input": 0,
                "output": 0,
                "cache_write": 0,
                "cache_read": 0,
            })
            entry["requests"] += 1
            entry["input"] += usage.get("input_tokens", 0)
            entry["output"] += usage.get("output_tokens", 0)
            entry["cache_write"] += usage.get("cache_creation_input_tokens", 0)
            entry["cache_read"] += usage.get("cache_read_input_tokens", 0)
    return stats, total_lines


def format_report(stats: Dict[str, Dict[str, int]]) -> str:
    lines = ["=== セッション費用レポート ==="]
    grand_total = 0.0
    for model in sorted(stats.keys()):
        entry = stats[model]
        pricing_key, known = resolve_pricing_key(model)
        if not known:
            print(f"警告: 未知のモデル '{model}' は {DEFAULT_PRICING_KEY} の料金で計算します", file=sys.stderr)
        price = PRICING[pricing_key]

        input_cost = round(entry["input"] / 1_000_000 * price["input"], 2)
        output_cost = round(entry["output"] / 1_000_000 * price["output"], 2)
        cache_write_cost = round(entry["cache_write"] / 1_000_000 * price["cache_write"], 2)
        cache_read_cost = round(entry["cache_read"] / 1_000_000 * price["cache_read"], 2)
        subtotal = input_cost + output_cost + cache_write_cost + cache_read_cost
        grand_total += subtotal

        lines.append("")
        lines.append(f"モデル: {model} ({entry['requests']} リクエスト)")
        lines.append(f"  入力:        {entry['input']:>10,} tok  (${input_cost:.2f})")
        lines.append(f"  出力:        {entry['output']:>10,} tok  (${output_cost:.2f})")
        lines.append(f"  キャッシュ作成:  {entry['cache_write']:>10,} tok  (${cache_write_cost:.2f})")
        lines.append(f"  キャッシュ読取:  {entry['cache_read']:>10,} tok  (${cache_read_cost:.2f})")
        lines.append(f"  小計: ${subtotal:.2f}")

    lines.append("")
    lines.append(f"合計: ${grand_total:.2f}")
    return "\n".join(lines)


def resolve_target(args: argparse.Namespace) -> Tuple[Optional[Path], List[str]]:
    """集計対象と、見つからなかったときに警告へ出す探した場所を返す。"""
    if args.file:
        return Path(args.file), [args.file]
    if not args.auto_detect:
        return None, []
    searched = []
    # 並走セッションと project ディレクトリを共有していても、自分のセッションの JSONL を選ぶ
    session_id = os.environ.get("CLAUDE_CODE_SESSION_ID", "")
    if session_id:
        target = find_session_file_by_id(session_id)
        if target:
            return target, []
        if SESSION_ID_PATTERN.fullmatch(session_id):
            searched.append(str(PROJECTS_DIR / "*" / f"{session_id}.jsonl"))
        else:
            # 値はそのまま出さない（改行や制御文字が端末に出るため）
            searched.append("（CLAUDE_CODE_SESSION_ID は形式が不正なため使わなかった）")
    cwd = os.getcwd()
    searched.append(str(PROJECTS_DIR / encode_project_dir(cwd) / "*.jsonl"))
    return find_latest_session_file(cwd), searched


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Claude Code セッション JSONL からトークン使用量と費用を集計する",
    )
    parser.add_argument(
        "--auto-detect", action="store_true",
        help="現在の作業ディレクトリから対応する最新セッション JSONL を自動検出する",
    )
    parser.add_argument("--file", metavar="PATH", help="集計対象の JSONL ファイルパスを直接指定する")
    parser.add_argument(
        "--snapshot", metavar="MARKER_PATH",
        help="現在の JSONL の行数をマーカーファイルに記録して終了する",
    )
    parser.add_argument(
        "--since", metavar="MARKER_PATH",
        help="マーカーファイルの行数以降のデータのみ集計する（差分計算）",
    )

    if len(sys.argv) == 1:
        parser.print_help()
        return 0

    args = parser.parse_args()

    target, searched = resolve_target(args)
    if target is None or not target.is_file():
        print("警告: セッション JSONL ファイルが見つかりません", file=sys.stderr)
        for path in searched:
            print(f"  探した場所: {path}", file=sys.stderr)
        return 0

    if args.snapshot:
        with target.open("r", encoding="utf-8") as f:
            line_count = sum(1 for _ in f)
        marker_path = Path(args.snapshot)
        marker_path.parent.mkdir(parents=True, exist_ok=True)
        marker_path.write_text(str(line_count), encoding="utf-8")
        print(f"スナップショット記録: {line_count} 行 -> {marker_path}")
        return 0

    start_line = 0
    if args.since:
        marker_path = Path(args.since)
        if marker_path.is_file():
            try:
                start_line = int(marker_path.read_text(encoding="utf-8").strip())
            except ValueError:
                start_line = 0
        else:
            print(
                f"警告: マーカーファイルが見つかりません ({marker_path})。セッション全体を集計します",
                file=sys.stderr,
            )

    stats, _ = aggregate(target, start_line)
    print(format_report(stats))
    return 0


if __name__ == "__main__":
    sys.exit(main())
