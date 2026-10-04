#!/bin/bash
# sync-dotclaude.sh の rules / agents 同期と、setup.sh が global 配下を配らないことの検査
#
# 実行: bash tests/test_sync_rules_agents.sh
#
#   - rules/global/<category>/ → ~/.claude/rules/<category> をカテゴリ単位で symlink
#   - agents/global/*.md → ~/.claude/agents/<name>.md をファイル単位で symlink
#   - 同名の実体が居座る場合はスキップ + WARN (exit 2)
#   - このリポジトリ由来で実体が消えた rules / agents の symlink を dangling として検出（--prune で除去）
#   - 実体を退避したあと再同期すると symlink になり exit 0（既存環境の一度きりの移行）
#   - このリポジトリ自身の .claude/rules は rules/hve だけ、.claude/agents は agents/hve-*.md だけを指す
#     （global 配下を project-level で重ねて読ませない。サブディレクトリの agent も読み込まれるため）
#   - setup.sh は rules/global・agents/global・global skill を導入先にコピーしない
#     （cq/mdq の導入分岐に入らないよう、python3 をスタブにして実行する）
#   - workflows/hve-*.js が Read させる SKILL.md は、導入先でも自リポでもルートから解決できる

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
check "自リポ: .claude/rules 直下は hve だけ" [ "$(ls -A "$REPO_DIR/.claude/rules")" = "hve" ]
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

echo
echo "結果: PASS=$pass FAIL=$fail"
[ "$fail" -eq 0 ]
