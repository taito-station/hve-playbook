#!/usr/bin/env python3
"""
permission-request-logger.py

Claude Code PermissionRequest hook (Unix / WSL 向け; fcntl を使用するため
Windows ネイティブ Python では動作しない)。

公式 docs (https://code.claude.com/docs/en/hooks.md) で PermissionRequest が
独立 event として列挙されている。Notification + notification_type ==
"permission_prompt" 経由の旧設計は実機で 0 件しか捕捉できなかったため、
本実装は PermissionRequest event を直接受ける設計に切り替えた。

payload schema は公式未文書化のため observe-first で運用した (Phase A)。
2026-05-29〜2026-10-12 の 5199 件の観測で、tool_name / tool_input が常に
トップレベルにあることを確かめたので、Phase B として debug log を既定 OFF
にした (ADR 0022)。
  - 環境変数 PERM_REQUEST_DEBUG が "1" のときだけ、全 payload を
    ~/.claude/logs/debug-perm-request.log に dump する ("true" 等は OFF)
  - 環境変数 PERM_REQUEST_LOG が "0" のとき、本体 JSONL を書かない

【秘密値の取り扱い】
許可ダイアログの対象になるコマンド (Bash の curl/wget で Authorization header
を使う、WebFetch の URL に token を含む等) は秘密値を含むことが多い。よって:
  - 書く前に、既知の秘密値のパターン (SECRET_PATTERNS) の値を <redacted> に
    伏せる。本体 JSONL は tool_input・title・message を、debug log は
    payload 全体を伏せる。パターンで捕まえきれない秘密値は残りうるので、
    残したくなければ PERM_REQUEST_LOG=0 で止める
  - 伏せる処理で例外が出たら書かない (fail-closed)
  - LOG_PATH / DEBUG_PATH ともに 0o600 で作成し、`os.open` + umask 077 で
    生成時から狭い権限を保つ (touch → chmod の race を避ける)
  - 親 dir (~/.claude/logs/) は他 hook と共有しているため無条件 chmod は
    しない (副作用回避)。dir 内の他ファイルの mode は各 hook 責任とする

JSONL 出力 schema は旧 Notification 経由実装と完全に後方互換を維持。
statusline (~/.claude/statusline.sh) と /review-permissions skill は
~/.claude/logs/permission-requests.jsonl の行数と field 名で動いており、
本 hook の差し替えだけで完結した (statusline は無変更。JSONL の field 名は変えない)。

LOG_PATH / DEBUG_PATH / LOG_ENABLED / DEBUG_ENABLED は module import 時に 1 回だけ評価
される。テストはサブプロセス起動 (毎回 import) を前提に env 経由で
override する設計。pytest 等で同一プロセス内 override したい場合は
将来 helper 関数化が必要。

env 評価の挙動:
  - LOG_PATH / DEBUG_PATH: `os.environ.get(...) or default` で **未設定 /
    空文字** どちらも default に fallback。設定ミスは安全側に倒す意図。
  - LOG_ENABLED: `"0"` のときだけ OFF。未設定・空文字は ON (従来どおり書く)。
  - DEBUG_ENABLED: `"1"` のときだけ ON。未設定・空文字・"true" 等は OFF。
"""

from __future__ import annotations

import fcntl
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

LOG_PATH = Path(
    os.environ.get("PERM_REQUEST_LOG_PATH")
    or (Path.home() / ".claude" / "logs" / "permission-requests.jsonl")
)
DEBUG_PATH = Path(
    os.environ.get("PERM_REQUEST_DEBUG_PATH")
    or (Path.home() / ".claude" / "logs" / "debug-perm-request.log")
)
LOG_ENABLED = os.environ.get("PERM_REQUEST_LOG") != "0"
DEBUG_ENABLED = os.environ.get("PERM_REQUEST_DEBUG") == "1"
# `<project>-parallel-N` 形式の cwd から parallel 番号を抽出する。
# プロジェクトで命名規約が違う場合はここを書き換える。
PARALLEL_RE = re.compile(r"-parallel-(\d+)")

