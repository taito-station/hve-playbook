#!/bin/bash
# pdf skill の手順 2（SVG と相対パスの画像の Base64 埋め込み）の検査（Issue #99・#102・#112）
#
# 実行: bash tests/test_pdf_embed_svg.sh
# 前提: python3（無ければ SKIP）
#
# 検査すること:
#   - 同梱の embed-svg-to-md.py が、SVG と、入力の Markdown から辿れるローカルの画像（親ディレクトリを辿るもの・大文字の拡張子を含む）の参照を
#     data URI に置き換え、存在しないファイル・URL（http・data）・絶対パス・画像でないファイル・圧縮された画像（.svgz）の参照は残す
#     （#102: 出力を作業ディレクトリに置いても画像が壊れないため。data URI は置き換え前に判定し、長い参照で落ちない）
#   - タイトル付きの参照（"title"・'title'）はタイトルを外したパスで、%20 などはデコードしたパス（無ければデコード前のパス）で探す。
#     デコードで初めて現れる / や ..（..%2F・%2E%2E）と NUL（%00）の候補は読まない（#112）
#   - alt の `"` を属性の中でエスケープする
#   - SKILL.md の手順 2 が、SVG 以外のローカルの画像も埋め込むことと、外部から受け取った Markdown の参照先を確かめることを書いてある
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
check "SKILL.md: 手順 2 は SVG 以外のローカルの画像も埋め込む" grep -qF 'SVG だけでなく、入力の Markdown から辿れるローカルのファイルのうち、拡張子から画像と判定できるもの（PNG・JPEG など）を data URI にする' "$SKILL"
check "SKILL.md: 手順 2 の出力は作業ディレクトリに置いても画像が壊れない" grep -qF '作業ディレクトリに置いても相対パスの画像が壊れない' "$SKILL"
check "SKILL.md: 手順 2 が残す参照を列挙している" grep -qF 'URL・絶対パス・存在しないファイル・画像と判定できない拡張子の参照と、`<img>` の HTML、括弧で書いたタイトル（`![alt](path (title))`）と山括弧で囲んだパス（`![alt](<path>)`）の参照はそのまま残る' "$SKILL"
check "SKILL.md: デコードで初めて現れる / や .. は辿らない（#112）" grep -qF 'デコードで初めて現れる `/` や `..`（`..%2F`・`%2E%2E%2F` など）は辿らない' "$SKILL"
check "SKILL.md: タイトル付きの参照はタイトルを外して探す（#112）" grep -qF 'タイトル付きの参照（`![alt](path "title")`）はタイトルを外したパスを、`%20` などのパーセントエンコードはデコードしたパスを探す' "$SKILL"
check "SKILL.md: タイトル付きの参照を「残る参照」に挙げない（#112）" lacks 'の参照と、タイトル付きの参照'
check "SKILL.md: 外部から受け取った Markdown は参照先を確かめる" grep -qF '外部から受け取った Markdown は参照先を確かめてから使う' "$SKILL"
check "SKILL.md: 手順 3-1 の --basedir は手順 2 が残した参照にだけ効く" grep -qF '手順 2 を通ったときは画像が埋め込み済みなので、手順 2 が残した参照にだけ効く' "$SKILL"

# 2) スクリプトの動作
if ! command -v python3 >/dev/null 2>&1; then
    echo "SKIP: python3 が無いのでスクリプトの動作の検査を飛ばす"
else
    W="$(mktemp -d)"
    trap 'rm -rf "$W"' EXIT
    mkdir -p "$W/doc/img" "$W/doc/files" "$W/images"
    printf '<svg xmlns="http://www.w3.org/2000/svg" width="1" height="1"/>' > "$W/doc/img/a.svg"
    printf 'png' > "$W/doc/img/b.png"
    printf 'jpeg' > "$W/images/c.jpg"
    printf 'text' > "$W/doc/files/d.txt"
    printf 'upper' > "$W/doc/img/U.PNG"
    printf 'gzip' > "$W/doc/img/z.svgz"
    printf 'space' > "$W/doc/img/my image.png"
    printf 'lit' > "$W/doc/img/lit%20name.png"
    printf 'dec' > "$W/doc/img/both name.png"
    printf 'raw' > "$W/doc/img/both%20name.png"
    mkdir -p "$W/outside"
    printf 'secret' > "$W/outside/s.png"
    # 期待値の base64 は実装と独立に固定する（png=cG5n, jpeg=anBlZw==, upper=dXBwZXI=, space=c3BhY2U=, lit=bGl0, dec=ZGVj）
    long_data="data:image/png;base64,$(printf 'A%.0s' $(seq 1 3000))"
    cat > "$W/doc/in.md" <<EOF
