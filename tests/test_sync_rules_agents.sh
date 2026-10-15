#!/bin/bash
# sync-dotclaude.sh の rules / agents 同期と、setup.sh が導入先に配るもの・触れないものの検査
#
# 実行: bash tests/test_sync_rules_agents.sh
#
#   - rules/global/<category>/ → ~/.claude/rules/<category> をカテゴリ単位で symlink
#   - agents/global/*.md → ~/.claude/agents/<name>.md をファイル単位で symlink
#   - 同名の実体が居座る場合はスキップ + WARN (exit 2)
#   - このリポジトリ由来で実体が消えた rules / agents の symlink を dangling として検出（--prune で除去）
#   - 実体を退避したあと再同期すると symlink になり exit 0（既存環境の一度きりの移行）
#   - リポの外を指す symlink は張り替え、WARN に元のリンク先と戻すコマンドを出す (exit 2)。
#     同じリポを別の綴り（symlink 経由のパス・末尾 / の有無）で指すリンクは今までどおり静かに張り直す。
#     .. を含む綴りでリポの外を指すリンクは見逃さない。戻すコマンドは非 ASCII のパスでも正しい UTF-8
#   - このリポジトリ自身の .claude/rules は rules/hve とリポジトリ専用の testing.md だけ、
#     .claude/agents は agents/hve-*.md だけを指す
#     （global 配下を project-level で重ねて読ませない。サブディレクトリの agent も読み込まれるため）
#   - setup.sh は rules/global・agents/global・global skill を導入先にコピーしない
#     （cq/mdq の導入分岐に入らないよう、python3 をスタブにして実行する）
#   - workflows/hve-*.js が Read させる SKILL.md は、導入先でも自リポでもルートから解決できる
#   - setup.sh は rules/hve/local-overrides.md を配り、完了メッセージで .claude/rules/hve-local/ を案内する
#   - setup.sh を再実行しても .claude/rules/hve-local/ には触れない（既存の挙動を固定する回帰テスト）
#   - setup.sh は LICENSE を .claude/LICENSE-hve-playbook に配り、再実行で最新の LICENSE に戻す
#     （写しの位置が symlink でも、リンク先は書き換えずに実ファイルの写しに置き換える）

set -u
command -v python3 >/dev/null 2>&1 || { echo "[FAIL] 前提: python3 が必要"; exit 1; }
REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
SYNC="$REPO_DIR/sync-dotclaude.sh"
TMP="$(mktemp -d)"
trap 'rm -rf "${TMP:?}"' EXIT

pass=0; fail=0
check() {
    local desc="$1"; shift
    if "$@"; then echo "[PASS] $desc"; pass=$((pass + 1))
    else echo "[FAIL] $desc"; fail=$((fail + 1)); fi
}
run_sync() { CLAUDE_HOME="$1" bash "$SYNC" "${@:2}" >"$1.log" 2>&1; echo $? >"$1.rc"; }
rc() { cat "$1.rc"; }
links_to() { [ -L "$1" ] && [ "$(readlink "$1")" = "$2" ]; }

CATEGORY="$(basename "$(find "$REPO_DIR/rules/global" -mindepth 1 -maxdepth 1 -type d | sort | head -1)")"
AGENT="$(basename "$(find "$REPO_DIR/agents/global" -maxdepth 1 -name '*.md' | sort | head -1)")"
check "前提: rules/global にカテゴリがある" [ -n "$CATEGORY" ]
check "前提: agents/global に agent がある" [ -n "$AGENT" ]

# 1) 新規: rules / agents の symlink が張られる
H="$TMP/h1"; mkdir -p "$H"
run_sync "$H"
check "新規: exit 0" [ "$(rc "$H")" = 0 ]
check "新規: rules のカテゴリが symlink" links_to "$H/rules/$CATEGORY" "$REPO_DIR/rules/global/$CATEGORY/"
check "新規: 全カテゴリが張られる" \
    [ "$(find "$H/rules" -mindepth 1 -maxdepth 1 -type l | wc -l)" -eq "$(find "$REPO_DIR/rules/global" -mindepth 1 -maxdepth 1 -type d | wc -l)" ]
check "新規: agent が symlink" links_to "$H/agents/$AGENT" "$REPO_DIR/agents/global/$AGENT"
check "新規: hve-* の agent は張らない" [ -z "$(find "$H/agents" -name 'hve-*' 2>/dev/null)" ]
check "新規: rules/hve は張らない" [ ! -e "$H/rules/hve" ]

