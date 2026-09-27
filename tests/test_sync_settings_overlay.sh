#!/bin/bash
# sync-dotclaude.sh の settings.json 生成（リポ版 + マシン固有 overlay のマージ）の動作検査
#
# 実行: bash tests/test_sync_settings_overlay.sh
#
# user レベルの ~/.claude/settings.local.json は Claude Code に読まれない（v2.1.282 で実測）。
# そのためマシン固有の設定は ~/.claude/settings.machine.json に置き、sync が
# リポの settings.json とマージして ~/.claude/settings.json を生成する。
#
#   - overlay 無し → リポ版と同内容
#   - overlay 有り → dict は再帰マージ、list はリポ版に無い要素を追記、スカラーは overlay 優先
#   - 再実行で変化なし（冪等）
#   - 前回配置後の直接編集（hook / hook 以外 / 壊れた JSON）→ 退避 + WARN (exit 2)。同内容の退避は重ねない
#   - overlay から hook を消す正当な削除 → 退避も WARN も出ない
#   - overlay が実在しない hook を参照 → FATAL (exit 1)、settings.json は変えない
#   - overlay が不正（JSON 不正 / トップレベルが object でない / dict・list を別の型で上書き）
#     → FATAL (exit 1)、settings.json は変えない
#   - 旧方式の symlink → 生成ファイルへ移行
#   - 読まれない settings.local.json に hooks / permissions → WARN (exit 2)

set -u
for cmd in jq python3; do
    command -v "$cmd" >/dev/null 2>&1 || { echo "[FAIL] 前提: $cmd が必要"; exit 1; }
done
REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
SYNC="$REPO_DIR/sync-dotclaude.sh"
TMP="$(mktemp -d)"
trap 'rm -rf "${TMP:?}"' EXIT

pass=0; fail=0
check() {  # $1=説明 $2...=評価コマンド
    local desc="$1"; shift
    if "$@"; then echo "[PASS] $desc"; pass=$((pass + 1))
    else echo "[FAIL] $desc"; fail=$((fail + 1)); fi
}
run_sync() { CLAUDE_HOME="$1" bash "$SYNC" >"$1.log" 2>&1; echo $? >"$1.rc"; }
rc() { cat "$1.rc"; }
jqe() { jq -e "$@" >/dev/null; }
jq_eq() { [ "$(jq -S . "$1")" = "$(jq -S . "$2")" ]; }
n_backups() { find "$1" -maxdepth 1 -name 'settings.json.bak-*' | wc -l | tr -d ' '; }
not_grep() { ! grep -qE "$@"; }
mode_of() { python3 -c 'import os,sys; print(format(os.stat(sys.argv[1]).st_mode & 0o777, "o"))' "$1"; }
n_hook_links() { find "$1/hooks" -maxdepth 1 -type l 2>/dev/null | wc -l | tr -d ' '; }
MACHINE_HOOK='{ "matcher": "*", "hooks": [ { "type": "command", "command": "/opt/machine-hook.sh" } ] }'

# 1) overlay 無し → リポ版と同内容
H="$TMP/h1"; mkdir -p "$H"
run_sync "$H"
check "overlay 無し: exit 0" [ "$(rc "$H")" = 0 ]
check "overlay 無し: リポ版と同内容" jq_eq "$H/settings.json" "$REPO_DIR/settings.json"
check "overlay 無し: 実ファイル（symlink でない）" [ ! -L "$H/settings.json" ]
check "overlay 無し: 退避なし" [ "$(n_backups "$H")" = 0 ]
check "overlay 無し: settings.json のモードは 644" [ "$(mode_of "$H/settings.json")" = 644 ]

# 2) overlay 有り → マージ
H="$TMP/h2"; mkdir -p "$H"
FIRST_ALLOW="$(jq -r '.permissions.allow[0]' "$REPO_DIR/settings.json")"
cat >"$H/settings.machine.json" <<EOF
{
  "model": "machine-model",
  "permissions": { "allow": ["$FIRST_ALLOW", "Bash(machine-only:*)"] },
  "hooks": { "PreToolUse": [ $MACHINE_HOOK ] },
  "machineOnlyKey": true
}
EOF
run_sync "$H"
check "overlay 有り: exit 0" [ "$(rc "$H")" = 0 ]
check "overlay 有り: allow にマシン固有エントリが入る" \
    jqe '.permissions.allow | index("Bash(machine-only:*)")' "$H/settings.json"
