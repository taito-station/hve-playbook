# 不確定点チェックの回答探索から Gmail 検索を外す

## ステータス

Partially superseded by 0030-drop-past-gmail-qa-special-rules — 2026-10-31

- 有効な部分: 下の失効した部分以外の決定はすべて有効（Gmail 検索の手順と `allowed-tools` の Gmail を外したこと、hve-implement の Step 4 の探索順など）
- 失効した部分: 過去に保存した `source: gmail` の Q&A の扱い（ADR 0019）は変えず、PII の除外とガードレールをその規則の場所に書き直したこと。過去分の Q&A の内容が引き続き既定値候補の理由として `qa/*.md` に載ること、その写しの扱いを #63 で決めること。0030 でその特例規定を外し（既定値候補として載る経路は無くなった）、写しは 0 件のため扱いを定めないとした

## 背景と課題

resolve-issue と create-issue の不確定点チェックは、Issue の不明点の回答を knowledge → Gmail → PO の質問票の順に探していた。ADR 0019 で、Gmail で見つけた事実は保存せず、質問票の既定値候補とその理由（「Gmail（YYYY-MM-DD）に記載: <抽出した事実>」）として PO に示すことにした。questionnaire skill は既定値候補とその理由を質問票の記録（`qa/*.md`。git 管理）に残すので、PO が採らなかった Gmail の事実も記録に残り、PUBLIC なリポジトリでは公開される。