# 2) 冪等
run_sync "$H"
check "再実行: exit 0" [ "$(rc "$H")" = 0 ]
check "再実行: link も張り直しも無し" grep -q 'link=0 fix=0' "$H.log"

# 3) 実体が居座る → スキップ + WARN
H="$TMP/h3"; mkdir -p "$H/rules/$CATEGORY" "$H/agents"
echo 'local' >"$H/rules/$CATEGORY/local.md"
echo 'local' >"$H/agents/$AGENT"
run_sync "$H"
check "実体の居座り: exit 2" [ "$(rc "$H")" = 2 ]
check "実体の居座り: rules は WARN" grep -q "WARN.*rules/$CATEGORY" "$H.log"
check "実体の居座り: agents は WARN" grep -q "WARN.*agents/$AGENT" "$H.log"
check "実体の居座り: rules の実体は残る" [ -f "$H/rules/$CATEGORY/local.md" ]
check "実体の居座り: agent の実体は symlink にされない" [ ! -L "$H/agents/$AGENT" ]

# 3b) 実体を退避してから再同期 → symlink になり exit 0（既存環境の移行）
mkdir -p "$H/backups"
mv "$H/rules/$CATEGORY" "$H/backups/" && mv "$H/agents/$AGENT" "$H/backups/"
run_sync "$H"
check "移行後: exit 0" [ "$(rc "$H")" = 0 ]
check "移行後: rules が symlink" links_to "$H/rules/$CATEGORY" "$REPO_DIR/rules/global/$CATEGORY/"
check "移行後: agent が symlink" links_to "$H/agents/$AGENT" "$REPO_DIR/agents/global/$AGENT"

# 3c) リポの外を指す symlink → 張り替え + WARN（元のリンク先と戻すコマンド）+ exit 2
H="$TMP/h3c"; OUT="$TMP/my dotfiles 日本語's/$CATEGORY"; mkdir -p "$H/rules" "$OUT"
echo mine >"$OUT/mine.md"
ln -s "$OUT" "$H/rules/$CATEGORY"
run_sync "$H"
check "リポの外: exit 2" [ "$(rc "$H")" = 2 ]
check "リポの外: WARN に元のリンク先を出す" sh -c 'grep "WARN" "$1" | grep -qF "$2"' _ "$H.log" "$OUT"
check "リポの外: リポへのリンクに張り替える" links_to "$H/rules/$CATEGORY" "$REPO_DIR/rules/global/$CATEGORY/"
check "リポの外: 元のリンク先の中身は変えない" [ "$(ls -A "$OUT")" = "mine.md" ]
cp "$H.log" "$H.first.log"
run_sync "$H"
check "リポの外（張り替え後の再実行）: exit 0" [ "$(rc "$H")" = 0 ]
check "リポの外（張り替え後の再実行）: WARN なし" sh -c '! grep -q WARN "$1"' _ "$H.log"
restore="$(grep -o 'ln -sfn .*' "$H.first.log" | grep -F "rules/$CATEGORY" | head -1)"
check "リポの外: WARN の戻すコマンドで元のリンクに戻る（空白・日本語・' を含むパス）" \
    sh -c '[ -n "$1" ] && bash -c "$1" && [ "$(readlink "$2")" = "$3" ]' _ "$restore" "$H/rules/$CATEGORY" "$OUT"
# 端末からコピーして貼れるよう、出力は正しい UTF-8 で、パスは文字のまま出す（bash 3.2 の %q は壊す）
check "リポの外: WARN の出力は正しい UTF-8" sh -c 'iconv -f UTF-8 -t UTF-8 "$1" >/dev/null 2>&1' _ "$H.first.log"
check "リポの外: 戻すコマンドにパスが文字のまま出る" grep -qF "日本語" "$H.first.log"

