#!/usr/bin/env bash
set -eu
shopt -s nullglob

usage() {
    echo "使い方: bash setup.sh /path/to/my-project"
    echo ""
    echo "hve-playbook の内容を対象プロジェクトの .claude/ に配置します。"
}

if [ "$#" -lt 1 ]; then
    usage
    exit 1
fi

TARGET="$1"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"

if [ ! -d "$TARGET" ]; then
    echo "[ERROR] ターゲットディレクトリが存在しません: $TARGET"
    exit 1
fi

if [ "$(cd "$TARGET" && pwd -P)" = "$SCRIPT_DIR" ]; then
    echo "[ERROR] hve-playbook 自身をターゲットにすることはできません"
    exit 1
fi

TARGET_CLAUDE="$TARGET/.claude"
mkdir -p "$TARGET_CLAUDE"

echo "[INFO] $TARGET_CLAUDE に hve-playbook を配置します"

# rules/hve/
mkdir -p "$TARGET_CLAUDE/rules"
rm -rf "$TARGET_CLAUDE/rules/hve"
cp -r "$SCRIPT_DIR/rules/hve" "$TARGET_CLAUDE/rules/hve"
echo "[INFO] rules/hve/ を配置しました"

# skills/hve-*/
mkdir -p "$TARGET_CLAUDE/skills"
skills=("$SCRIPT_DIR"/skills/hve-*/)
if [ ${#skills[@]} -gt 0 ]; then
    for dir in "${skills[@]}"; do
        name="$(basename "$dir")"
        rm -rf "$TARGET_CLAUDE/skills/$name"
        cp -r "$dir" "$TARGET_CLAUDE/skills/$name"
    done
    echo "[INFO] skills/hve-*/ を配置しました"
fi

# agents/hve-*.md
mkdir -p "$TARGET_CLAUDE/agents"
rm -f "$TARGET_CLAUDE"/agents/hve-*.md
agents=("$SCRIPT_DIR"/agents/hve-*.md)
if [ ${#agents[@]} -gt 0 ]; then
    for file in "${agents[@]}"; do
        cp "$file" "$TARGET_CLAUDE/agents/"
    done
    echo "[INFO] agents/hve-*.md を配置しました"
fi

# workflows/hve-*.js
mkdir -p "$TARGET_CLAUDE/workflows"
rm -f "$TARGET_CLAUDE"/workflows/hve-*.js
workflows=("$SCRIPT_DIR"/workflows/hve-*.js)
if [ ${#workflows[@]} -gt 0 ]; then
    for file in "${workflows[@]}"; do
        cp "$file" "$TARGET_CLAUDE/workflows/"
    done
    echo "[INFO] workflows/hve-*.js を配置しました"
fi

# CLAUDE.hve.md（HVE 方法論の説明）
if [ ! -f "$TARGET_CLAUDE/CLAUDE.md" ]; then
    cp "$SCRIPT_DIR/CLAUDE.hve.md" "$TARGET_CLAUDE/CLAUDE.md"
    echo "[INFO] CLAUDE.md を配置しました（HVE 方法論）"
elif [ ! -f "$TARGET_CLAUDE/CLAUDE.hve.md" ]; then
    cp "$SCRIPT_DIR/CLAUDE.hve.md" "$TARGET_CLAUDE/CLAUDE.hve.md"
    echo "[WARN] $TARGET_CLAUDE/CLAUDE.md が既に存在するため、HVE 方法論は"
    echo "       $TARGET_CLAUDE/CLAUDE.hve.md として配置しました。"
    echo "       内容を確認し、既存の CLAUDE.md へ手動でマージしてください。"
else
    cp "$SCRIPT_DIR/CLAUDE.hve.md" "$TARGET_CLAUDE/CLAUDE.hve.md"
    echo "[INFO] CLAUDE.hve.md を最新版で更新しました。"
    echo "       既存の CLAUDE.md との差分を確認し、必要に応じてマージしてください。"
fi

# docs/
mkdir -p "$TARGET/docs"
echo "[INFO] docs/ を確保しました"

# cq/mdq の自動インストール
if python3 -m cq --help >/dev/null 2>&1 && python3 -m mdq --help >/dev/null 2>&1; then
    echo "[INFO] cq/mdq はインストール済みです"
else
    echo "[INFO] cq/mdq をインストールします..."
    if [ -n "${HVE_REPO_PATH:-}" ] && [ ! -d "$HVE_REPO_PATH" ]; then
        echo "[WARN] HVE_REPO_PATH が存在しません: $HVE_REPO_PATH（無視して自動探索します）"
        HVE_DIR="$SCRIPT_DIR/../HypervelocityEngineering"
    else
        HVE_DIR="${HVE_REPO_PATH:-$SCRIPT_DIR/../HypervelocityEngineering}"
    fi
    if [ ! -d "$HVE_DIR" ]; then
        echo "[INFO] HypervelocityEngineering をクローンします: $HVE_DIR"
        git clone https://github.com/dahatake/HypervelocityEngineering.git "$HVE_DIR" || {
            echo "[WARN] クローンに失敗しました。cq/mdq なしで続行します"
            rm -rf "$HVE_DIR"
        }
    fi
    if [ -d "$HVE_DIR" ]; then
        python3 -m pip install -e "$HVE_DIR[code,mdq]" || {
            echo "[WARN] cq/mdq のインストールに失敗しました。grep/find にフォールバックします"
        }
    fi
fi

echo ""
echo "[DONE] セットアップが完了しました。"
echo "次のアクション: Claude Code セッション内で /hve-ard を実行し、要件定義を開始してください。"