# 本体 JSONL から除外する内部 tool 名。
# AskUserQuestion / ExitPlanMode は「awaiting 化シグナル」として
# 意図的に PermissionRequest を fire させる用途であり、許可要求としてレビュー
# 対象にする意義は無い (= /review-permissions skill のノイズになる)。
# 本体 JSONL のみ filter し、debug log や他の PermissionRequest hook (awaiting
# 表示など) への伝達は影響を受けない (再観測時の schema 観測 + awaiting 化の維持)。
INTERNAL_TOOLS_SKIP_LOGGING = frozenset({"AskUserQuestion", "ExitPlanMode"})

# 既知の秘密値のパターン。値だけを REDACTED に置き換え、前後は残す
# (review-permissions のクラスタリングと危険パターンの判定に後続の `| sh` 等が要る)。
# 値は空白・引用符・シェルの区切り (| ; > ) など) の手前までとし、`<` も含めない
# (置換済みの REDACTED に再び当たらないように)。
# 伏せ字に `*` を使わないのは、許可ルールの glob 案に混ざるため。
REDACTED = "<redacted>"
# 伏せる値の 1 文字。`$` も含めないので、`$VAR` / `$(cmd)` で始まる値は伏せず、
# 値の途中の `$(cmd)` などはその手前で止まる
_VALUE = r"[^\s\"'<|;>()`&$]"
SECRET_PATTERNS = (
    # Authorization / Proxy-Authorization ヘッダ。スキーム語 (Bearer 等) は残す。
    # 値は 8 文字以上に限る (`grep "Authorization: Bearer"` のような検索語に当てない)。
    # 区切りは改行を含めない (Markdown の「Authorization:」の次の行の語に当てない)
    re.compile(r"(?i)(\b(?:proxy-)?authorization[ \t]*:[ \t]*(?:(?:bearer|basic|token|digest)[ \t]+)?)" + _VALUE + "{8,}"),
    # ヘッダ名の無い Bearer トークン ({"Authorization": "Bearer x"} の値など)。
    # 値は 8 文字以上で、数字を含むものに限る (英文の "Bearer authentication." 等に当てない)
    re.compile(r"(?i)(\bbearer[ \t]+)(?=" + _VALUE + r"*[0-9])" + _VALUE + "{8,}"),
    # URL クエリ・フラグメント。`?` / `&` / `#` の直後のキーに限る (`gh api -f key=v` 等に当てない)
    re.compile(r"(?i)([?&#](?:access_token|client_secret|api_key|apikey|password|secret|(?:\w*_)?token)=)" + _VALUE + "+"),
    # 環境変数代入。大文字の名前に限る (`max_tokens=100` 等に当てない)。名前の長さに上限を付けて
    # 計算量を抑える。二重引用符・引用符なしの `$VAR` / `$(cmd)` の参照と、二重引用符の中の
    # コマンド置換は伏せない (秘密値そのものではなく、伏せると危険の手掛かりも消える)。
    # 単一引用符の中の `$` は展開されないので伏せる。引用符の値は改行ともう一方の種類の引用符を含まず、
    # 閉じ引用符の直後が空白・行末・シェルの区切りのときだけ伏せる (別の引用符の中の `NAME='` から
    # 伏せ始めて、実行される `| sh` などを飲み込まないように。そこから抜けるにはもう一方の引用符が要る)。
    # 引用符なしの値は `$` の手前で止まる
    re.compile(
        r"(?<![A-Za-z0-9_])([A-Z0-9_]{0,64}(?:TOKEN|SECRET|PASSWORD|API_KEY)[A-Z0-9_]{0,64}=)"
        r"(?!\"\$|\"(?:[^\"\\\n]|\\.)*(?:\$\(|`))"
        r"(?:\"(?:[^\"\\\n']|\\.)*\"(?=[\s;&|<>)]|$)|'[^'\n\"]*'(?=[\s;&|<>)]|$)|[^\s\"';&|<>()`$]+)"
    ),
    # URL の userinfo の password (https://user:<token>@host)。値の文字は _VALUE と同じく
    # シェルの区切りと `$` を含めない (`http://h:1|sh;#@` の `| sh` を飲み込まないように)
    re.compile(r"(://[^/\s:@\"'<]+:)[^@/\s\"'<|;>()`&$]+(?=@)"),
)


