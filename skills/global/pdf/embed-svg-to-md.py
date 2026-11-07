#!/usr/bin/env python3
import base64, html, mimetypes, re, sys
from pathlib import Path
from urllib.parse import unquote, urlsplit

# 括弧の中身の末尾のタイトル（"title" か 'title'）。タイトルが無ければ中身全体をパスとして扱う
TITLE = re.compile(r'^(.*?)\s+(?:"[^"]*"|\'[^\']*\')\s*$')

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
            if Path(candidate).is_absolute():  # %2F で始まる参照がデコードで絶対パスになるのを防ぐ
                continue
            img_path = (md_dir / candidate).resolve()
            try:
                if img_path.is_file():
                    data = img_path.read_bytes()
                    break
            except OSError:
                continue
        if data is None:
            return match.group(0)
        b64 = base64.b64encode(data).decode('ascii')
        return f'<img src="data:{mime};base64,{b64}" alt="{html.escape(alt, quote=True)}" style="max-width:100%"/>'

    content = re.sub(r'!\[([^\]]*)\]\(([^)]+)\)', replace_image, content)
    output_path.write_text(content, encoding='utf-8')

if __name__ == '__main__':
    main()
