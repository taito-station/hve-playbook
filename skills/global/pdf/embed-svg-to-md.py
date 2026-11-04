#!/usr/bin/env python3
import base64, mimetypes, re, sys
from pathlib import Path

def main():
    md_path = Path(sys.argv[1])
    output_path = Path(sys.argv[2])
    md_dir = md_path.parent
    content = md_path.read_text(encoding='utf-8')

    # 入力の Markdown から辿れるローカルの画像（SVG・PNG・JPEG など）を data URI にする。
    # 出力は作業ディレクトリに置くので、ファイルで参照したままだと md-to-pdf が相対パスを解決できない（Issue #102）。
    def replace_image(match):
        alt, src = match.group(1), match.group(2)
        if src.lower().endswith('.svg'):
            mime = 'image/svg+xml'
        else:
            mime = mimetypes.guess_type(src)[0] or ''
            if not mime.startswith('image/'):
                return match.group(0)
        img_path = (md_dir / src).resolve()
        if not img_path.is_file():
            return match.group(0)
        b64 = base64.b64encode(img_path.read_bytes()).decode('ascii')
        return f'<img src="data:{mime};base64,{b64}" alt="{alt}" style="max-width:100%"/>'

    content = re.sub(r'!\[([^\]]*)\]\(([^)]+)\)', replace_image, content)
    output_path.write_text(content, encoding='utf-8')

if __name__ == '__main__':
    main()