def identify_parallel(cwd: str) -> int:
    """cwd から `<project>-parallel-N` の N を抽出。該当なしは 0。"""
    m = PARALLEL_RE.search(cwd or "")
    return int(m.group(1)) if m else 0


def mask_secrets(value: object) -> object:
    """value の中の文字列から SECRET_PATTERNS の値を REDACTED に置き換える。

    dict / list は再帰し (dict のキーは変えない)、文字列以外の値はそのまま返す。
    """
    if isinstance(value, str):
        for pattern in SECRET_PATTERNS:
            value = pattern.sub(lambda m: m.group(1) + REDACTED, value)
        return value
    if isinstance(value, dict):
        return {k: mask_secrets(v) for k, v in value.items()}
    if isinstance(value, list):
        return [mask_secrets(v) for v in value]
    return value


def _open_secure_append(path: Path):
    """秘密値を含む log ファイルを 0o600 で safely open して append 用 fd を返す。

    失敗時 (symlink 検出 / chmod 失敗 / open 失敗等) は None を返し、呼び
    出し元が write skip する fail-closed 設計。

    is_symlink チェックと `os.open` の間の TOCTOU race を塞ぐため、open
    自体に `O_NOFOLLOW` を付与: race で symlink が挿入されても `ELOOP`
    で fail-closed になる。新規作成 / 既存追記 を同一の `os.open` 呼び
    出しで処理し、chmod は `os.fchmod(fd, 0o600)` で fd 経由 (= symlink
    を辿らず inode 自体に作用) で確実に 0o600 に揃える。

    親 dir 自体が symlink だった場合も拒否する (本 hook の信頼境界は
    `~/.claude/logs/` の下流のみであり、parent dir が attacker controlled
    symlink になっている脅威モデルは Claude Code 全体の信頼境界の問題で
    本 hook 単独では防げないが、念のため浅い検出は入れる)。

    本 hook は単発起動 (stdin 受け → exit) のサブプロセスのため、
    `os.umask` 設定はプロセス全体に影響するが他処理に副作用しない。
    finally で復元するため例外時も umask は元に戻る。
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.parent.is_symlink():
        print(
            f"[permission-request-logger] refusing: parent is symlink: {path.parent}",
            file=sys.stderr,
        )
        return None
    if path.is_symlink():
        print(
            f"[permission-request-logger] refusing to write to symlink: {path}",
            file=sys.stderr,
        )
        return None
    old_umask = os.umask(0o077)
    try:
        try:
            fd = os.open(
                path,
                os.O_WRONLY | os.O_CREAT | os.O_APPEND | os.O_NOFOLLOW,
                0o600,
            )
        except OSError as e:
            print(
                f"[permission-request-logger] secure open failed on {path}: {e}",
                file=sys.stderr,
            )
            return None
    finally:
        os.umask(old_umask)
    try:
        # fd 経由の fchmod は symlink を辿らず inode 自体に作用するため、
        # check-then-open の race を経た後でも安全に 0o600 を強制できる。
        os.fchmod(fd, 0o600)
    except OSError as e:
        print(
            f"[permission-request-logger] fchmod 0o600 failed on {path}: {e} (skipping write)",
            file=sys.stderr,
        )
        os.close(fd)
        return None
    return fd


def _safe_json_default(obj: object) -> str:
    """JSON 非 serializable な値を型情報のみで置き換える。

    `default=str` で `__str__` 経由にすると bytes や object の repr で
    秘密値が漏れる可能性があるため、型名のみ残す (schema の観測には型が分かれば
    十分で、生値は不要)。
    """
    return f"<non-serializable: {type(obj).__name__}>"


def _debug_dump(payload: dict) -> None:
    """全 payload を、秘密値を伏せて debug log に append する。

    PERM_REQUEST_DEBUG=1 のときだけ書く (payload schema を再観測するとき用)。
    伏せる処理を含め、失敗時は書かずに stderr に痕跡を残す。
    """
    if not DEBUG_ENABLED:
        return
    payload_dict = payload if isinstance(payload, dict) else {}
    try:
        rec = {
            "ts": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
            "hook_event_name": payload_dict.get("hook_event_name", ""),
            "session_id": payload_dict.get("session_id", ""),
            "cwd": payload_dict.get("cwd", ""),
            # all_keys は raw を見れば取れるが、grep / jq での top-level 横断
            # 解析 (例: schema 観測のため `jq '.all_keys | unique'`) を簡便に
            # するため top-level に冗長コピーする。raw が `_safe_json_default`
            # で型名にしか変換できなかった場合の最終 fallback としても有効。
            "all_keys": sorted(payload_dict.keys()),
            "raw": mask_secrets(payload),
        }
        fd = _open_secure_append(DEBUG_PATH)
        if fd is None:
            return
        with os.fdopen(fd, "a", encoding="utf-8") as f:
            fcntl.flock(f, fcntl.LOCK_EX)
            try:
                # default は型名のみ残す安全 fallback (bytes 等の repr 漏洩防止)
                f.write(json.dumps(rec, ensure_ascii=False, default=_safe_json_default) + "\n")
                f.flush()
            finally:
                fcntl.flock(f, fcntl.LOCK_UN)
    except Exception as e:
        sid = payload_dict.get("session_id", "")
        cwd = payload_dict.get("cwd", "")
        print(
            f"[permission-request-logger debug] session={sid} cwd={cwd} type={type(e).__name__} err={e}",
            file=sys.stderr,
        )


def _as_dict(value: object) -> dict:
    """value が dict なら返す、そうでなければ空 dict。

    payload schema は公式に文書化されていないので、想定 field に str / list 等が
    入る可能性がある (e.g. `payload["tool"] == "Bash"` のような flat 形式)。
    `or {}` パターンは falsy のみガードするため、truthy な非 dict (空でない
    str/list) では `.get` が AttributeError を起こす。本関数で明示的に
    dict 型ガードする。
    """
    return value if isinstance(value, dict) else {}


def _extract_tool_info(payload: dict) -> dict:
    """PermissionRequest payload から tool 情報を抽出。

    payload schema は未確定なので、想定される field 名を順に試す:
      1. payload["tool_name"] / payload["tool_input"] / payload["tool_use_id"]
         (PreToolUse 系互換)
      2. payload["tool"]["name"] / payload["tool"]["input"] / payload["tool"]["id"]
         (nested)
      3. payload["request"]["tool_name"] etc. (request サブオブジェクト経由)

    どれも空なら {} を返す (本体 append は schema 不一致でも空 tool_name で
    続行する)。各値は型ガードして JSONL の type pollution を防ぐ:
      - `name` / `id`: str に正規化 (None は "" に)
      - `input`: dict に正規化 (list/str/None は {} に)
    """
    tool = _as_dict(payload.get("tool"))
    request = _as_dict(payload.get("request"))
    candidates = [
        (
            payload.get("tool_name"),
            payload.get("tool_input"),
            payload.get("tool_use_id"),
        ),
        (tool.get("name"), tool.get("input"), tool.get("id")),
        (
            request.get("tool_name"),
            request.get("tool_input"),
            request.get("tool_use_id"),
        ),
    ]
    for name, inp, tid in candidates:
        if name:
            safe_name = name if isinstance(name, str) else str(name)
            safe_input = inp if isinstance(inp, dict) else {}
            safe_tid = tid if isinstance(tid, str) else ("" if tid is None else str(tid))
            return {"name": safe_name, "input": safe_input, "id": safe_tid}
    return {}


def append_log(payload: dict) -> None:
    """PermissionRequest event のときログに 1 行 append。

    防御 filter: hook_event_name が truthy かつ "PermissionRequest" 以外
    なら無視 (settings.json で誤って別 event に登録された場合の保険)。
    field 欠落 / 空文字は accept する (Claude Code バージョン差で field 自体が
    欠落した場合の false negative を防ぐ。docstring の「field 欠落でも accept」
    と一貫させる)。

    内部 tool filter: `INTERNAL_TOOLS_SKIP_LOGGING` に含まれる tool_name
    (AskUserQuestion / ExitPlanMode 等) は本体 JSONL から除外する。これらは
    awaiting 化シグナルとして意図的に PermissionRequest を fire させる用途で、
    許可要求としてレビュー対象にする意義が無いため。
    PERM_REQUEST_LOG=0 のときは何も書かない。tool_input・title・message は
    秘密値を伏せて書き、伏せる処理で例外が出たら書かない (fail-closed)。

    debug log (`_debug_dump`) や他の PermissionRequest hook への伝達は本 filter の
    対象外で従来通り動作する。`_debug_dump` は main() で本関数より前に呼ばれる
    (本関数の filter は debug 出力後にのみ作用する) ため、PERM_REQUEST_DEBUG=1
    で再観測するときは内部 tool の payload も debug log に残る。
    比較は前後空白を除いた exact match (Claude Code の tool_name 文字列が
    厳密一致前提)。schema が変わって大小文字違いで来た場合は logger に流入
    するため、debug log で発見次第 `INTERNAL_TOOLS_SKIP_LOGGING` を更新する
    運用とする。
    """
    if not LOG_ENABLED:
        return
    event = payload.get("hook_event_name")
    if event and event != "PermissionRequest":
        return
    try:
        tool_info = _extract_tool_info(payload)
        tool_name = (tool_info.get("name") or "").strip()
        if tool_name in INTERNAL_TOOLS_SKIP_LOGGING:
            return
        entry = {
            "ts": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
            "parallel": identify_parallel(payload.get("cwd", "")),
            "cwd": payload.get("cwd", ""),
            "session_id": payload.get("session_id", ""),
            "transcript_path": payload.get("transcript_path", ""),
            "title": mask_secrets(payload.get("title", "")),
            "message": mask_secrets(payload.get("message", "")),
            "tool_use_id": tool_info.get("id", ""),
            "tool_name": tool_info.get("name", ""),
            "tool_input": mask_secrets(tool_info.get("input", {})),
        }
        fd = _open_secure_append(LOG_PATH)
        if fd is None:
            return
        with os.fdopen(fd, "a", encoding="utf-8") as f:
            fcntl.flock(f, fcntl.LOCK_EX)
            try:
                # default は debug log と対称化 (型名のみ、bytes 等の repr 漏洩防止)
                f.write(json.dumps(entry, ensure_ascii=False, default=_safe_json_default) + "\n")
                f.flush()
            finally:
                fcntl.flock(f, fcntl.LOCK_UN)
    except Exception as e:
        sid = payload.get("session_id", "")
        cwd = payload.get("cwd", "")
        print(
            f"[permission-request-logger] session={sid} cwd={cwd} type={type(e).__name__} err={e}",
            file=sys.stderr,
        )


def main() -> int:
    try:
        # json.JSONDecodeError は ValueError サブクラス。OSError は stdin の
        # I/O 障害 (まれ) を握り潰す。それ以外の予期せぬ例外 (MemoryError 等)
        # は素通り stderr に traceback を出し、調査の手掛かりにする。
        payload = json.load(sys.stdin)
    except (ValueError, OSError):
        return 0
    if not isinstance(payload, dict):
        # PermissionRequest payload は dict 想定 (json.load は list/str/number
        # 等も返しうるが、本 hook の対象は dict 形式のみ)。dict 以外は
        # debug log でも本体 append でも処理対象外。stderr に痕跡を
        # 残して、schema の変化に気づけるようにする。
        print(
            f"[permission-request-logger] non-dict payload type={type(payload).__name__}",
            file=sys.stderr,
        )
        return 0
    _debug_dump(payload)
    append_log(payload)
    return 0


if __name__ == "__main__":
    sys.exit(main())
