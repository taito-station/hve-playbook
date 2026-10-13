# 許可要求ログの hook は既知の形の秘密値を伏せて書き、debug ログは opt-in、本体は環境変数で止められるようにする

## ステータス

Accepted — 2026-10-13

## 背景と課題

`hooks/permission-request-logger.py`（PermissionRequest hook。user-level の `settings.json` で既定で有効）は、許可を求めた操作の `tool_input` を平文で `~/.claude/logs/permission-requests.jsonl` に追記していた。payload 全体を書く debug ログ（`~/.claude/logs/debug-perm-request.log`）も既定で書いていた。debug ログは、payload の schema が公式に文書化されていなかったための観測用（Phase A）で、docstring に「十分な観測後に既定 OFF へ切り替える」とあった。JSONL を止める設定は無く、リポ版の hook は `settings.machine.json` から外せない（ADR 0006）。

リポジトリは PUBLIC になり、第三者が user-level を入れうる。許可ダイアログの対象になるコマンドは、Authorization ヘッダや URL の token などの秘密値を含むことが多い（[hve-playbook#50](https://github.com/taito-station/hve-playbook/issues/50)。#40 のレビューで検出）。

問い: 許可要求のログに秘密値が平文で残る範囲をどう減らし、利用者がどう止められるようにするか。

## 意思決定の要因

- `review-permissions` skill（`tool_input` の command の先頭 3 トークン・tool 名・`file_path` でクラスタを作り、危険パターンを判定する）と `statusline.sh`（JSONL の行数を数える）が動き続ける
- 伏せる処理で、危険な後続（`| sh`・`&& rm -rf` など）を消さない。秘密値でない文字列を伏せない
- 要件にない仕組み（ローテーション・過去分の自動削除）を足さない

## 検討した選択肢

- debug ログ: 既定 OFF（opt-in） / 既定 ON のまま止め方を明記 / 機能を削除
- JSONL: 既知の形の秘密値を伏せ、かつ環境変数で止められるようにする / 止めるだけ / 伏せるだけ / 現状維持

## 決定内容

Issue #50 の質問票（`qa/permission-request-log-secrets-questionnaire.md`）で確定した。

- debug ログは `PERM_REQUEST_DEBUG=1` のときだけ書く（"true" なども OFF）。2026-05-29〜2026-10-12 の 5199 件の観測で、`tool_name` / `tool_input` が常にトップレベルにあることを確かめ、観測（Phase A）は完了とした
- `PERM_REQUEST_LOG=0` のとき JSONL を書かない。未設定のときは従来どおり書く。利用者は `settings.machine.json` の `env` に書いて同期すれば止められる（settings の `env` が hook のプロセスに届くことを `claude -p --settings` で実測した）
- 書く前に、次の形の値を `<redacted>` に置き換える。JSONL は `tool_input`・`title`・`message` の文字列を、debug ログは payload 全体を、dict / list を再帰して伏せる
  - `Authorization:` / `Proxy-Authorization:` ヘッダの値（スキーム語 Bearer などは残す。値が 8 文字以上のときだけ）
  - ヘッダ名の無い `Bearer <token>`（値が 8 文字以上で、数字を含むときだけ。英文の "Bearer authentication." や検索語の `Authorization: Bearer` に当てないため）。ヘッダ名と値の間の空白は改行を含めない
  - URL クエリ・フラグメントの `token`・`*_token`（`access_token`・`private_token`・`refresh_token` など）・`api_key`・`apikey`・`password`・`secret`・`client_secret` の値（`?` / `&` / `#` の直後に限る。キー名は大文字小文字を区別しない）
  - 名前に `TOKEN`・`SECRET`・`PASSWORD`・`API_KEY` を含む大文字の環境変数代入の値（大文字小文字を区別し、`max_tokens=` などに当てない。名前の長さに上限を付けて計算量を抑える。単一引用符の中の `$` は展開されないので伏せる）
  - URL の userinfo の password（`https://user:<token>@host`）。Issue の「URL の token」に当たり、`git clone` で出る形のため
- 値は空白・引用符・シェルの区切り（`|`・`;`・`&`・`>`・`(`・`)`・バッククォート）の手前までとし、後ろは残す（`| sh` などの危険の手掛かりを消さない）。どのパターンでも、`$` で始まる参照（`$VAR`・`$(cmd)`）と、二重引用符の中にコマンド置換を含む環境変数の値は伏せず、引用符なしの値は途中の `$` の手前で止める。環境変数の引用符の値は、改行ともう一方の種類の引用符を含まず、閉じ引用符の直後が空白・行末・シェルの区切りのときだけ伏せる（別の引用符の中の `NAME='` から伏せ始めて、実行される `| sh` を飲み込まないため。そこから抜けるにはもう一方の引用符が要る）。URL の userinfo の値も同じくシェルの区切りと `$` の手前までとする。秘密値そのものではなく、伏せると `review-permissions` の危険パターンの判定から `$(curl …|sh)` などの手掛かりが消えるため。伏せ字に `*` を使わない（許可ルールの glob 案に混ざるため）
- 伏せる処理で例外が出たら書かない（fail-closed）。hook は exit 0 で終わる
- `review-permissions` Step 6 のコード例は、reviewed と `.jsonl.new` を 0600 で作る（従来は umask の既定で 0644 になり、過去の平文の `tool_input` が他のユーザーから読めた）
- ローテーション・保存期間、過去分の自動削除は扱わない。README に過去分の削除の案内も書かない（質問票 Q03・Q04）
- 挙動は `tests/test_permission_request_logger.sh` で固定する

### 結果（Consequences）

- 良い結果: 既定の設定で、debug ログ（payload 全体）が書かれなくなり、JSONL からは既知の形の秘密値が消える。止めたい利用者は環境変数 1 つで止められる。秘密値を含まない入力は従来と同じ内容で書かれるので、`review-permissions` のクラスタリングは変わらない
- 悪い結果: パターンに当たらない秘密値（独自のヘッダ名（`X-Api-Key`・`PRIVATE-TOKEN`・`Cookie` など）、`--password=…`・`curl -u user:pass` などのオプション、本文中の鍵、7 文字以下や数字を含まない Bearer トークン、値の途中に `$` を含むトークンの `$` 以降、もう一方の種類の引用符を含む環境変数の値（`A_TOKEN="x'y"`）、シェルの区切りや `$` を含む URL の userinfo の password（`https://u:p&q@h`。通常はパーセントエンコードされる）、Bearer・Basic・Token・Digest 以外のスキーム（Negotiate など）の値と AWS SigV4 の `Signature=`、`key`・`sig`・`signature`・`X-Amz-*` などのクエリ、ユーザー名だけの userinfo（`https://<token>@github.com`）、dict のキー名で秘密とわかる値（MCP の `{"api_key": …}`、スキーム語が Bearer 以外の `{"Authorization": "Basic …"}` など））は平文で残る。`key`・`sig` とユーザー名だけの userinfo は、伏せると誤マスクの面が広がる（`gh api -f key=v`・`https://user@host`）ため対象にしていない。逆に、`docker://alpine:3.19@sha256:…` のタグを userinfo とみなして伏せる。`NUM_TOKENS=5`・`PASSWORD_FILE=/etc/x` のように名前に TOKEN などを含むだけの変数も伏せる（短いパスワードを取りこぼさないため、環境変数の値には長さの下限を設けない）。これが Bash の先頭にあると `review-permissions` のクラスタのキーが `NUM_TOKENS=<redacted>` になる。残したくなければ `PERM_REQUEST_LOG=0` で止める。伏せた値は `review-permissions` の「具体的なコマンド例」でも `<redacted>` と表示される。payload の schema が変わったときの再観測は、`PERM_REQUEST_DEBUG=1` を明示しないとできない。すでに溜まった平文の過去分は、各利用者の環境に残る。先頭 3 トークンに秘密値を含む Bash では、過去の平文の行と新しい伏せた行のクラスタが分かれる。`review-permissions` は前後の tool_use を Claude Code の transcript から抜き出すので、伏せた値はそこから表示されうる（transcript はこの hook が書くものではなく範囲外）

## 選択肢の評価（Pros and Cons）

### debug ログを既定 OFF（opt-in）にする（採用）

#### メリット

- 秘密値の平文の保存先が 1 つ減る。docstring の予定どおりで、変更が小さい

#### デメリット

- schema の再観測には明示の設定が要る

### debug ログを削除する

#### メリット

- コードが減る

#### デメリット

- 調査が要るときに opt-in で使える余地が無くなる

### JSONL: 伏せたうえで止められるようにする（採用）

#### メリット

- 「残る範囲を減らす」と「止められる」の両方を満たす。パターンの漏れを止める手段で補える

#### デメリット

- 正規表現の保守が要る。誤マスクと漏れの境界をテストで固定する必要がある

### JSONL: 止めるだけ・伏せるだけ・現状維持

#### メリット

- 実装が小さい

#### デメリット

- 止めるだけでは既定の利用者のログに秘密値が残り、伏せるだけではパターンの漏れを止める手段が無い。現状維持は Issue の要件を満たさない

## 関連リンク

- Related: [0006-generate-settings-json-with-machine-overlay](0006-generate-settings-json-with-machine-overlay.md)（リポ版の hook は overlay で外せないので、止める手段を hook 側に設けた。`settings.machine.json` の `env` は同期で `settings.json` に入る）
- Related: [hve-playbook#50](https://github.com/taito-station/hve-playbook/issues/50)
- Related: [hve-playbook#40](https://github.com/taito-station/hve-playbook/issues/40)
