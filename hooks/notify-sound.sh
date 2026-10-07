#!/bin/sh
# Cross-platform notification sound for Claude Code hooks
# (Notification / PermissionRequest / Stop).
#
# - WSL2: plays Windows notify.wav via powershell.exe.
# - macOS: plays /System/Library/Sounds/Glass.aiff via afplay if both
#   exist; otherwise no-op. Plays in the background because afplay takes
#   3-4 s to return, which would delay the hook. Sounds from hooks fired
#   close together may overlap. A long sound set via CLAUDE_NOTIFY_SOUND
#   keeps playing to the end, even after Ctrl-C or the session ends.
# - native Linux: plays a sound only if both a player and a
#   sound file exist; otherwise no-op.
# Always exits 0 so the hook never reports an error on hosts without the
# relevant tooling (e.g. powershell.exe absent on native Linux).
#
# Override the macOS / Linux sound file via CLAUDE_NOTIFY_SOUND.

WIN_WAV='C:\Windows\Media\notify.wav'
MAC_SOUND="${CLAUDE_NOTIFY_SOUND:-/System/Library/Sounds/Glass.aiff}"
LINUX_SOUND="${CLAUDE_NOTIFY_SOUND:-/usr/share/sounds/freedesktop/stereo/complete.oga}"

if command -v powershell.exe >/dev/null 2>&1; then
    powershell.exe -c "(New-Object Media.SoundPlayer \"$WIN_WAV\").PlaySync()" >/dev/null 2>&1
elif [ "$(uname -s 2>/dev/null)" = Darwin ]; then
    if [ -f "$MAC_SOUND" ] && command -v afplay >/dev/null 2>&1; then
        afplay "$MAC_SOUND" </dev/null >/dev/null 2>&1 &
    fi
elif [ -f "$LINUX_SOUND" ]; then
    # 既定音源は .oga (Ogg Vorbis)。paplay / pw-play / ffplay は再生可能だが、
    # aplay は WAV/raw 専用で .oga をデコードできない (その場合は無音 = no-op)。
    # WAV 音源を使う環境では CLAUDE_NOTIFY_SOUND で .wav を指定すれば aplay でも鳴る。
    if command -v paplay >/dev/null 2>&1; then
        paplay "$LINUX_SOUND" >/dev/null 2>&1
    elif command -v pw-play >/dev/null 2>&1; then
        pw-play "$LINUX_SOUND" >/dev/null 2>&1
    elif command -v ffplay >/dev/null 2>&1; then
        ffplay -nodisp -autoexit -loglevel quiet "$LINUX_SOUND" >/dev/null 2>&1
    elif command -v aplay >/dev/null 2>&1; then
        aplay -q "$LINUX_SOUND" >/dev/null 2>&1
    fi
fi

exit 0
