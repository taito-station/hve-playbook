#!/usr/bin/env python3
import base64, html, mimetypes, re, sys
from pathlib import Path
from urllib.parse import unquote, urlsplit

# 括弧の中身の末尾にタイトル（"title" か 'title'）があれば、group(1) がタイトルを外したパス。
# タイトルが無ければ中身全体をパスとして扱う。(.*\S) は長い空白の並びで後戻りが増えない形にしている
TITLE = re.compile(r'^(.*\S)\s+(?:"[^"]*"|\'[^\']*\')\s*$')


def hides_path_parts(raw, decoded):
    """デコードで初めて現れる区切り（/）・親ディレクトリ（..）・NUL を持つ候補か。

    見えるとおりの ../ は辿るが、..%2F や %2E%2E%2F のようにエンコードで隠した参照は読まない（Issue #112）。
    %2F で始まる参照がデコードで絶対パスになるのも、区切りが増えるのでここで防ぐ。
    """
    if '\x00' in decoded or decoded.count('/') != raw.count('/'):
        return True
    return any(d == '..' and r != '..' for r, d in zip(raw.split('/'), decoded.split('/')))


def main():
    md_path = Path(sys.argv[1])
    output_path = Path(sys.argv[2])
    md_dir = md_path.parent
    content = md_path.read_text(encoding='utf-8')

    # 入力の Markdown から辿れるローカルの画像（SVG・PNG・JPEG など）を data URI にする。
    # 出力は作業ディレクトリに置くので、ファイルで参照したままだと md-to-pdf が相対パスを解決できない（Issue #102）。
    # タイトル付きの参照はタイトルを外したパスを、%20 などはデコードしたパス（無ければデコード前のパス）を探す（Issue #112）。
    # URL（http・data など）・絶対パス・画像と判定できない拡張子・存在しないファイルの参照はそのまま残す。
    def replace_image(match):
        alt, src = match.group(1), match.group(2).strip()
        titled = TITLE.match(src)
        if titled:
            src = titled.group(1)
        if urlsplit(src).scheme or Path(src).is_absolute():
            return match.group(0)
        mime, encoding = mimetypes.guess_type(src)
        if not mime or not mime.startswith('image/') or encoding:
            return match.group(0)
        data = None
        for candidate in dict.fromkeys((unquote(src), src)):
            if candidate != src and hides_path_parts(src, candidate):
                continue
            try:
                img_path = (md_dir / candidate).resolve()
                if img_path.is_file():
                    data = img_path.read_bytes()
                    break
            except (OSError, ValueError):  # ValueError: パスに NUL が含まれるとき
                continue
        if data is None:
            return match.group(0)
        b64 = base64.b64encode(data).decode('ascii')
        return f'<img src="data:{mime};base64,{b64}" alt="{html.escape(alt, quote=True)}" style="max-width:100%"/>'

    content = re.sub(r'!\[([^\]]*)\]\(([^)]+)\)', replace_image, content)
    output_path.write_text(content, encoding='utf-8')

if __name__ == '__main__':
    main()
