# Issue #50 許可要求ログ hook の秘密値の扱い

- 対象スコープ: hooks/permission-request-logger.py とそのテスト、README の注意書き
- 対象ドキュメント:
  - `hooks/permission-request-logger.py`
  - `skills/global/review-permissions/SKILL.md`
  - `README.md`
- 関連スコープ: Issue #50（#40 / PR #47 のレビューで検出）
- 生成: aqod（debug ログの既定、JSONL 本体の扱い、範囲の境界を決める）
- 状態: 回答済み
- 推論許可: 既定値候補は手元のログの実測（debug ログ 5199 件の集計）とコードの読解に基づく
- 作成日: 2026-10-12
- 回答確定日: 2026-10-12
- 反映先: `hooks/permission-request-logger.py`、`knowledge/adr/`（ADR 起票）

## サマリー

`hooks/permission-request-logger.py` は許可を求めた操作の `tool_input` を平文で `~/.claude/logs/permission-requests.jsonl` に追記し、payload 全体を debug ログ（`~/.claude/logs/debug-perm-request.log`）にも既定で書いている。debug ログの既定、JSONL 本体の扱い、範囲の境界を決める。

---

[Q01]
- 対象ドキュメント: hooks/permission-request-logger.py
- 該当箇所: DEBUG_ENABLED（68 行目）、docstring 13〜18 行目
- 問題種別: 不明瞭
- 重大度: major
- 質問内容: debug ログ（payload 全体の dump）の既定をどうするか
- 選択肢: A) 既定 OFF にし、PERM_REQUEST_DEBUG=1 のときだけ書く（観測は完了したと判断） B) 既定 ON のまま、止め方（PERM_REQUEST_DEBUG=0）を README に明記する C) debug ログの機能自体を削除する
- 未回答時の既定値候補: 既定 OFF にし、PERM_REQUEST_DEBUG=1 のときだけ書く（観測は完了したと判断）
- 既定値候補の理由: 4.5 か月・5199 件の観測で schema が安定しており、Phase A の目的は果たした。docstring の予定どおり既定 OFF に切り替えるのが最小で、秘密値の平文の保存先が 1 つ減る
- 未回答のまま進めた場合の影響: 既定 ON のままだと、第三者の環境でも payload 全体が平文で溜まり続ける

[Q02]
- 対象ドキュメント: hooks/permission-request-logger.py
- 該当箇所: append_log（256 行目〜）
- 問題種別: 重大な欠落
- 重大度: major
- 質問内容: JSONL 本体（permission-requests.jsonl）の秘密値をどう扱うか
- 選択肢: A) 既知の秘密値のパターン（Authorization / Bearer、token= などのクエリ、*_TOKEN= などの環境変数代入）を伏せて書き、加えて環境変数で記録自体を止められるようにする B) 環境変数で記録を止められるようにするだけ（伏せない） C) 既知のパターンを伏せるだけ（止める手段は作らない） D) 現状維持（README の注意だけ）
- 未回答時の既定値候補: 既知の秘密値のパターンを伏せて書き、加えて環境変数で記録自体を止められるようにする
- 既定値候補の理由: Issue の要件「残る範囲を減らす、または止められるようにする」の両方を満たす。伏せるのはクラスタリングに使わない値の部分だけなので review-permissions は動き続ける。パターンで漏れる秘密値は止める手段で補う
- 未回答のまま進めた場合の影響: Authorization ヘッダや URL の token などが平文で残り続ける

[Q03]
- 重大度: minor
- 質問内容: ログの保存期間・ローテーションを今回の範囲に含めるか
- 選択肢: A) 含めない（必要になったら別 Issue） B) 含める（サイズや日数で古い行を消す）
- 未回答時の既定値候補: 含めない（必要になったら別 Issue）
- 既定値候補の理由: JSONL はレビューで切り詰められ、debug ログは既定 OFF で増えなくなる。要件にないローテーションを先回りして足さない

[Q04]
- 重大度: minor
- 質問内容: 既に溜まっている debug ログ・JSONL の過去分をどうするか
- 選択肢: A) hook では消さず、README に「過去分は手で消してよい」と書く B) debug を OFF にしたとき hook が debug ログを消す C) 何もしない（README にも書かない）
- 未回答時の既定値候補: hook では消さず、README に「過去分は手で消してよい」と書く
- 既定値候補の理由: 利用者のファイルを黙って消さない。過去分は平文のままなので、消し方だけ案内する

---

## 回答（確定 2026-10-12）

| No. | 回答 | 判断 | 根拠 |
|---|---|---|---|
| Q01 | **既定 OFF にし、PERM_REQUEST_DEBUG=1 のときだけ書く（観測は完了したと判断）** | 既定値承認 | 4.5 か月・5199 件の観測で schema が安定しており、Phase A の目的は果たした。docstring の予定どおり既定 OFF に切り替えるのが最小で、秘密値の平文の保存先が 1 つ減る |
| Q02 | **既知の秘密値のパターンを伏せて書き、加えて環境変数で記録自体を止められるようにする** | 既定値承認 | Issue の要件の両方を満たす。伏せるのはクラスタリングに使わない値の部分だけなので review-permissions は動き続ける。パターンで漏れる秘密値は止める手段で補う |
| Q03 | **含めない（必要になったら別 Issue）** | 既定値承認 | JSONL はレビューで切り詰められ、debug ログは既定 OFF で増えなくなる。要件にないローテーションを先回りして足さない |
| Q04 | **README には書かない。hook にも削除処理を入れない。作者の環境の debug ログの過去分は、この対応の中で手で削除する（JSONL は review-permissions で使うので残す）** | 人間判断 | 回答「README に書かずに消して」を、確認の質問（手元の過去分を今消す / hook が消す / debug と JSONL を両方消す）で「手元の過去分を今消す」と確定した |