# 3c-2) . / .. を含む綴りでリポの外を指すリンク → 前方一致で見逃さず WARN (exit 2)
H="$TMP/h3c2"; mkdir -p "$H/rules"
ln -s "$REPO_DIR/../outside-dotdot" "$H/rules/$CATEGORY"
run_sync "$H"
check "..: リポの外を指す綴りは exit 2" [ "$(rc "$H")" = 2 ]
check "..: WARN を出す" grep -q "WARN.*rules/$CATEGORY" "$H.log"
# 最後の要素が .. の綴り（リポの親ディレクトリ）も見逃さない
for tgt in "$REPO_DIR/.." "$REPO_DIR/../" "$REPO_DIR/rules/../.." "$REPO_DIR/..//"; do
    H="$TMP/h3c2-tail"; rm -rf "$H"; mkdir -p "$H/rules"
    ln -s "$tgt" "$H/rules/$CATEGORY"
    run_sync "$H"
    check "..（末尾 ${tgt#"$REPO_DIR"}）: exit 2・WARN" sh -c '[ "$(cat "$1.rc")" = 2 ] && grep -q WARN "$1.log"' _ "$H"
done

# 3c-3) リポ配下を同じ前置きのパスで指し、末尾 / だけ違うリンク → 今までどおり fix 行だけで exit 0
H="$TMP/h3c3"; mkdir -p "$H/rules"
ln -s "$REPO_DIR/rules/global/$CATEGORY" "$H/rules/$CATEGORY"
run_sync "$H"
check "リポ配下の表記ゆれ: exit 0" [ "$(rc "$H")" = 0 ]
check "リポ配下の表記ゆれ: fix 行を出す" grep -q "fix *: $CATEGORY" "$H.log"
check "リポ配下の表記ゆれ: WARN なし" sh -c '! grep -q WARN "$1"' _ "$H.log"
check "リポ配下の表記ゆれ: 張り直す" links_to "$H/rules/$CATEGORY" "$REPO_DIR/rules/global/$CATEGORY/"

# 3d) 同じリポを別の綴り（symlink 経由のパス）で指すリンク → 今までどおり静かに張り直す（exit 0）
ALIAS="$TMP/repo-alias"; ln -s "$REPO_DIR" "$ALIAS"
H="$TMP/h3d"; mkdir -p "$H"
CLAUDE_HOME="$H" bash "$ALIAS/sync-dotclaude.sh" >"$H.log" 2>&1; echo $? >"$H.rc"
check "別の綴り: symlink 経由のパスで sync → exit 0" [ "$(rc "$H")" = 0 ]
run_sync "$H"
check "別の綴り: 実パスで再実行 → exit 0" [ "$(rc "$H")" = 0 ]
check "別の綴り: 実パスで再実行 → 張り直す" links_to "$H/rules/$CATEGORY" "$REPO_DIR/rules/global/$CATEGORY/"
check "別の綴り: 実パスで再実行 → WARN なし" sh -c '! grep -q WARN "$1"' _ "$H.log"
CLAUDE_HOME="$H" bash "$ALIAS/sync-dotclaude.sh" >"$H.log" 2>&1; echo $? >"$H.rc"
check "別の綴り: symlink 経由のパスで再実行 → exit 0・WARN なし" sh -c '[ "$(cat "$1.rc")" = 0 ] && ! grep -q WARN "$1.log"' _ "$H"

# 4) dangling 検出と --prune
H="$TMP/h4"; mkdir -p "$H/rules" "$H/agents"
ln -s "$REPO_DIR/rules/global/no-such-category/" "$H/rules/no-such-category"
ln -s "$REPO_DIR/agents/global/no-such-agent.md" "$H/agents/no-such-agent.md"
run_sync "$H"
check "dangling: exit 2" [ "$(rc "$H")" = 2 ]
check "dangling: rules を検出" grep -q 'DANGLE : no-such-category' "$H.log"
check "dangling: agents を検出" grep -q 'DANGLE : no-such-agent.md' "$H.log"
run_sync "$H" --prune
check "--prune: rules を除去" [ ! -L "$H/rules/no-such-category" ]
check "--prune: agents を除去" [ ! -L "$H/agents/no-such-agent.md" ]

# 4b) このリポジトリ自身の .claude/rules・.claude/agents
check "自リポ: .claude/rules は symlink でない" [ ! -L "$REPO_DIR/.claude/rules" ]
check "自リポ: .claude/rules/hve は rules/hve を指す" [ "$(readlink "$REPO_DIR/.claude/rules/hve")" = "../../rules/hve" ]
check "自リポ: .claude/rules 直下は hve と testing.md だけ" [ "$(ls -A "$REPO_DIR/.claude/rules" | tr '\n' ' ')" = "hve testing.md " ]
check "自リポ: .claude/agents は symlink でない" [ ! -L "$REPO_DIR/.claude/agents" ]
check "自リポ: .claude/agents は agents/hve-*.md だけを指す（global を project-level で重ねて読ませない）" \
    [ "$(cd "$REPO_DIR/.claude/agents" && for f in *; do printf '%s->%s\n' "$f" "$(readlink "$f")"; done)" \
      = "$(cd "$REPO_DIR/agents" && for f in hve-*.md; do printf '%s->../../agents/%s\n' "$f" "$f"; done)" ]

