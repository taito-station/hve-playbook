#!/bin/bash
# クリーンアーキテクチャ共通規約のクライアントの節の契約検査（Issue #58）
#
# 実行: bash tests/test_clean_architecture_contract.sh
#
# 検査すること:
#   - クライアントの節が、Web（React の SPA）とモバイル（Flutter）に分かれ、それぞれレイヤーの表を持つ
#   - 適用範囲（それ以外のクライアントは原則だけ・hve-local）、use-case の層が必須、エラーの変換、
#     既存のクライアントの扱いがクライアントの節にある
#   - 両方の表で、model は何にも依存せず、use-case は実装・画面の層に依存せず、画面の層は model と use-case だけに依存し、
#     依存の組み立ての行がある。Flutter の data は use-case のエラー型へ変換できる
#   - 秘密情報・認可、ルートの定義、画面の層で動くキャッシュ、lib/utils/ の扱いがある
#   - Flutter で、原則の gateway が repository に当たり、抽象を domain に置く
#   - 「#58 で作る・決める」の記述が残っていない
#   - 未定義の領域に、クライアントのライブラリの選択がある
#   - 判断の ADR・一覧の行・質問票の記録がある

set -u
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
CA="$ROOT/rules/hve/clean-architecture.md"
[ -f "$CA" ] || { echo "[FAIL] 規約のファイルが無い: $CA"; exit 1; }
pass=0
fail=0
check() {
    local name="$1"; shift
    if "$@"; then echo "[PASS] $name"; pass=$((pass + 1)); else echo "[FAIL] $name"; fail=$((fail + 1)); fi
}
# 見出し $2 から、次の同じ深さ以上の見出し（$3 で始まる行）の手前までに $4 があるか
section_has() { awk -v s="$2" -v e="$3" 'index($0,s)==1{on=1;next} on&&index($0,e)==1{on=0} on' "$1" 2>/dev/null | grep -qF -- "$4"; }
# 見出し $2 から次の見出し $3 の手前で、$4 で始まる表の行の最後のセル（依存してよい先）が $5 か
last_cell_is() {
    local row
    row="$(awk -v s="$2" -v e="$3" 'index($0,s)==1{on=1;next} on&&index($0,e)==1{on=0} on' "$1" 2>/dev/null | awk -v k="$4" 'index($0,k)==1' | head -1)"
    [ -n "$row" ] && [ "$(printf '%s' "$row" | awk -F'|' '{gsub(/^ +| +$/,"",$(NF-1)); print $(NF-1)}')" = "$5" ]
}

CLIENT="## クライアント（フロントエンド・モバイル）"
WEB="### Web（React の SPA）"
MOBILE="### モバイル（Flutter）"

# 1) 「#58 で作る・決める」が残っていない
check "規約: クライアントの規約がまだ無いという記述が残っていない" bash -c '! grep -qF "レイヤー構成と命名の規約はまだ無い" "$1"' _ "$CA"
check "規約: 原則の節に「クライアントでは #58 で決める」が残っていない" bash -c '! grep -qF "クライアントでは #58 で決める" "$1"' _ "$CA"

# 2) クライアントの節の共通の決まり
check "クライアント: Web の節がある" section_has "$CA" "$CLIENT" "## " "$WEB"
check "クライアント: モバイルの節がある" section_has "$CA" "$CLIENT" "## " "$MOBILE"
check "クライアント: それ以外のクライアントは原則の節だけを適用し hve-local に書く" section_has "$CA" "$CLIENT" "## " "原則の節だけを適用し、構成は \`.claude/rules/hve-local/clean-architecture.md\` に書く"
check "クライアント: use-case の層は必須" section_has "$CA" "$CLIENT" "## " "use-case の層は必須"
check "クライアント: 画面の層は gateway・repository を抽象も実装も直接使わない" section_has "$CA" "$CLIENT" "## " "抽象（gateway・repository）も実装も直接使わない"
check "クライアント: エラーをレイヤーごとに変換し、画面に内部の詳細を出さない" section_has "$CA" "$CLIENT" "## " "画面には内部の詳細を出さない"
check "クライアント: 既存のクライアントは既存の構成に合わせる" section_has "$CA" "$CLIENT" "## " "既存のクライアントがこの構成でなければ、既存の構成と命名に合わせる"
check "クライアント: 移行するかは各リポジトリの Issue で決める" section_has "$CA" "$CLIENT" "## " "この構成へ移行するかは各リポジトリの Issue で決める"
check "クライアント: 画面の詳細はログに回し、秘密情報・個人情報は出さない" section_has "$CA" "$CLIENT" "## " "詳細はログに残す。秘密情報・認証情報・個人情報は出さない"
check "クライアント: 秘密情報を置かず、認可はサーバで判定する" section_has "$CA" "$CLIENT" "## " "認可はサーバで判定し、クライアントでの判定は表示の制御に留める"
check "クライアント: ルートのパスの定数の置き場所（Web は presentation、Flutter は routes.dart）" section_has "$CA" "$CLIENT" "## " "Web は \`src/presentation/\` に置く。Flutter は case study どおり \`lib/routing/routes.dart\` に置き、ui はこのファイルだけ参照してよい"
check "クライアント: 画面の層で動くキャッシュは取得を use-case 経由にすれば画面の層に置いてよい" section_has "$CA" "$CLIENT" "## " "取得を use-case（Web は interactor）経由にすれば、キャッシュを画面の層に置いてよい"
check "クライアント: 手本は別のリポジトリとして作る" section_has "$CA" "$CLIENT" "## " "別のリポジトリとして作る"

