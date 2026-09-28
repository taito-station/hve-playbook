#!/usr/bin/env bash
# sync-dotclaude.sh — dotclaude リポの内容を ~/.claude へ冪等に反映する。
#
# なぜ必要か:
#   CLAUDE.md / statusline.sh は「ファイル単位の symlink」なので
#   git pull だけで中身が追従する。settings.json はリポ版と settings.machine.json
#   （マシン固有の設定）をマージして生成する（外部ツールの書き込みがリポに伝播しないように）。
#   しかし skills / hooks / rules / agents は「項目ごとの symlink」で
#   デプロイしており、リポに *新規追加* された skill・hook・rule・agent は pull しても
#   ~/.claude 側に symlink が張られない（＝取りこぼす）。
#   rules / agents は user-level 用の rules/global/・agents/global/ だけを対象にする
#   （rules/hve・agents/hve-* は setup.sh が導入先プロジェクトにコピーする project-level 資産）。
#   特に settings.json が参照する hook の実体ファイルが無い状態になると、
#   その hook が発火する全 tool がブロックされる。
#
# このスクリプトは pull 後に実行して以下を保証する（何度実行しても安全）:
#   1. skills/global/*・hooks/*・rules/global/*・agents/global/* の不足 symlink を張る
#   2. CLAUDE.md / statusline.sh の symlink を保証（新規セットアップ兼用）
#   3. リポから消えた skill/hook/script/rule/agent を指す dangling symlink を検知（--prune で除去）
#   4. 生成した settings.json が参照する hook が全て実在するか検証し、実在するときだけ配置する
#      （全 tool ブロック事故の防止）。前回配置後に settings.json が直接編集されていたら退避する
#
# 使い方:
#   ./sync-dotclaude.sh           # 同期＋検証（安全な既定）
#   ./sync-dotclaude.sh --prune   # 併せて dangling symlink を除去
#
# 環境変数:
#   CLAUDE_HOME  デプロイ先（既定: ~/.claude）
#
# 終了コード:
#   0   正常（不足リンク作成含む。警告・欠落なし）
#   1   FATAL: settings.json の "command" が参照する hook が実在しない、または settings.json の生成失敗
#       （要即対応。いずれも配置済みの settings.json は変更しない。symlink の同期と検査は行う）
#   2   要手動確認: dangling symlink 残置、同名実体の居座りスキップ、settings.json 直接編集の退避、
#       または読まれない ~/.claude/settings.local.json に hooks / permissions が残っている
#   64  引数エラー（未知フラグ）
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CLAUDE_DIR="${CLAUDE_HOME:-$HOME/.claude}"

PRUNE=0
for arg in "$@"; do
  case "$arg" in
    --prune) PRUNE=1 ;;
    *) echo "不明な引数: $arg (使用可能: --prune)" >&2; exit 64 ;;
  esac
done

linked=0; okcnt=0; fixed=0; warncnt=0; pruned=0

mkdir -p "$CLAUDE_DIR/hooks" "$CLAUDE_DIR/skills" "$CLAUDE_DIR/rules" "$CLAUDE_DIR/agents"

# link_one <target-symlink> <source-in-repo>
# 既存が正しい symlink なら何もしない。別 symlink なら張り直す。
# 実ディレクトリ/実ファイルが居座っている場合はネスト事故を避けてスキップ＋警告。
link_one() {
  local link="$1" src="$2"
  if [ -L "$link" ]; then
    if [ "$(readlink "$link")" = "$src" ]; then
      okcnt=$((okcnt + 1)); return
    fi
    ln -sfn "$src" "$link"
    echo "  fix    : $(basename "$link")  (別リンクから張り直し)"
    fixed=$((fixed + 1)); return
  fi
  if [ -e "$link" ]; then
    echo "  WARN   : $link は実体（symlink でない）。ネスト回避のためスキップ。手動確認が必要"
    warncnt=$((warncnt + 1)); return
  fi
  ln -s "$src" "$link"
  echo "  link   : $(basename "$link")"
  linked=$((linked + 1))
}

echo "==> dotclaude 同期: $REPO_DIR -> $CLAUDE_DIR"

# 1) トップレベルの単体ファイル（新規セットアップ時のみ実効、既存はほぼ ok）
echo "-- top-level files"
link_one "$CLAUDE_DIR/CLAUDE.md"     "$REPO_DIR/CLAUDE.md"
link_one "$CLAUDE_DIR/statusline.sh" "$REPO_DIR/statusline.sh"

