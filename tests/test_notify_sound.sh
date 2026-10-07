#!/bin/bash
# Regression tests for hooks/notify-sound.sh (OS ごとの通知音の分岐)。
#
# 実行: bash tests/test_notify_sound.sh
# 前提:
#   - リポ内 hooks/notify-sound.sh を直接実行する (~/.claude への symlink 状況に非依存)。
#   - PATH を stub のディレクトリだけにして /bin/sh で起動する。uname・afplay・paplay・
#     powershell.exe を stub に差し替え、実物のプレイヤーで音を鳴らさない。
#     stub は PATH に外部コマンドが無いので、組み込みコマンドだけで呼ばれ方を記録する。
#     記録先 (LOG) と停止の合図 (STOP) は環境変数で渡し、stub の本文にパスを埋め込まない。
#   - macOS の分岐は afplay を裏で起動するので、記録が書かれるまで wait_calls で待つ。
#   - macOS の既定の音 (/System/Library/Sounds/Glass.aiff) を使うケースは、
#     ホストにそのファイルが無ければ SKIP する。

REPO="$(cd "$(dirname "$0")/.." && pwd)"
HOOK="$REPO/hooks/notify-sound.sh"
[ -f "$HOOK" ] || { echo "HOOK not found: $HOOK"; exit 1; }

WORK="$(mktemp -d)" && [ -n "$WORK" ] || { echo "mktemp failed"; exit 1; }
STOP="$WORK/stop"
# 中断されても裏の stub (mac_background) が残らないよう、STOP を作ってから消す。
trap ': > "$STOP" 2>/dev/null; rm -rf "$WORK"' EXIT
SOUND="$WORK/sound.aiff"
: > "$SOUND"
FAIL=0

# stub を作る。$1=コマンド名 $2=終了コード。呼ばれたら「名前 引数…」を LOG に追記する。
# echo は使わない (macOS の /bin/sh の echo は引数の C:\Windows\Media\notify.wav の \n を改行にする)。
make_stub() {
  cat > "$BIN/$1" <<'EOF'
#!/bin/sh
printf '%s\n' "${0##*/} $*" >> "$LOG"
EOF
  printf 'exit %s\n' "$2" >> "$BIN/$1"
  chmod +x "$BIN/$1"
}

# uname の stub。$1=返す OS 名 (呼び出しは記録しない)。
make_uname() {
  printf '#!/bin/sh\necho %s\n' "$1" > "$BIN/uname"
  chmod +x "$BIN/uname"
}

# ケースごとに stub のディレクトリと記録を分ける (裏で動く stub の遅れた記録が次のケースに混ざらないように)。
reset_case() {
  BIN="$WORK/bin-$1"
  LOG="$WORK/calls-$1.log"
  mkdir -p "$BIN"
  : > "$LOG"
}

# hook を起動する。CLAUDE_NOTIFY_SOUND は $1 (空なら未設定) で渡す。終了コードを RC に入れる。
fire() {
  if [ -n "$1" ]; then
    env -i PATH="$BIN" LOG="$LOG" STOP="$STOP" CLAUDE_NOTIFY_SOUND="$1" /bin/sh "$HOOK"
  else
    env -i PATH="$BIN" LOG="$LOG" STOP="$STOP" /bin/sh "$HOOK"
  fi
  RC=$?
}

assert_eq() {  # $1=name $2=expected $3=actual
  if [ "$2" = "$3" ]; then
    printf 'PASS  %s\n' "$1"
  else
    printf 'FAIL  %s  (expected=[%s] actual=[%s])\n' "$1" "$2" "$3"
    FAIL=1
  fi
}

calls() { cat "$LOG"; }

# 裏で起動した stub が記録を書くまで最大 5 秒待つ。記録しないケースは 1 秒だけ待つ。
wait_calls() {
  for _ in $(seq 50); do [ -s "$LOG" ] && return; sleep 0.1; done
}
wait_none() { sleep 1; }

# --- macOS ---

reset_case mac_env
make_uname Darwin; make_stub afplay 0
fire "$SOUND"
wait_calls
assert_eq "macOS: CLAUDE_NOTIFY_SOUND を afplay で鳴らす" "afplay $SOUND" "$(calls)"
assert_eq "macOS: exit 0" 0 "$RC"

