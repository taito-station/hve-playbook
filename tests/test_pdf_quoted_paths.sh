#!/bin/bash
# pdf skill のコマンド例で、パスのプレースホルダがクォートされていることの検査（Issue #100）
#
# 実行: bash tests/test_pdf_quoted_paths.sh
#
# 検査すること:
#   - 手順 1・3-2・3-3 のコマンド例で、パスのプレースホルダがダブルクォートで囲まれている
#   - 手順 3-2 の入力が具体名（manual.md）ではなくプレースホルダになっている
#   - クォートされていない旧い書き方が残っていない
#   - ダブルクォートの中で解釈される文字（$・`・"・\）のエスケープの規則が書いてある
#   - フォントの確認コマンドが、出力のパスを Python の文字列に埋め込まず argv で渡す

set -u
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SKILL="$ROOT/skills/global/pdf/SKILL.md"
pass=0
fail=0
check() {
    local name="$1"; shift
    if "$@"; then echo "[PASS] $name"; pass=$((pass + 1)); else echo "[FAIL] $name"; fail=$((fail + 1)); fi
}
has() { grep -qF -- "$1" "$SKILL"; }
lacks() { ! grep -qF -- "$1" "$SKILL"; }

check "手順 1: 入力と出力をクォートする" has '~/.claude/hooks/run-drawio-export.sh "<入力.drawio>" "<出力.svg>"'
check "手順 3-2: ディレクトリと入力をクォートする" has 'cd "<md があるディレクトリ>" && npx --yes md-to-pdf "<入力.md>" \'
check "手順 3-3: 入力をクォートする（行全体で照合し、手順 3-2 の行と区別する）" grep -qxF -- 'npx --yes md-to-pdf "<入力.md>" \' "$SKILL"
check "手順 3-2: <入力.md> が cd 先から見たファイル名だと書いてある" has '`<入力.md>` には、`<md があるディレクトリ>` から見たファイル名を入れる'
check "置き換えの規則: ダブルクォートの中で解釈される文字をエスケープする" has 'パスに `$`・`` ` ``・`"`・`\` が含まれるときは、それぞれの直前に `\` を付けてから置き換える'
check "フォントの確認: 出力のパスを argv で渡す" has "PdfReader(sys.argv[1])"
check "フォントの確認: Python の文字列にパスを埋め込まない" lacks "PdfReader('<出力.pdf>')"
check "手順 3-2・3-3: --basedir をクォートする" has '--basedir "<共通ルート>" \'
check "手順 1: クォートなしの形が残っていない" lacks 'run-drawio-export.sh <入力.drawio>'
check "手順 3-2: 入力が具体名 manual.md でない" lacks 'md-to-pdf manual.md'
check "手順 3-2: cd のディレクトリがクォートなしで残っていない" lacks 'cd <md があるディレクトリ>'
check "手順 3-3: 入力がクォートなしで残っていない" lacks 'md-to-pdf <md>'
check "手順 3-2・3-3: 入力がクォートなしで残っていない" lacks 'md-to-pdf <入力.md>'
check "手順 3-2・3-3: --basedir がクォートなしで残っていない" lacks '--basedir <共通ルート>'

echo
echo "passed: $pass, failed: $fail"
[ "$fail" -eq 0 ]