check "overlay 有り: allow の重複は除去される" \
    [ "$(jq --arg a "$FIRST_ALLOW" '[.permissions.allow[] | select(. == $a)] | length' "$H/settings.json")" = 1 ]
check "overlay 有り: allow のリポ版エントリは全て残る" \
    [ "$(jq -s '(.[1].permissions.allow - .[0].permissions.allow) | length' "$H/settings.json" "$REPO_DIR/settings.json")" = 0 ]
check "overlay 有り: PreToolUse にマシン固有 hook が追加される" \
    jqe '[.hooks.PreToolUse[].hooks[].command] | index("/opt/machine-hook.sh")' "$H/settings.json"
check "overlay 有り: PreToolUse のリポ版 hook は全て残る" \
    [ "$(jq -s '([.[1].hooks.PreToolUse[]] - [.[0].hooks.PreToolUse[]]) | length' "$H/settings.json" "$REPO_DIR/settings.json")" = 0 ]
check "overlay 有り: スカラーは overlay が勝つ" jqe '.model == "machine-model"' "$H/settings.json"
check "overlay 有り: overlay 固有キーが入る" jqe '.machineOnlyKey == true' "$H/settings.json"

# 3) 冪等
cp "$H/settings.json" "$TMP/h2.gen"
run_sync "$H"
check "再実行: exit 0" [ "$(rc "$H")" = 0 ]
check "再実行: 内容不変" cmp -s "$H/settings.json" "$TMP/h2.gen"
check "再実行: settings.json の更新表示なし" not_grep '^  (update|migrate) *: settings\.json' "$H.log"

# 4) 直接編集された hook → 退避 + WARN
jq '.hooks.Stop = [{"hooks":[{"type":"command","command":"/opt/orca-hook.sh"}]}]' "$H/settings.json" >"$TMP/ext.json"
cp "$TMP/ext.json" "$H/settings.json"
run_sync "$H"
check "直接編集 hook: exit 2" [ "$(rc "$H")" = 2 ]
check "直接編集 hook: WARN に変更キー hooks が出る" grep -q 'WARN.*変更キー: hooks' "$H.log"
check "直接編集 hook: 退避が直接編集版と一致" \
    bash -c "cmp -s \"\$(ls '$H'/settings.json.bak-* | tail -1)\" '$TMP/ext.json'"
check "直接編集 hook: 退避のパーミッションは 600" \
    [ "$(mode_of "$(ls "$H"/settings.json.bak-* | tail -1)")" = 600 ]
check "直接編集 hook: settings.json は生成版に戻る" cmp -s "$H/settings.json" "$TMP/h2.gen"

# 5) 同じ直接編集が繰り返される（書き戻し続けるツール）→ 退避は重ねない
cp "$TMP/ext.json" "$H/settings.json"
run_sync "$H"
check "同内容の再編集: exit 2" [ "$(rc "$H")" = 2 ]
check "同内容の再編集: 退避は 1 件のまま" [ "$(n_backups "$H")" = 1 ]

# 6) hook 以外の直接編集 → 退避 + WARN
jq '.enabledPlugins = {"x@y": true}' "$TMP/h2.gen" >"$H/settings.json"
run_sync "$H"
check "hook 以外の直接編集: exit 2" [ "$(rc "$H")" = 2 ]
check "hook 以外の直接編集: WARN に変更キー enabledPlugins が出る" grep -q 'WARN.*enabledPlugins' "$H.log"
check "hook 以外の直接編集: 退避が増える" [ "$(n_backups "$H")" = 2 ]

# 6b) 書式だけの変更（キー順・インデント）→ 退避も WARN も出ない
jq -S --indent 4 . "$H/settings.json" >"$TMP/fmt.json" && cp "$TMP/fmt.json" "$H/settings.json"
run_sync "$H"
check "書式だけの変更: exit 0" [ "$(rc "$H")" = 0 ]
check "書式だけの変更: WARN なし" not_grep 'WARN' "$H.log"
check "書式だけの変更: 退避は増えない" [ "$(n_backups "$H")" = 2 ]

