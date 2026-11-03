#!/usr/bin/env python3
import base64, re, sys
from pathlib import Path

def main():
    md_path = Path(sys.argv[1])
    output_path = Path(sys.argv[2])
    md_dir = md_path.parent
    content = md_path.read_text(encoding='utf-8')

    def replace_svg(match):
        alt, src = match.group(1), match.group(2)
        if not src.endswith('.svg'):
            return match.group(0)
        svg_path = (md_dir / src).resolve()
        if not svg_path.exists():
            return match.group(0)
        b64 = base64.b64encode(svg_path.read_bytes()).decode('ascii')
        return f'<img src="data:image/svg+xml;base64,{b64}" alt="{alt}" style="max-width:100%"/>'

    content = re.sub(r'!\[([^\]]*)\]\(([^)]+)\)', replace_svg, content)
    output_path.write_text(content, encoding='utf-8')

if __name__ == '__main__':
    main()
