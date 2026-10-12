#!/usr/bin/env python3
"""
plan-gate-check.py

Claude Code PermissionRequest (matcher: ExitPlanMode) hook。

ExitPlanMode で計画の承認を求める前に、計画本文に次の 2 つの見出しが揃っているかを検査する
（ADR 0020）。揃っていなければ承認画面に進ませず、足りない見出しと書き方を返す。
- 「ゲートの確認結果」: implement-flow の Step 2〜4 の結果。対象外の計画は「対象外: <理由>」と書く
- 「ルール準拠表」: ルール｜状態｜対応 の表。節の中に `|` を含む行が 1 行以上必要

判定:
- 見出しは `#`〜`####`。見出しの文字列が上の語を含めばよい（前後の語・括弧書きは許容）
- コードフェンス（``` / ~~~）の中の行は見出しとも表の行とも数えない
- ルール準拠表の節は、同じか上位のレベルの次の見出しまで
- 計画本文は `tool_input.plan`。無ければ `tool_input.planFilePath` のファイルを読む。
  どちらも無ければ「計画本文が渡っていない」として止める。Claude Code は計画ファイルの中身を
  `tool_input.plan` に入れて渡すが、計画ファイルがまだ無い（Write と並列に呼んだ）と `{}` になる

止め方: stdout に `hookSpecificOutput.decision.behavior = "deny"` の JSON を出して exit 0
（PermissionRequest の decision control）。通すときは何も出さずに exit 0 で、承認画面へ進む。

既知の限界: 見出しがあるかを見るだけで、中身が検討されたかは検査できない。Plan モードを
経ない承認（resolve-issue の AskUserQuestion など）は対象外。

例外は飲み込み、hook 失敗で Claude Code を止めない（何も出さずに exit 0）。
"""

from __future__ import annotations

import json
import re
import sys

GATE = "ゲートの確認結果"
TABLE = "ルール準拠表"

HEADING_RE = re.compile(r"^(#{1,4})\s+(.*)$")
FENCE_RE = re.compile(r"^\s*(`{3,}|~{3,})")
# 計画ファイルの Write / Edit と ExitPlanMode を同じ応答で並列に呼ぶと、書き込む前の内容
# （初回はファイルが無いので空）で判定される（2026-10-12 の E2E で確認）
PARALLEL_NOTE = (
    "計画ファイルの Write / Edit と ExitPlanMode を同じ応答で並列に呼ぶと、書き込む前の内容で判定される。"
    "書き込みが終わってから、別の応答で ExitPlanMode を呼ぶ。"
)


def _plan_text(ti: dict) -> str:
    plan = ti.get("plan")
    if isinstance(plan, str) and plan.strip():
        return plan
    path = ti.get("planFilePath")
    if isinstance(path, str) and path:
        try:
            with open(path, encoding="utf-8") as f:
                return f.read()
        except OSError:
            return ""
    return ""


def _lines_outside_fences(text: str) -> list[str]:
    """フェンスは開きと同じ文字で、同じ長さ以上のフェンスでだけ閉じる（CommonMark と同じ）。"""
    out = []
    fence = None  # 開いているフェンスの文字列（``` や ~~~~ など）
    for line in text.splitlines():
        m = FENCE_RE.match(line)
        if m:
            f = m.group(1)
            if fence is None:
                fence = f
                continue
            if f[0] == fence[0] and len(f) >= len(fence) and not line.strip()[len(f):].strip():
                fence = None
                continue
        if fence is None:
            out.append(line)
    return out


def _missing(text: str) -> list[str]:
    """足りない項目の説明を返す。空なら揃っている。"""
    lines = _lines_outside_fences(text)
    has_gate = False
    table_found = False
    table_has_row = False
    table_level = None  # ルール準拠表の節の中なら、その見出しのレベル
    for line in lines:
        m = HEADING_RE.match(line)
        if m:
            level, title = len(m.group(1)), m.group(2)
            if table_level is not None and level <= table_level:
                table_level = None
            if GATE in title:
                has_gate = True
            if TABLE in title:
                table_found = True
                table_level = level
            continue
        if table_level is not None and "|" in line:
            table_has_row = True

    missing = []
    if not has_gate:
        missing.append(
            f"「{GATE}」の見出し: implement-flow の Step 2（Knowledge 検索）・Step 3（棄却済み案チェック）・"
            "Step 4（ギャップ分析）の結果を書く。implement-flow の対象外の計画は「対象外: <理由>」と書く"
        )
    if not table_found:
        missing.append(f"「{TABLE}」の見出し: ルール｜状態｜対応 の表で、関係する rules・skill ごとの準拠状況を書く")
    elif not table_has_row:
        missing.append(f"「{TABLE}」の節の表: ルール｜状態｜対応 の表の行（`|` を含む行）が 1 行も無い")
    return missing


def _deny(message: str) -> None:
    print(
        json.dumps(
            {
                "hookSpecificOutput": {
                    "hookEventName": "PermissionRequest",
                    "decision": {"behavior": "deny", "message": message},
                }
            },
            ensure_ascii=False,
        )
    )


def main() -> int:
    try:
        try:
            payload = json.load(sys.stdin)
        except (json.JSONDecodeError, ValueError, OSError):
            return 0
        if not isinstance(payload, dict):
            return 0
        if payload.get("hook_event_name") != "PermissionRequest":
            return 0
        if payload.get("tool_name") != "ExitPlanMode":
            return 0
        ti = payload.get("tool_input")
        if not isinstance(ti, dict):
            ti = {}

        text = _plan_text(ti)
        if not text.strip():
            _deny(
                "BLOCKED by plan-gate-check hook.\n"
                "reason: ExitPlanMode に計画本文が渡っていない。計画ファイルに、"
                f"「{GATE}」と「{TABLE}」の見出しを含む計画を書いてから呼び直す。\n"
                + PARALLEL_NOTE
            )
            return 0

        missing = _missing(text)
        if not missing:
            return 0
        _deny(
            "BLOCKED by plan-gate-check hook.\n"
            "reason: 計画に必須の見出しが足りない。次を計画に足してから ExitPlanMode を呼び直す"
            "（見出しは # 〜 ####、見出しの文字列に語を含めばよい）。\n"
            + "\n".join(f"- {m}" for m in missing)
            + "\n"
            + PARALLEL_NOTE
        )
        return 0
    except BaseException:
        # hook 失敗で Claude Code を止めない
        return 0


if __name__ == "__main__":
    sys.exit(main())