抽出時の除外の規則は、個人情報（個人名・メールアドレス・電話番号）と、メールの引用・やり取りの文面だけを対象にしていた。取引先との契約条件・金額などの機密な業務情報と、出所（社内か外部か）を PO が判断する材料は定めていなかった（[hve-playbook#64](https://github.com/taito-station/hve-playbook/issues/64)。#56 の PR #59 のセルフレビューの Security 指摘から切り出した）。

問い: 質問票の記録に載る Gmail 由来の情報について、機密な業務情報の扱いと出所の示し方をどう決めるか。その前に、Gmail で回答候補を探す仕組みを続ける必要があるか。

## 意思決定の要因

- 質問票の記録から、メール由来の機密な業務情報が公開されない
- 規則を増やさない（使われていない仕組みに規則を継ぎ足さない）
- resolve-issue・create-issue・hve-implement の扱いが食い違わない

## 検討した選択肢

- Gmail 検索の手順を外す
- 続け、機密な業務情報の除外（PUBLIC リポジトリでは要約の粒度に留める、または既定値候補にしない）と送信元の区分（社内／取引先）の規則を足す
- 既定では行わず、PO が Issue 対応時に明示したときだけ行う

## 決定内容

選択した選択肢: **Gmail 検索の手順を外す**。Issue #64 の質問票（`qa/gmail-derived-info-in-qa-records-questionnaire.md`）の Q01 で確定した。機密な業務情報の扱い（Q02）と送信元の区分（Q03）は、手順が無くなるので決めない。

- resolve-issue の Step 2 [feature] 項目 1 から手順 2（Gmail 検索）を削除し、探索を knowledge → PO の質問票の 2 段にする。旧手順 3・4 は手順 2・3 になった（ADR 0017・0019 の本文の手順番号は旧番号のまま）
- create-issue の質問票ゲート（1.5 の 3）からも Gmail 検索の手順を削除する。両 skill の `allowed-tools` から `mcp__claude_ai_Gmail__search_threads` を外す
- resolve-issue の前段の規則（hve-implement を呼ぶ場合）から「Gmail で見つけた回答」の扱いを削除する。hve-implement の Step 4 の表の探索順も knowledge → PO の質問票にする
- 過去に保存した `source: gmail` の Q&A の扱い（ADR 0019。既知の回答として除外に使わず既定値候補にし、PO が確定したら置き換える）は変えない。これまで手順 2 を参照していた PII の除外とガードレールは、その規則の場所に書き直した。過去分の扱いそのものは [hve-playbook#63](https://github.com/taito-station/hve-playbook/issues/63) で決める
- 過去分の Q&A の内容は、引き続き既定値候補の理由として `qa/*.md` に載る。ただしその内容はすでに `knowledge/<domain>/` で git 管理されているので、`qa/*.md` に載っても公開される範囲は増えない。このため本 ADR の対象外とした
- ただし #63 で過去分の Q&A を `knowledge/<domain>/` から置き換え・削除しても、それを既定値候補にした質問票の記録（`qa/*.md`）には写しが HEAD に残る。この写しの扱いも #63 で決める
- ADR 0019 のうち「Gmail 検索で見つけた事実を既定値候補にする」を置き換える（0019 は Partially superseded）
- 契約は `tests/test_qa_answer_destination.sh` と `tests/test_hve_implement_contract.sh` で固定する

### 結果（Consequences）

- 良い結果: メールから新しく情報を取り込む経路が無くなり、質問票の記録にメール由来の機密な業務情報が新しく載ることは無くなる。機密・送信元の規則を足さずに済む。不確定点チェックの手順が短くなる
- 悪い結果: メールに答えがある質問も、PO が自分で調べて答える必要がある。ただし、手順の記録の文言（「Gmail から回答候補を発見」など）が載った Issue は、gh search で検索できる範囲（アクセスできるリポジトリの Issue）では、仕組みを決めた #56 以外に見つからなかった（2026-10-25 に確認）。使われていた形跡は無い。導入先の hve-implement の写しは setup.sh を実行した時点のままなので、Step 4 の表は再適用するまで「knowledge → Gmail → PO の質問票」の記述が残る。resolve-issue（sync で常に最新）の側に Gmail の手順が無く、写しと食い違うときは resolve-issue の定義を優先するので、Gmail 検索は行わない定めになる。ただしこれは規則による定めで、機械的な保証ではない（`allowed-tools` から外しても、Gmail MCP を接続したセッションでは確認を挟めば呼べる）。確実にするには導入先で setup.sh を再適用し、写しの記述も揃える。ADR 0019 の要因の 1 つ「上流 HVE の Work IQ の扱い（メールを PO の回答の材料に留める）と揃える」に当たる経路は、本 ADR で持たなくなる。Gmail 検索を再び使いたくなったら、本 ADR を supersede する新しい ADR で、機密情報と送信元の扱い（本 Issue の Q02・Q03）と、上流の Work IQ との揃え方（ADR 0019 の要因）を決めてから戻す

## 選択肢の評価（Pros and Cons）

### Gmail 検索の手順を外す（採用）

#### メリット

- メール由来の情報の公開のおそれと、それを防ぐ規則が要らなくなる
- 手順と契約テストが減る

#### デメリット

- メールに答えがある質問も PO が答える必要がある

### 続け、機密情報と送信元の規則を足す

#### メリット

- メールの事実を PO の判断材料として使い続けられる

#### デメリット

- 使われていない仕組みに規則を継ぎ足すことになる。機密な業務情報かどうかの判定は AI の解釈に依存し、除外漏れを機械的に検出できない
- 「PUBLIC では既定値候補にしない」は、ADR 0019 で却下した「Issue コメントだけに記録する」（PO の判断材料にならない）に近づく

### 既定では行わず、PO が明示したときだけ行う

#### メリット

- 必要なときだけメールを使える

#### デメリット

- 明示したときには機密・送信元の規則が結局必要で、手順の分岐も増える

## 関連リンク

- Partially supersedes: [0019-gmail-answers-as-questionnaire-defaults](0019-gmail-answers-as-questionnaire-defaults.md)（Gmail 検索で見つけた事実を既定値候補にする部分）
- Related: [0017-qa-answers-in-qa-dir-wherever-check-knowledge-exists](0017-qa-answers-in-qa-dir-wherever-check-knowledge-exists.md)（本文の手順番号は旧番号のまま）
- Related: [hve-playbook#64](https://github.com/taito-station/hve-playbook/issues/64)
- Related: [hve-playbook#63](https://github.com/taito-station/hve-playbook/issues/63)