MAC_DEFAULT=/System/Library/Sounds/Glass.aiff
if [ -f "$MAC_DEFAULT" ]; then
  reset_case mac_default
  make_uname Darwin; make_stub afplay 0
  fire ""
  wait_calls
  assert_eq "macOS: 未指定なら Glass.aiff を鳴らす" "afplay $MAC_DEFAULT" "$(calls)"
else
  printf 'SKIP  macOS: 未指定なら Glass.aiff を鳴らす (%s が無い)\n' "$MAC_DEFAULT"
fi

reset_case mac_no_player
make_uname Darwin; make_stub paplay 0
fire "$SOUND"
wait_none
assert_eq "macOS: afplay が無ければ何もしない" "" "$(calls)"
assert_eq "macOS: afplay が無くても exit 0" 0 "$RC"

reset_case mac_missing_file
make_uname Darwin; make_stub afplay 0
fire "$WORK/no-such.aiff"
wait_none
assert_eq "macOS: 音のファイルが無ければ何もしない" "" "$(calls)"
assert_eq "macOS: 音のファイルが無くても exit 0" 0 "$RC"

reset_case mac_fail
make_uname Darwin; make_stub afplay 1
fire "$SOUND"
wait_calls
assert_eq "macOS: afplay が失敗しても呼び出しまでは届く" "afplay $SOUND" "$(calls)"
assert_eq "macOS: afplay が失敗しても exit 0" 0 "$RC"

# afplay が鳴り終わらなくても hook は戻る (stub は STOP ファイルができるか $WORK が消えるまで終わらない)。
# hook の stdout・stderr をパイプで受け、EOF まで測る (Claude Code は hook の出力を受け取るため、
# 裏の afplay が出力を引き継いでいると hook が終わっても待たされる)。
reset_case mac_background
make_uname Darwin
ln -s "$(command -v sleep)" "$BIN/sleep"
cat > "$BIN/afplay" <<'EOF'
#!/bin/sh
printf '%s\n' "afplay $*" >> "$LOG"
while [ ! -f "$STOP" ] && [ -d "${STOP%/*}" ]; do sleep 0.1; done
EOF
chmod +x "$BIN/afplay"
fire "$SOUND" 2>&1 | cat > /dev/null &
READER_PID=$!   # パイプの読み手 (cat)。hook 側の出力がすべて閉じたら終わる
for _ in $(seq 50); do kill -0 "$READER_PID" 2>/dev/null || break; sleep 0.1; done
state="出力が閉じた"
kill -0 "$READER_PID" 2>/dev/null && state="5 秒たっても出力が開いたまま"
assert_eq "macOS: afplay の終了を待たずに戻る" "出力が閉じた" "$state"
wait_calls
assert_eq "macOS: 裏で afplay を起動する" "afplay $SOUND" "$(calls)"
: > "$STOP"   # 裏の stub を終わらせる
wait

# --- WSL2 (既存の挙動の回帰) ---

reset_case wsl
make_uname Linux; make_stub powershell.exe 0; make_stub afplay 0; make_stub paplay 0
fire "$SOUND"
case "$(calls)" in
  "powershell.exe "*) assert_eq "WSL2: powershell.exe だけを呼ぶ" 1 "$(grep -c . "$LOG")" ;;
  *) assert_eq "WSL2: powershell.exe だけを呼ぶ" "powershell.exe ..." "$(calls)" ;;
esac

# --- Linux (既存の挙動の回帰) ---

reset_case linux
make_uname Linux; make_stub paplay 0; make_stub afplay 0
fire "$SOUND"
assert_eq "Linux: paplay で鳴らし afplay は呼ばない" "paplay $SOUND" "$(calls)"

reset_case linux_no_player
make_uname Linux
fire "$SOUND"
assert_eq "Linux: プレイヤーが無ければ何もしない" "" "$(calls)"
assert_eq "Linux: プレイヤーが無くても exit 0" 0 "$RC"

if [ "$FAIL" -ne 0 ]; then
  echo "RESULT: FAIL"
  exit 1
fi
echo "RESULT: OK"