# 7) overlay から hook を消す正当な削除 → 退避も WARN も出ない
jq 'del(.hooks)' "$H/settings.machine.json" >"$TMP/ov.json" && cp "$TMP/ov.json" "$H/settings.machine.json"
run_sync "$H"
check "overlay の hook 削除: exit 0" [ "$(rc "$H")" = 0 ]
check "overlay の hook 削除: WARN なし" not_grep 'WARN' "$H.log"
check "overlay の hook 削除: 退避は増えない" [ "$(n_backups "$H")" = 2 ]
check "overlay の hook 削除: マシン固有 hook が消える" \
    bash -c "! jq -e '[.hooks.PreToolUse[].hooks[].command] | index(\"/opt/machine-hook.sh\")' '$H/settings.json' >/dev/null"

# 8) 配置済み settings.json が壊れた JSON → 退避してから上書き
echo '{ broken' >"$H/settings.json"
run_sync "$H"
check "壊れた配置済み: exit 2" [ "$(rc "$H")" = 2 ]
check "壊れた配置済み: 退避が増える" [ "$(n_backups "$H")" = 3 ]
check "壊れた配置済み: settings.json は正しい JSON に戻る" jqe . "$H/settings.json"

# 8b) リポ側から設定を消す正当な削除（前回配置にあった hook が今回の生成版に無い）→ 退避も WARN も出ない
H="$TMP/h8b"; mkdir -p "$H"
jq '.hooks.Stop = [{"hooks":[{"type":"command","command":"/opt/removed-from-repo.sh"}]}]' "$REPO_DIR/settings.json" >"$H/settings.json"
cp "$H/settings.json" "$H/.settings.generated.json"
run_sync "$H"
check "リポ側の削除: exit 0" [ "$(rc "$H")" = 0 ]
check "リポ側の削除: WARN なし" not_grep 'WARN' "$H.log"
check "リポ側の削除: 退避なし" [ "$(n_backups "$H")" = 0 ]
check "リポ側の削除: 生成版になる" jq_eq "$H/settings.json" "$REPO_DIR/settings.json"

# 9) overlay が実在しない hook を参照 → FATAL、settings.json は変えない
H="$TMP/h9"; mkdir -p "$H"
run_sync "$H"
cp "$H/settings.json" "$TMP/h9.before"
cat >"$H/settings.machine.json" <<'EOF'
{ "hooks": { "Stop": [ { "hooks": [ { "type": "command", "command": "~/.claude/hooks/no-such-hook.sh" } ] } ] } }
EOF
run_sync "$H"
check "欠落 hook 参照: exit 1" [ "$(rc "$H")" = 1 ]
check "欠落 hook 参照: FATAL 表示" grep -q 'FATAL.*no-such-hook.sh' "$H.log"
check "欠落 hook 参照: settings.json は変えない" cmp -s "$H/settings.json" "$TMP/h9.before"
H="$TMP/h9b"; mkdir -p "$H"
cp "$TMP/h9/settings.machine.json" "$H/"
run_sync "$H"
check "欠落 hook 参照（新規）: settings.json を作らない" [ ! -e "$H/settings.json" ]
H="$TMP/h9c"; mkdir -p "$H"
cat >"$H/settings.machine.json" <<'EOF'
{ "hooks": { "Stop": [ { "hooks": [ { "type": "command", "command": "${HOME}/.claude/hooks/no-such-hook2.sh" } ] } ] } }
EOF
run_sync "$H"
check "欠落 hook 参照（\${HOME} 形式）: exit 1" [ "$(rc "$H")" = 1 ]
check "欠落 hook 参照（\${HOME} 形式）: FATAL 表示" grep -q 'FATAL.*no-such-hook2.sh' "$H.log"
H="$TMP/h9d"; mkdir -p "$H"
cat >"$H/settings.machine.json" <<'EOF'
{ "hooks": { "Stop": [ { "hooks": [
  { "type": "command", "command": "python3 /Users/nobody/.claude/hooks/no-such-abs.py" },
  { "type": "command", "command": "python3 \"$HOME\"/.claude/hooks/no-such-quoted.py" } ] } ] } }