# 5) setup.sh は global 配下を配らない
T="$TMP/target"; mkdir -p "$T" "$TMP/stub-bin"
REAL_PY="$(command -v python3)"
cat >"$TMP/stub-bin/python3" <<EOF
#!/bin/bash
# cq / mdq は導入済みとして振る舞い、setup.sh の clone・pip install 分岐に入らせない
if [ "\$1" = "-m" ] && { [ "\$2" = "cq" ] || [ "\$2" = "mdq" ]; }; then exit 0; fi
exec "$REAL_PY" "\$@"
EOF
chmod +x "$TMP/stub-bin/python3"
PATH="$TMP/stub-bin:$PATH" bash "$REPO_DIR/setup.sh" "$T" >"$TMP/setup.log" 2>&1
check "setup.sh: exit 0" [ $? -eq 0 ]
check "setup.sh: cq/mdq の導入分岐に入らない" grep -q 'cq/mdq はインストール済み' "$TMP/setup.log"
check "setup.sh: rules/hve は配る" [ -d "$T/.claude/rules/hve" ]
check "setup.sh: rules/global は配らない" [ ! -e "$T/.claude/rules/global" ]
check "setup.sh: rules/<category> は配らない" [ ! -e "$T/.claude/rules/$CATEGORY" ]
check "setup.sh: agents/global は配らない" [ ! -e "$T/.claude/agents/global" ]
check "setup.sh: global の agent は配らない" [ ! -e "$T/.claude/agents/$AGENT" ]
check "setup.sh: global skill は配らない" [ ! -e "$T/.claude/skills/learn" ]
check "setup.sh: hve-implement skill を配る" [ -f "$T/.claude/skills/hve-implement/SKILL.md" ]

# 5b) 言語に依存しないクリーンアーキテクチャ規約（Issue #34、ADR 0018）
CA="$T/.claude/rules/hve/clean-architecture.md"
check "setup.sh: clean-architecture 規約を配る" [ -f "$CA" ]
# frontmatter（1 行目の --- から次の --- まで）の paths: に並ぶ glob を 1 行ずつ出す（クォートは外す）
# 閉じの --- が無い（frontmatter として読まれない）ときは何も出さない
ca_paths() { awk 'NR==1&&$0!="---"{exit} NR>1&&$0=="---"{closed=1; exit} /^paths:/{on=1;next} on&&/^[^ ]/{on=0} on&&/^ *- /{sub(/^ *- */,""); gsub(/["\047]/,""); buf=buf $0 "\n"} END{if(closed) printf "%s", buf}' "$CA" 2>/dev/null; }
# paths: が対象の 16 種の拡張子と過不足なく一致する（.md・**/*・.sh などの混入や欠けを検出する）
CA_EXPECTED="$(for e in rs go py rb php java kt cs ts tsx js jsx vue svelte swift dart; do printf '**/*.%s\n' "$e"; done | sort)"
ca_paths_exact() { [ "$(ca_paths | sort)" = "$CA_EXPECTED" ]; }
check "clean-architecture: paths: が対象の 16 種の拡張子と過不足なく一致する" ca_paths_exact