# settings.json は「リポ版 + マシン固有 overlay」をマージした生成物として配置する
# （symlink だと外部ツールの書き込みがリポに伝播するため）。
# マシン固有の設定は settings.machine.json に置く。user レベルの settings.local.json は
# Claude Code に読まれないため置き場所にならない（v2.1.282 で実測）。
# ここでは生成だけ行い、配置は hook の実在検査を通った後（末尾）で行う。
SETTINGS="$CLAUDE_DIR/settings.json"
OVERLAY="$CLAUDE_DIR/settings.machine.json"
SNAPSHOT="$CLAUDE_DIR/.settings.generated.json"   # 前回配置した生成版（直接編集の検知用）

# settings_py merge <repo> <overlay> <out> | changed-keys <old> <new> | same <a> <b>
settings_py() {
  python3 - "$@" <<'PYHELPER'
import json, os, sys

def merge(base, over, path):
    # dict は再帰マージ、list はリポ版に無い要素を追記、スカラーは overlay 優先。
    # dict / list を別の型で上書きするとリポ版の hook や permissions が丸ごと消えるため拒否する
    if isinstance(base, dict) or isinstance(base, list):
        if type(over) is not type(base):
            sys.exit(f"settings.machine.json の {path or '(トップレベル)'} は "
                     f"{type(base).__name__} であるべきところ {type(over).__name__} になっている")
    if isinstance(base, dict):
        out = dict(base)
        for k, v in over.items():
            out[k] = merge(base[k], v, f"{path}.{k}" if path else k) if k in base else v
        return out
    if isinstance(base, list):
        return base + [x for x in over if x not in base]
    return over

def load(path, label):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError) as e:
        sys.exit(f"{label} を読み込めない: {path}: {e}")

def load_or_none(path):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None

cmd = sys.argv[1]
if cmd == "merge":
    repo_path, overlay_path, out_path = sys.argv[2:5]
    data = load(repo_path, "リポの settings.json")
    if os.path.exists(overlay_path):
        overlay = load(overlay_path, "settings.machine.json")
        if not isinstance(overlay, dict):
            sys.exit("settings.machine.json のトップレベルは object であるべき")
        data = merge(data, overlay, "")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")
elif cmd == "changed-keys":
    # 2 ファイルで値が異なるトップレベルキーを列挙する（片方が JSON として読めなければ "(全体)"）
    old, new = load_or_none(sys.argv[2]), load_or_none(sys.argv[3])
    if not (isinstance(old, dict) and isinstance(new, dict)):
        print("(全体)")
        sys.exit(0)
    for k in sorted(set(old) | set(new)):
        if old.get(k) != new.get(k):
            print(k)
elif cmd == "same":
    # 2 ファイルが JSON として同じ値か（書式・キー順の違いは無視。読めなければ違うとみなす）
    a, b = load_or_none(sys.argv[2]), load_or_none(sys.argv[3])
    sys.exit(0 if a is not None and a == b else 1)
PYHELPER
}

# 生成に失敗しても symlink の同期と検査は続け、settings.json の配置だけを止めて最後に exit 1 する
generated="$(mktemp)"
tmpfiles=("$generated")
trap 'rm -f "${tmpfiles[@]}"' EXIT
gen_failed=0
if ! command -v python3 >/dev/null 2>&1; then
  echo "  FATAL  : python3 が見つからない（settings.json の生成に必要）。settings.json は変更しない" >&2
  gen_failed=1
elif ! settings_py merge "$REPO_DIR/settings.json" "$OVERLAY" "$generated"; then
  echo "  FATAL  : settings.json の生成に失敗（上のメッセージ参照）。settings.json は変更しない" >&2
  gen_failed=1
fi

# 2) hooks（*.py / *.sh を項目ごとに symlink。既存デプロイと同じく末尾スラッシュ無し）
echo "-- hooks"
for f in "$REPO_DIR"/hooks/*.py "$REPO_DIR"/hooks/*.sh; do
  [ -e "$f" ] || continue
  link_one "$CLAUDE_DIR/hooks/$(basename "$f")" "$f"
done

# 3) global skills（既存デプロイに合わせ末尾スラッシュ付きでリンク）
echo "-- skills/global"
for d in "$REPO_DIR"/skills/global/*/; do
  [ -d "$d" ] || continue
  name="$(basename "$d")"
  link_one "$CLAUDE_DIR/skills/$name" "$d"
done