# 3) Web の表の依存の向き
check "Web: model は何にも依存しない" last_cell_is "$CA" "$WEB" "#" "| model |" "なし"
check "Web: use-case は model だけに依存する" last_cell_is "$CA" "$WEB" "#" "| use-case |" "model"
check "Web: gateway は model と use-case に依存する" last_cell_is "$CA" "$WEB" "#" "| gateway |" "model・use-case"
check "Web: presentation は model と use-case の interactor・errors だけに依存する" last_cell_is "$CA" "$WEB" "#" "| presentation |" "model・use-case の interactor と errors"
check "Web: 依存の組み立ての行（app）がある" last_cell_is "$CA" "$WEB" "#" "| app |" "すべて"

# 4) Flutter の表の依存の向き
check "Flutter: model は何にも依存しない" last_cell_is "$CA" "$MOBILE" "#" "| model |" "なし"
check "Flutter: use-case は model と repository の抽象だけに依存する" last_cell_is "$CA" "$MOBILE" "#" "| use-case |" "model・repository の抽象"
check "Flutter: repository の抽象は model と use-case のエラー型に依存する" last_cell_is "$CA" "$MOBILE" "#" "| repository の抽象 |" "model・use-case のエラー型"
check "Flutter: data は model・repository の抽象・use-case のエラー型に依存する" last_cell_is "$CA" "$MOBILE" "#" "| data |" "model・repository の抽象・use-case のエラー型"
check "Flutter: use-case のエラー型を lib/domain/use_cases/errors/ に置く" section_has "$CA" "$MOBILE" "#" "\`lib/domain/use_cases/errors/\`"
check "クライアント: 補助（src/utils/・lib/utils/）は層に属さずどの層からも使ってよい" section_has "$CA" "$CLIENT" "## " "ドメインの概念を持たない補助（Web は \`src/utils/\`、Flutter は \`lib/utils/\`）は層に属さず、どの層からも使ってよい。補助は層のコードを import しない"
check "Web: presentation は interactor を受け取る口を持ち、app を import しない" section_has "$CA" "$WEB" "#" "presentation は app を import しない"
check "未定義の領域: 言語別規約が定めるのはバックエンドの項目だけ" grep -qF "このうちバックエンドの項目（トランザクションの境界を除く）を定めている" "$CA"
check "Flutter: ui は model と use-case だけに依存する" last_cell_is "$CA" "$MOBILE" "#" "| ui |" "model・use-case"
check "Flutter: 依存の組み立ての行がある" last_cell_is "$CA" "$MOBILE" "#" "| 組み立て・起動 |" "すべて"
check "Flutter: 公式の case study を基にする" section_has "$CA" "$MOBILE" "#" "https://docs.flutter.dev/app-architecture/case-study"
check "Flutter: 原則の gateway は repository に当たる" section_has "$CA" "$MOBILE" "#" "原則の gateway は repository に当たる"
check "Flutter: repository の抽象は lib/domain/repositories/ に置く" section_has "$CA" "$MOBILE" "#" "\`lib/domain/repositories/\`"

# 5) 未定義の領域
check "未定義の領域: クライアントの状態管理・ルーティング・キャッシュのライブラリ" section_has "$CA" "## 未定義の領域" "## " "クライアントの状態管理・ルーティング・サーバの状態のキャッシュに使うライブラリ"

# 6) 決定ログと質問票の記録
ADR="$(ls "$ROOT"/knowledge/adr/[0-9][0-9][0-9][0-9]-client-clean-architecture.md 2>/dev/null | head -1)"
check "Issue #58 の ADR がある（番号でなく slug で探す）" [ -n "$ADR" ]
check "ADR 一覧に Issue #58 の ADR の行がある" grep -qF -- "-client-clean-architecture.md)" "$ROOT/knowledge/adr/README.md"
check "質問票の記録がある" [ -f "$ROOT/qa/client-clean-architecture-questionnaire.md" ]

echo
echo "passed: $pass, failed: $fail"
[ "$fail" -eq 0 ]