EOF
run_sync "$H"
check "欠落 hook 参照（絶対パス・クォート付き）: exit 1" [ "$(rc "$H")" = 1 ]
check "欠落 hook 参照（絶対パス）: FATAL 表示" grep -q 'FATAL.*no-such-abs.py' "$H.log"
check "欠落 hook 参照（クォート付き）: FATAL 表示" grep -q 'FATAL.*no-such-quoted.py' "$H.log"
check "欠落 hook 参照（絶対パス・クォート付き）: settings.json を作らない" [ ! -e "$H/settings.json" ]
H="$TMP/h9e"; mkdir -p "$H"
cat >"$H/settings.machine.json" <<EOF
{ "hooks": { "SessionStart": [ { "hooks": [
  { "type": "command", "command": "python3 $HOME/.claude/hooks/no-such-home-abs.py" } ] } ] } }
EOF
run_sync "$H"
check "欠落 hook 参照（\$HOME の絶対パス展開済み）: FATAL 表示" grep -q 'FATAL.*no-such-home-abs.py' "$H.log"

# 9b) ~/.claude/hooks/ 以外の .claude/hooks/ を指す絶対パス → 参照先そのものの実在で判定する
mkdir -p "$TMP/proj/.claude/hooks" && : >"$TMP/proj/.claude/hooks/projhook.sh"
H="$TMP/h9f"; mkdir -p "$H"
cat >"$H/settings.machine.json" <<EOF
{ "hooks": { "SessionStart": [ { "hooks": [
  { "type": "command", "command": "bash $TMP/proj/.claude/hooks/projhook.sh" } ] } ] } }
EOF
run_sync "$H"
check "別の場所に実在する .claude/hooks/: exit 0" [ "$(rc "$H")" = 0 ]
check "別の場所に実在する .claude/hooks/: 配置される" \
    jqe --arg c "bash $TMP/proj/.claude/hooks/projhook.sh" '[.hooks.SessionStart[].hooks[].command] | index($c)' "$H/settings.json"
H="$TMP/h9g"; mkdir -p "$H"
REPO_HOOK="$(jq -r '[.hooks[][].hooks[].command | capture("hooks/(?<n>[A-Za-z0-9._-]+)").n][0]' "$REPO_DIR/settings.json")"
cat >"$H/settings.machine.json" <<EOF
{ "hooks": { "SessionStart": [ { "hooks": [
  { "type": "command", "command": "python3 /Users/olduser/.claude/hooks/$REPO_HOOK" } ] } ] } }
EOF
run_sync "$H"
check "実在しない絶対パス（同名が ~/.claude/hooks にある）: exit 1" [ "$(rc "$H")" = 1 ]
check "実在しない絶対パス（同名が ~/.claude/hooks にある）: settings.json を作らない" [ ! -e "$H/settings.json" ]
H="$TMP/h9h"; mkdir -p "$H"
cat >"$H/settings.machine.json" <<'EOF'
{ "hooks": { "SessionStart": [ { "hooks": [
  { "type": "command", "command": "sh $CLAUDE_PROJECT_DIR/.claude/hooks/a.sh" },
  { "type": "command", "command": "sh \"$CLAUDE_PROJECT_DIR\"/.claude/hooks/b.sh 2>/dev/null || true" },
  { "type": "command", "command": "sh ${CLAUDE_PROJECT_DIR}/.claude/hooks/c.sh" },
  { "type": "command", "command": "sh proj/.claude/hooks/d.sh" },
  { "type": "command", "command": "./.claude/hooks/e.sh" } ] } ] } }
EOF
run_sync "$H"
check "他の変数・相対パスの .claude/hooks/: exit 0" [ "$(rc "$H")" = 0 ]
check "他の変数・相対パスの .claude/hooks/: FATAL なし" not_grep 'FATAL' "$H.log"
check "他の変数・相対パスの .claude/hooks/: 配置される" [ -e "$H/settings.json" ]