# t
![図A](img/a.svg)
![図B](img/b.png)
![図C](../images/c.jpg)
![図D](img/U.PNG)
![引用 "x"](img/b.png)
![無い](img/missing.svg)
![無いPNG](img/missing.png)
![遠い](https://example.com/e.png)
![埋め込み済み]($long_data)
![絶対]($W/images/c.jpg)
![添付](files/d.txt)
![圧縮](img/z.svgz)
![題1](img/b.png "タイトル")
![題2](img/b.png 'single')
![空白](img/my%20image.png)
![生](img/lit%20name.png)
![素の空白](img/my image.png)
![題無し](img/missing.png "t")
![符号化した絶対](%2F${W#/}/images/c.jpg)
![題3](img/a.svg "図 1")
![題4](img/my image.png "t")
![両方](img/both%20name.png)
![NUL](img/a%00.png)
![隠した親1](..%2Foutside%2Fs.png)
![隠した親2](%2E%2E/outside/s.png)
EOF
    b64_svg="$(python3 -c 'import base64,sys;print(base64.b64encode(open(sys.argv[1],"rb").read()).decode())' "$W/doc/img/a.svg")"
    python3 "$SCRIPT" "$W/doc/in.md" "$W/out.md"
    rc=$?
    check "スクリプト: 終了コード 0" test "$rc" -eq 0
    check "スクリプト: 出力を書く" test -s "$W/out.md"
    check "スクリプト: SVG を data URI に置き換える" grep -qF "<img src=\"data:image/svg+xml;base64,$b64_svg\" alt=\"図A\"" "$W/out.md"
    check "スクリプト: PNG も data URI に置き換える" grep -qF '<img src="data:image/png;base64,cG5n" alt="図B"' "$W/out.md"
    check "スクリプト: 親ディレクトリを辿る画像も data URI に置き換える" grep -qF '<img src="data:image/jpeg;base64,anBlZw==" alt="図C"' "$W/out.md"
    check "スクリプト: 大文字の拡張子も data URI に置き換える" grep -qF '<img src="data:image/png;base64,dXBwZXI=" alt="図D"' "$W/out.md"
    check "スクリプト: alt の \" をエスケープする" grep -qF '<img src="data:image/png;base64,cG5n" alt="引用 &quot;x&quot;"' "$W/out.md"
    check "スクリプト: 出力にファイルで参照する画像が残らない" bash -c '! grep -qE "^!\[(図A|図B|図C|図D|引用)" "$1"' _ "$W/out.md"
    check "スクリプト: 存在しない SVG はそのまま" grep -qF '![無い](img/missing.svg)' "$W/out.md"
    check "スクリプト: 存在しない PNG はそのまま" grep -qF '![無いPNG](img/missing.png)' "$W/out.md"
    check "スクリプト: URL の画像はそのまま" grep -qF '![遠い](https://example.com/e.png)' "$W/out.md"
    check "スクリプト: 埋め込み済みの data URI はそのまま（長くても落ちない）" grep -qF "![埋め込み済み]($long_data)" "$W/out.md"
    check "スクリプト: 絶対パスの画像はそのまま" grep -qF "![絶対]($W/images/c.jpg)" "$W/out.md"
    check "スクリプト: 画像でないファイルはそのまま" grep -qF '![添付](files/d.txt)' "$W/out.md"
    check "スクリプト: 圧縮された画像（.svgz）はそのまま" grep -qF '![圧縮](img/z.svgz)' "$W/out.md"
    check "スクリプト: \"title\" 付きの参照もタイトルを外して置き換える（#112）" grep -qF '<img src="data:image/png;base64,cG5n" alt="題1"' "$W/out.md"
    check "スクリプト: 'title' 付きの参照もタイトルを外して置き換える（#112）" grep -qF '<img src="data:image/png;base64,cG5n" alt="題2"' "$W/out.md"
    check "スクリプト: %20 を含むパスはデコードして置き換える（#112）" grep -qF '<img src="data:image/png;base64,c3BhY2U=" alt="空白"' "$W/out.md"
    check "スクリプト: デコードした名前が無ければデコード前の名前で置き換える（#112）" grep -qF '<img src="data:image/png;base64,bGl0" alt="生"' "$W/out.md"
    check "スクリプト: タイトルの無い空白入りのパスは従来どおり置き換える" grep -qF '<img src="data:image/png;base64,c3BhY2U=" alt="素の空白"' "$W/out.md"
    check "スクリプト: タイトル付きでも存在しないファイルはそのまま" grep -qF '![題無し](img/missing.png "t")' "$W/out.md"
    check "スクリプト: デコードで絶対パスになる参照（%2F で始まる）はそのまま" grep -qF "![符号化した絶対](%2F${W#/}/images/c.jpg)" "$W/out.md"
    check "スクリプト: SVG のタイトルの中に空白がある参照も置き換える（#112 の成功条件の例）" grep -qF "<img src=\"data:image/svg+xml;base64,$b64_svg\" alt=\"題3\"" "$W/out.md"
    check "スクリプト: 空白入りのパスにタイトルが付く参照も置き換える" grep -qF '<img src="data:image/png;base64,c3BhY2U=" alt="題4"' "$W/out.md"
    check "スクリプト: デコード後とデコード前の両方の名前があればデコード後を使う" grep -qF '<img src="data:image/png;base64,ZGVj" alt="両方"' "$W/out.md"
    check "スクリプト: %00 を含む参照はそのまま（落ちない）" grep -qF '![NUL](img/a%00.png)' "$W/out.md"
    check "スクリプト: エンコードで隠した親ディレクトリ（..%2F）は辿らない" grep -qF '![隠した親1](..%2Foutside%2Fs.png)' "$W/out.md"
    check "スクリプト: エンコードで隠した親ディレクトリ（%2E%2E）は辿らない" grep -qF '![隠した親2](%2E%2E/outside/s.png)' "$W/out.md"
fi

echo
echo "passed: $pass, failed: $fail"
[ "$fail" -eq 0 ]