# 4) scripts（*.py / *.sh を項目ごとに symlink）
echo "-- scripts"
if [ -d "$REPO_DIR/scripts" ]; then
  mkdir -p "$CLAUDE_DIR/scripts"
  for f in "$REPO_DIR"/scripts/*.py "$REPO_DIR"/scripts/*.sh; do
    [ -e "$f" ] || continue
    link_one "$CLAUDE_DIR/scripts/$(basename "$f")" "$f"
  done
fi

# 4b) user-level rules（カテゴリ単位で symlink。skills と同じく末尾スラッシュ付き）
echo "-- rules/global"
for d in "$REPO_DIR"/rules/global/*/; do
  [ -d "$d" ] || continue
  link_one "$CLAUDE_DIR/rules/$(basename "$d")" "$d"
done

# 4c) user-level agents（*.md を項目ごとに symlink）
echo "-- agents/global"
for f in "$REPO_DIR"/agents/global/*.md; do
  [ -e "$f" ] || continue
  link_one "$CLAUDE_DIR/agents/$(basename "$f")" "$f"
done

# 5) dangling 検知（リポから消えた skill/hook/script/rule/agent を指す壊れリンク）
echo "-- dangling リンク検査"
for dir in "$CLAUDE_DIR/hooks" "$CLAUDE_DIR/skills" "$CLAUDE_DIR/scripts" "$CLAUDE_DIR/rules" "$CLAUDE_DIR/agents"; do
  for l in "$dir"/*; do
    [ -L "$l" ] || continue
    tgt="$(readlink "$l")"
    case "$tgt" in
      "$REPO_DIR"/*) ;;    # このリポ由来のみ対象
      *) continue ;;
    esac
    if [ ! -e "$l" ]; then
      if [ "$PRUNE" -eq 1 ]; then
        rm "$l"; echo "  prune  : $(basename "$l")  (リポから消えたため除去)"
        pruned=$((pruned + 1))
      else
        echo "  DANGLE : $(basename "$l") -> $tgt  (リポに実体無し。--prune で除去可)"
        warncnt=$((warncnt + 1))
      fi
    fi
  done
done

# 6) 致命チェック: 生成した settings.json が参照する hook が全て実在するか
echo "-- settings 参照 hook の実在検査"
missing_hook=0
# hook として発火するのは "command" 行のみ。permissions の allow 文字列
# (例: "Bash(~/.claude/hooks/xxx:*)") は tool ブロックに無関係なので対象外にする。
# 対象は .claude/hooks/ を含む参照。~ / $HOME / ${HOME} / "$HOME" / 展開済みの $HOME を @HOME@ に
# 正規化してから拾い、~/.claude/hooks/ 直下は $CLAUDE_DIR/hooks/ で、それ以外は参照先そのもので実在を確かめる。
# 他の変数（$CLAUDE_PROJECT_DIR 等）で始まるパスはここでは解決できないので対象外にし、
# 絶対パスは語の先頭（行頭・空白・" ・= の直後）から始まるものだけを拾う（相対パスの途中を拾わない）。
check_hook_refs() {
  local label="$1" file="$2"
  local refs
  refs="$(grep -E '"command"' "$file" 2>/dev/null \
    | sed -E 's#\\"\$\{?(CLAUDE_)?HOME\}?\\"#@HOME@#g; s#\$\{?(CLAUDE_)?HOME\}?#@HOME@#g; s#(^|[" =])~/#\1@HOME@/#g' \
    | awk -v h="$HOME/" '{ while ((i = index($0, h)) > 0) $0 = substr($0, 1, i - 1) "@HOME@/" substr($0, i + length(h)); print }' \
    | sed -E 's#(\\")?\$\{?[A-Za-z_][A-Za-z0-9_]*\}?(\\")?/[^" \\]*##g' \
    | grep -oE '(^|[ "=])(@HOME@)?/[^" \\@]*\.claude/hooks/[A-Za-z0-9._-]+' | sed -E 's#^[ "=]##' | sort -u || true)"
  [ -n "$refs" ] || return 0
  while IFS= read -r ref; do
    [ -n "$ref" ] || continue
    local name target
    name="$(basename "$ref")"
    case "$ref" in
      "@HOME@/.claude/hooks/"*) target="$CLAUDE_DIR/hooks/$name" ;;
      "@HOME@/"*) target="$HOME/${ref#@HOME@/}" ;;
      *) target="$ref" ;;
    esac
    if [ ! -e "$target" ]; then
      echo "  FATAL  : $label が参照する hook が実在しない: $name ($target)  (この hook 発火 tool が全ブロックされる)"
      missing_hook=$((missing_hook + 1))
    fi
  done <<HOOKEOF
$refs
HOOKEOF
}
if [ "$gen_failed" -eq 0 ]; then
  # 生成版はリポ版と settings.machine.json の両方の参照を含む
  check_hook_refs "settings.json" "$generated"
elif [ -f "$SETTINGS" ]; then
  # 生成できないときは、配置済みのまま残る settings.json の参照が壊れていないかを検査する
  check_hook_refs "配置済み settings.json" "$SETTINGS"
fi

# 7) settings.json の配置（hook が全て実在するときだけ）
echo "-- settings.json"
# 同じディレクトリの一時ファイルから mv して、読み手に書きかけの JSON を見せない
install_file() {  # <src> <dest>
  local tmp
  tmp="$(mktemp "$2.tmp.XXXXXX")"
  tmpfiles+=("$tmp")
  cp "$1" "$tmp"
  chmod 644 "$tmp"   # mktemp の 600 を引き継がず、従来の cp 配置と同じモードにする
  mv -f "$tmp" "$2"
}
if [ "$gen_failed" -ne 0 ]; then
  echo "  skip   : settings.json  (生成に失敗したため配置しない)"
elif [ "$missing_hook" -gt 0 ]; then
  echo "  skip   : settings.json  (参照 hook が欠落しているため配置しない)"
elif [ ! -L "$SETTINGS" ] && [ -f "$SETTINGS" ] && cmp -s "$generated" "$SETTINGS"; then
  okcnt=$((okcnt + 1))
else
  if [ -L "$SETTINGS" ]; then
    rm "$SETTINGS"
    echo "  migrate: settings.json  (symlink → 生成ファイルに移行)"
  elif [ -f "$SETTINGS" ] && ! settings_py same "$SNAPSHOT" "$SETTINGS" \
    && ! settings_py same "$generated" "$SETTINGS"; then
    # 前回配置した生成版と JSON として違う = 外部ツールや UI による直接編集。上書き前に退避する
    # （前回配置の記録が無い初回も、何が失われるか分からないので退避する。
    #   書式だけの違い・生成版と同じ値への変化は退避しない）
    latest_backup="$(ls -1 "$SETTINGS".bak-* 2>/dev/null | tail -1 || true)"
    if [ -n "$latest_backup" ] && cmp -s "$latest_backup" "$SETTINGS"; then
      backup="$latest_backup"   # 同じ内容の退避が既にある（書き戻し続けるツール等）
    else
      # mktemp で作る（600・同じ秒の退避でも別名になる）
      backup="$(mktemp "$SETTINGS.bak-$(date +%Y%m%d-%H%M%S)-XXXX")"
      cp "$SETTINGS" "$backup"
    fi
    if [ -f "$SNAPSHOT" ]; then
      keys="$(settings_py changed-keys "$SNAPSHOT" "$SETTINGS" | paste -sd ' ' -)"
      echo "  WARN   : settings.json が前回の同期後に直接編集されていた（変更キー: ${keys:-不明}）。$backup に退避"
    else
      echo "  WARN   : settings.json の前回配置の記録が無いため、上書き前に $backup に退避"
    fi
    echo "           残す設定は settings.machine.json に書くこと（settings.json は同期のたびに再生成される）"
    warncnt=$((warncnt + 1))
  fi
  install_file "$generated" "$SETTINGS"
  echo "  update : settings.json  (リポ版 + settings.machine.json で生成)"
  fixed=$((fixed + 1))
fi
if [ "$gen_failed" -eq 0 ] && [ "$missing_hook" -eq 0 ]; then
  install_file "$generated" "$SNAPSHOT"
fi

# user レベルの settings.local.json は読まれない。hooks / permissions が残っていれば移行を促す
if [ -f "$CLAUDE_DIR/settings.local.json" ] \
  && grep -qE '"(hooks|permissions)"' "$CLAUDE_DIR/settings.local.json"; then
  echo "  WARN   : $CLAUDE_DIR/settings.local.json の hooks / permissions は Claude Code に読まれない。"
  echo "           有効にするなら、一度も効いていなかった allow / hook を見直してから settings.machine.json に移すこと"
  warncnt=$((warncnt + 1))
fi

echo
echo "==> 完了: link=$linked fix=$fixed ok=$okcnt warn=$warncnt prune=$pruned"
if [ "$gen_failed" -ne 0 ]; then
  echo "!! settings.json を生成できなかったため配置していない。上の FATAL を確認してください。" >&2
  exit 1
fi
if [ "$missing_hook" -gt 0 ]; then
  echo "!! settings 参照 hook が $missing_hook 件欠落。hooks/ にファイルが存在するか確認してください。" >&2
  exit 1
fi
if [ "$warncnt" -gt 0 ]; then
  exit 2
fi