# 10) overlay が不正 → FATAL、settings.json は変えない
i=0
for bad in '{ broken' '[]' '{ "hooks": null }' '{ "permissions": { "allow": "Bash(x)" } }'; do
    i=$((i + 1)); H="$TMP/h10-$i"; mkdir -p "$H"
    run_sync "$H"
    cp "$H/settings.json" "$H.before"
    printf '%s\n' "$bad" >"$H/settings.machine.json"
    run_sync "$H"
    check "不正 overlay ($bad): exit 1" [ "$(rc "$H")" = 1 ]
    check "不正 overlay ($bad): settings.json は変えない" cmp -s "$H/settings.json" "$H.before"
done
H="$TMP/h10n"; mkdir -p "$H"
echo '[]' >"$H/settings.machine.json"
run_sync "$H"
check "不正 overlay（新規）: settings.json を作らない" [ ! -e "$H/settings.json" ]
check "不正 overlay（新規）: hook の symlink 同期は行う" [ "$(n_hook_links "$H")" -gt 0 ]

# 10b) python3 が無い → FATAL、settings.json は変えず、symlink 同期は行う
NOPY="$TMP/nopy-bin"; mkdir -p "$NOPY"
for d in /bin /usr/bin; do
    for c in "$d"/*; do
        case "$(basename "$c")" in python*) continue ;; esac
        [ -e "$NOPY/$(basename "$c")" ] || ln -s "$c" "$NOPY/$(basename "$c")"
    done
done
H="$TMP/h10p"; mkdir -p "$H"
run_sync "$H"
cp "$H/settings.json" "$H.before"
rm -f "$H"/hooks/*
PATH="$NOPY" CLAUDE_HOME="$H" /bin/bash "$SYNC" >"$H.log" 2>&1; echo $? >"$H.rc"
check "python3 不在: exit 1" [ "$(rc "$H")" = 1 ]
check "python3 不在: FATAL 表示" grep -q 'FATAL.*python3' "$H.log"
check "python3 不在: settings.json は変えない" cmp -s "$H/settings.json" "$H.before"
check "python3 不在: hook の symlink 同期は行う" [ "$(n_hook_links "$H")" -gt 0 ]

# 11) 旧方式の symlink → 生成ファイルへ移行
H="$TMP/h11"; mkdir -p "$H"
ln -s "$REPO_DIR/settings.json" "$H/settings.json"
run_sync "$H"
check "symlink 移行: exit 0" [ "$(rc "$H")" = 0 ]
check "symlink 移行: 実ファイルになる" [ ! -L "$H/settings.json" ]
check "symlink 移行: リポ版と同内容" jq_eq "$H/settings.json" "$REPO_DIR/settings.json"

# 12) 前回配置の記録が無い既存 settings.json（PR #14 のコピー方式から移行）→ 退避してから生成版を配置
H="$TMP/h12"; mkdir -p "$H"
jq '.legacyLocalEdit = 1' "$REPO_DIR/settings.json" >"$H/settings.json"
run_sync "$H"
check "記録なし既存: exit 2" [ "$(rc "$H")" = 2 ]
check "記録なし既存: 退避される" [ "$(n_backups "$H")" = 1 ]
check "記録なし既存: 生成版になる" jq_eq "$H/settings.json" "$REPO_DIR/settings.json"

# 13) 読まれない settings.local.json に permissions → WARN
H="$TMP/h13"; mkdir -p "$H"
echo '{ "permissions": { "allow": ["Bash(x)"] } }' >"$H/settings.local.json"
run_sync "$H"
check "settings.local.json に permissions: exit 2" [ "$(rc "$H")" = 2 ]
check "settings.local.json に permissions: WARN" grep -q 'WARN.*settings.local.json' "$H.log"
H="$TMP/h13b"; mkdir -p "$H"
echo '{ "effortLevel": "high" }' >"$H/settings.local.json"
run_sync "$H"
check "settings.local.json に hooks / permissions 無し: exit 0" [ "$(rc "$H")" = 0 ]

echo
echo "結果: PASS=$pass FAIL=$fail"
[ "$fail" -eq 0 ]
