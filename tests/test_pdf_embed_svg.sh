#!/bin/bash
# pdf skill の手順 2（SVG の Base64 埋め込み）の検査（Issue #99）
#
# 実行: bash tests/test_pdf_embed_svg.sh
# 前提: python3（無ければ SKIP）
#
# 検査すること:
#   - 同梱の embed-svg-to-md.py が、SVG の参照を data URI に置き換え、SVG 以外・存在しない SVG の参照は残す
#   - SKILL.md の手順 2・3 が、/tmp の固定パス（/tmp/embed-svg-to-md.py・/tmp/pdf-source.md）を使わない
#   - 手順 2 が mktemp -d で実行ごとの作業ディレクトリを作り、手順 3-1 がその中の出力を渡す
#   - 片付けは作業ディレクトリの中の出力と空のディレクトリだけを消し（rm -rf を使わない）、失敗したときも片付ける

set -u
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SKILL="$ROOT/skills/global/pdf/SKILL.md"
SCRIPT="$ROOT/skills/global/pdf/embed-svg-to-md.py"
pass=0
fail=0
check() {
    local name="$1"; shift
    if "$@"; then echo "[PASS] $name"; pass=$((pass + 1)); else echo "[FAIL] $name"; fail=$((fail + 1)); fi
}

# 1) SKILL.md の記述
lacks() { ! grep -qF -- "$1" "$SKILL"; }
check "SKILL.md: /tmp/embed-svg-to-md.py を使わない" lacks '/tmp/embed-svg-to-md.py'
check "SKILL.md: /tmp/pdf-source.md を使わない" lacks '/tmp/pdf-source.md'
check "SKILL.md: 同梱のスクリプトを呼ぶ" grep -qF 'python3 ~/.claude/skills/pdf/embed-svg-to-md.py' "$SKILL"
check "SKILL.md: システム配置のスクリプトへの読み替えがある" grep -qF '/etc/claude-defaults/skills/pdf/embed-svg-to-md.py' "$SKILL"
check "SKILL.md: mktemp -d で作業ディレクトリを作る（コマンドの行）" grep -qx 'mktemp -d' "$SKILL"
check "SKILL.md: 手順 3-1 が作業ディレクトリの出力を渡す" grep -qF 'その実行で作った `<作業ディレクトリ>/pdf-source.md` を渡す' "$SKILL"
check "SKILL.md: 片付けは作業ディレクトリの中の出力と空のディレクトリだけを消す" grep -qF 'rm -f "<作業ディレクトリ>/pdf-source.md" && rmdir "<作業ディレクトリ>"' "$SKILL"
check "SKILL.md: rm -rf で作業ディレクトリを消さない" lacks 'rm -rf "<作業ディレクトリ>"'
check "SKILL.md: 手順 2・3 が失敗したときも片付ける" grep -qF '手順 2・3 が失敗して止まったときも' "$SKILL"

# 2) スクリプトの動作
if ! command -v python3 >/dev/null 2>&1; then
    echo "SKIP: python3 が無いのでスクリプトの動作の検査を飛ばす"
else
    W="$(mktemp -d)"
    trap 'rm -rf "$W"' EXIT
    mkdir -p "$W/doc/img"
    printf '<svg xmlns="http://www.w3.org/2000/svg" width="1" height="1"/>' > "$W/doc/img/a.svg"
    printf 'png' > "$W/doc/img/b.png"
    cat > "$W/doc/in.md" <<'EOF'
# t
![図A](img/a.svg)
![図B](img/b.png)
![無い](img/missing.svg)
EOF
    b64="$(python3 -c 'import base64,sys;print(base64.b64encode(open(sys.argv[1],"rb").read()).decode())' "$W/doc/img/a.svg")"
    python3 "$SCRIPT" "$W/doc/in.md" "$W/out.md"
    rc=$?
    check "スクリプト: 終了コード 0" test "$rc" -eq 0
    check "スクリプト: 出力を書く" test -s "$W/out.md"
    check "スクリプト: SVG を data URI に置き換える" grep -qF "<img src=\"data:image/svg+xml;base64,$b64\" alt=\"図A\"" "$W/out.md"
    check "スクリプト: SVG 以外の画像はそのまま" grep -qF '![図B](img/b.png)' "$W/out.md"
    check "スクリプト: 存在しない SVG はそのまま" grep -qF '![無い](img/missing.svg)' "$W/out.md"
fi

echo
echo "passed: $pass, failed: $fail"
[ "$fail" -eq 0 ]
