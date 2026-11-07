#!/bin/bash
# run-all.sh が、スキップを出したテストの理由をまとめに出すことを検査する（Issue #111）
#
# 実行: bash tests/test_run_all.sh
#
# run-all.sh を一時ディレクトリに写し、ダミーのテストだけを置いて流す（本物の全件は流さない）。
# このテスト自身も run-all.sh の全件に含まれるので、成功時の出力にスキップの目印の語を出さない
# （出すと外側の run-all.sh が、このテストをスキップありと判定する）。

set -u
RUN_ALL="$(cd "$(dirname "$0")" && pwd)/run-all.sh"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
FAIL=0

# ダミーのテストを置いたディレクトリを作る。引数は「ファイル名 本文」の組
make_suite() {
    local dir="$TMP/$1"; shift
    mkdir -p "$dir"
    cp "$RUN_ALL" "$dir/run-all.sh"
    while [ "$#" -gt 0 ]; do
        printf '#!/bin/bash\n%s\n' "$2" > "$dir/$1"
        shift 2
    done
}

# 中の run-all.sh を macOS 標準の /bin/bash（3.2）で流す。run-all.sh はログの一時ディレクトリを残すので、
# 結果の行に出るパスから割り出して消す（macOS の mktemp -d は TMPDIR を見ないので、置き場所は向けられない）
run_suite() {
    local work
    OUT="$(/bin/bash "$TMP/$1/run-all.sh" 2>&1)"
    RC=$?
    work="$(printf '%s\n' "$OUT" | sed -n 's|^結果: .*（ログ: \(.*\)/logs）$|\1|p')"
    case "$work" in */tmp.*) rm -rf "$work" ;; esac
}

check() {
    local desc="$1"; shift
    if "$@"; then
        echo "[PASS] $desc"
    else
        echo "[FAIL] $desc"
        printf '%s\n' "$OUT" | sed 's/^/    | /'
        FAIL=1
    fi
}

has_line() { printf '%s\n' "$OUT" | grep -qxF "$1"; }
reason_lines() { printf '%s\n' "$OUT" | grep -c '^SKIP: '; }
summary_after_reasons() {
    # 理由の行が、まとめ（結果: の行）の前にある
    printf '%s\n' "$OUT" | awk '/^SKIP: /{s=NR} /^結果: /{r=NR} END{exit !(s && r && s < r)}'
}

S='SKIP'  # 目印の語。このファイルの出力にそのまま出さないよう、変数に入れて組み立てる

# ① PASS とスキップだけ → exit 0、実在する 3 つの形の理由が出る
make_suite one \
    test_a.sh 'echo ok' \
    test_b.sh "echo \"$S: tmux not available\"; echo \"$S: python3 not available\"" \
    test_c.sh "echo \"[$S] chrome: Chrome が見つからない\"; echo '=== 静的検証: 0 failed / ブラウザ検証: $S ==='; echo '${S}PED_CASES=3'" \
    test_d.sh "printf '$S  macOS: Glass.aiff が無い\n'"
run_suite one
check "① exit 0" [ "$RC" -eq 0 ]
check "① コロンの形の理由が出る" has_line "$S: test_b.sh — tmux not available"
check "① 1 本が出す 2 行目の理由も出る" has_line "$S: test_b.sh — python3 not available"
check "① 角括弧の形の理由が出る" has_line "$S: test_c.sh — chrome: Chrome が見つからない"
check "① 空白 2 つの形の理由が出る" has_line "$S: test_d.sh — macOS: Glass.aiff が無い"
check "① 行頭が目印でない行・目印で終わらない語の行は理由に出さない" [ "$(reason_lines)" -eq 4 ]
check "① 理由はまとめの前に出る" summary_after_reasons

# ② PASS だけ → exit 0、理由の行が出ない
make_suite two test_a.sh 'echo ok'
run_suite two
check "② exit 0" [ "$RC" -eq 0 ]
check "② 理由の行が出ない" [ "$(reason_lines)" -eq 0 ]

# ③ スキップを出してから FAIL するテストを含む → exit 1、その理由も出る
make_suite three \
    test_a.sh 'echo ok' \
    test_b.sh "echo \"$S: python3 が無い\"; exit 1"
run_suite three
check "③ exit 1" [ "$RC" -eq 1 ]
check "③ FAIL したテストの理由も出る" has_line "$S: test_b.sh — python3 が無い"

# ④ 行の途中にだけ目印があるテスト → 理由の行の代わりに、ログを見るよう促す行が出る
make_suite four test_a.sh "echo '  in traceback INTERNAL_TOOLS_${S}_LOGGING'"
run_suite four
check "④ exit 0" [ "$RC" -eq 0 ]
check "④ 理由の行が無いことと、ログの場所が出る" \
    sh -c 'printf "%s\n" "$1" | grep -qE "^$2: test_a\.sh — （理由の行なし。ログ: .*/test_a\.sh\.log）$"' _ "$OUT" "$S"

echo "==================================="
if [ "$FAIL" -eq 0 ]; then echo "ALL TESTS PASSED"; exit 0; else echo "SOME TESTS FAILED"; exit 1; fi