# 6) workflow が Read させる SKILL.md は、導入先でも hve-playbook 自身でもルートから解決できる
read_paths() { grep -ohE 'Read [^ ]+/SKILL\.md' "$1"/hve-*.js | sed 's/^Read //' | sort -u; }
all_exist() {
    local root="$1" paths="$2" p
    [ -n "$paths" ] || return 1
    while IFS= read -r p; do
        case "$p" in /*|*..*) return 1 ;; esac   # ルートの外を指すパスは不合格
        [ -f "$root/$p" ] || return 1
    done <<<"$paths"
}
check "setup.sh: workflow の Read 先が導入先に実在する" all_exist "$T" "$(read_paths "$T/.claude/workflows")"
check "自リポ: workflow の Read 先が実在する" all_exist "$REPO_DIR" "$(read_paths "$REPO_DIR/workflows")"

# 7) プロジェクト固有の補足（hve-local）
check "setup.sh: local-overrides.md を配る" [ -f "$T/.claude/rules/hve/local-overrides.md" ]
check "setup.sh: 完了メッセージで hve-local を案内する" grep -q '\.claude/rules/hve-local/' "$TMP/setup.log"
check "setup.sh: hve-local は作らない" [ ! -e "$T/.claude/rules/hve-local" ]
mkdir -p "$T/.claude/rules/hve-local" && echo 'local note' >"$T/.claude/rules/hve-local/implement-flow.md"
PATH="$TMP/stub-bin:$PATH" bash "$REPO_DIR/setup.sh" "$T" >"$TMP/setup2.log" 2>&1
check "setup.sh 再実行 1 回目: exit 0" [ $? -eq 0 ]
PATH="$TMP/stub-bin:$PATH" bash "$REPO_DIR/setup.sh" "$T" >"$TMP/setup3.log" 2>&1
check "setup.sh 再実行 2 回目: exit 0" [ $? -eq 0 ]
check "setup.sh 再実行: hve-local の中身が残る" [ "$(cat "$T/.claude/rules/hve-local/implement-flow.md" 2>/dev/null)" = "local note" ]

# 8) knowledge 検査スクリプト（hve-scripts/ → .claude/scripts/hve/）
S="$T/.claude/scripts/hve"
runs_help() { "$REAL_PY" "$1" --help >/dev/null 2>&1; }
check "setup.sh: check-knowledge.py を配る" runs_help "$S/check-knowledge.py"
check "setup.sh: check-decision-log.py を配る" runs_help "$S/check-decision-log.py"
check "setup.sh: bump-distilled-sha.py を配る" runs_help "$S/bump-distilled-sha.py"
has_hooks() { [ -f "$S/hooks/session-stale-check.sh" ] && [ -f "$S/hooks/check-knowledge-impact.py" ]; }
check "setup.sh: hook を配る" has_hooks
check "setup.sh: 完了メッセージで .claude/scripts/hve/ を案内する" grep -q '\.claude/scripts/hve/' "$TMP/setup3.log"
echo stale >"$S/removed-upstream.py"
echo own >"$T/.claude/scripts/own.py"
PATH="$TMP/stub-bin:$PATH" bash "$REPO_DIR/setup.sh" "$T" >"$TMP/setup4.log" 2>&1
check "setup.sh 再実行: scripts/hve は置き直す（配布元に無いファイルは残らない）" [ ! -e "$S/removed-upstream.py" ]
check "setup.sh 再実行: scripts/hve の外の自作スクリプトには触れない" [ "$(cat "$T/.claude/scripts/own.py" 2>/dev/null)" = "own" ]

# 9) 著作権表示と許諾表示（LICENSE → .claude/LICENSE-hve-playbook）
L="$T/.claude/LICENSE-hve-playbook"
check "setup.sh: LICENSE の写しを配る（中身は LICENSE と同一）" cmp -s "$REPO_DIR/LICENSE" "$L"
echo tampered >"$L"
PATH="$TMP/stub-bin:$PATH" bash "$REPO_DIR/setup.sh" "$T" >"$TMP/setup5.log" 2>&1
check "setup.sh 再実行（LICENSE）: exit 0" [ $? -eq 0 ]
check "setup.sh 再実行: LICENSE の写しを最新の LICENSE に戻す" cmp -s "$REPO_DIR/LICENSE" "$L"
echo outside >"$TMP/outside.txt"
rm -f "$L" && ln -s "$TMP/outside.txt" "$L"
PATH="$TMP/stub-bin:$PATH" bash "$REPO_DIR/setup.sh" "$T" >"$TMP/setup6.log" 2>&1
check "setup.sh 再実行（LICENSE の symlink）: exit 0" [ $? -eq 0 ]
check "setup.sh 再実行: 写しの位置の symlink のリンク先を書き換えない" [ "$(cat "$TMP/outside.txt")" = "outside" ]
check "setup.sh 再実行: 写しの位置の symlink を実ファイルの写しに置き換える" sh -c '[ ! -L "$1" ] && cmp -s "$2" "$1"' _ "$L" "$REPO_DIR/LICENSE"

echo
echo "結果: PASS=$pass FAIL=$fail"
[ "$fail" -eq 0 ]
