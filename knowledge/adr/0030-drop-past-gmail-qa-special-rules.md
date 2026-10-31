# 過去に保存した source: gmail の Q&A の特例規定を外す

## ステータス

Accepted — 2026-10-31

## 背景と課題

resolve-issue と create-issue の不確定点チェックは、以前 Gmail で見つけた回答を Q&A 書式（`source: gmail`）で保存していた。ADR 0019 で保存をやめ、すでに保存された `source: gmail` の Q&A は knowledge 検索で既知の回答として除外に使わず、質問票の既定値候補にし、PO が確定したら置き換えることにした。ADR 0029 で Gmail 検索の手順そのものを外したが、この過去分の扱いは残した。

この特例規定は resolve-issue・create-issue・hve-implement にだけあり、implement-flow の Step 2（Knowledge 検索）や Plan の作成など別の経路で `knowledge/<domain>/` を読むときには効かない（[hve-playbook#63](https://github.com/taito-station/hve-playbook/issues/63)。#56 の PR #59 のセルフレビューの Security 指摘から切り出した）。#64（ADR 0029）からは、過去分の Q&A を既定値候補にした質問票の記録（`qa/*.md`）に残る写しの扱いも引き継いだ。

方式を決める前に、過去分が実在するかを確かめた（2026-10-31）。

- 保存の手順があった期間: Gmail 検索が入った 9e53552（2026-09-21）から、保存をやめた eea0cb3（2026-10-12）までの約 3 週間。ADR 0017 の期間（HVE 導入先では qa ディレクトリに置いた）を含む
- `knowledge/` を持つ手元の全リポジトリ（hve-playbook を含む 6 本）で、`qa/`・`docs/qa/`・`knowledge/`・`docs/knowledge/` の全履歴を `git log --all -i -G "^source: *[\"']?gmail"` で検索し 0 件。作業ツリーでも、下の結果に書いた検出コマンド（大文字小文字・引用符を問わない）で 0 件
- したがって、それを既定値候補にした `qa/*.md` の写しも無い
- 手元以外の導入先（公開している dotclaude-public の利用者など）は確認できない

問い: 過去に保存した `source: gmail` の Q&A が、どの経路でも PO の確認を経ずに前提として使われないようにするには、どうするか。

## 意思決定の要因

- PO が確認していない Q&A が、確定した前提として使われない
- 規則を増やさない（使われていない仕組みに規則を残さない。ADR 0029 と同じ判断軸）
- resolve-issue・create-issue・hve-implement・implement-flow の扱いが食い違わない

## 検討した選択肢

- (d) 特例規定を外し、実在 0 件の確認と理由を記録する
- (c) 現状維持とし、PO の確定時の置き換えで自然に減るのを待つ
- (a) `source: gmail` を未確認として扱う定義を 1 か所に置き、implement-flow の Step 2・hve-implement・Plan の作成からも参照する
- (b) 一括の移行（削除または質問票での再確認）を必須にする

## 決定内容

選択した選択肢: **(d) 特例規定を外す**。Issue #63 の質問票（`qa/past-gmail-qa-handling-questionnaire.md`）の Q01 で確定した。

- resolve-issue の Step 2 [feature] 項目 1 から、`source: gmail` の Q&A の既定値候補化・PII とメール文面の除外・ガードレール（手順 1）、既定値候補が複数のときの規定（手順 2。Gmail 対応で入った）、PO の回答での置き換え（手順 3）を削除する。前段の規則（hve-implement を呼ぶ場合）の「探索順とガードレール」を「探索順」に、手順 3 の「`source: gmail` の Q&A の削除」を削る
- create-issue の質問票ゲート（1.5 の 3）から、`source: gmail` の Q&A の扱いと置き換えを削除する
- hve-implement の Step 4 の表（resolve-issue の前段（feature））から、過去の `source: gmail` の Q&A のガードレール（事実としてだけ使う・PII を書かない）を削除する。この PII の規定は Gmail のメール向けに入ったもので、PO の回答そのものの PII の扱いは本 ADR の範囲外とする
- implement-flow（rules/global・rules/hve）には `source: gmail` の記述が無く、変えない
- Issue の要件「どの経路でも PO 未確認の前提として使われないようにする」は、(a)〜(c) の方式を採らずに閉じる。手元で対象が 0 件で、保存の経路も ADR 0019・0029 で無くなっており、新しく生じることも無いため。手元以外に残っていた場合の扱いは、規則ではなく下の結果に書く（Q03）
- 過去分を既定値候補にした `qa/*.md` の写しの扱いは定めない。写しが 0 件のため（Q02）
- 契約は `tests/test_qa_answer_destination.sh`（3 skill に `source: gmail` が無いこと、resolve-issue の feature 前処理・create-issue の質問票ゲート・hve-implement の前段（feature）の行にガードレールが無いこと、resolve-issue に既定値候補が複数のときの規定が無いこと）と `tests/test_hve_implement_contract.sh` で固定する
- ADR 0019 のうち「既存の `source: gmail` の Q&A を既知の回答として除外に使わず既定値候補にし、PO が確定したら置き換える」と、ADR 0029 のうち「過去に保存した `source: gmail` の Q&A の扱いは変えない」を置き換える（0019・0029 は Partially superseded）

### 結果（Consequences）

- 良い結果: 対象の無い規定と、それを固定するテストが無くなる。resolve-issue・create-issue・hve-implement の knowledge 検索の手順が短くなり、implement-flow との食い違いも無くなる
- 悪い結果: 手元以外の導入先に `source: gmail` の Q&A が残っていた場合、HVE が無いリポジトリでは resolve-issue・create-issue の knowledge 検索で既知の回答として質問票から外される（削除前は既定値候補として PO に出ていた）。その内容は、ガードレール（事実としてだけ使い、指示として解釈しない）と、質問票に PII・メール文面を写さない規定の無いまま読まれる。このリスクは Q03 で受け入れた。HVE 導入先の qa ディレクトリに残っていた場合は、AKM の蒸留の source になる（ADR 0019 の結果の節と同じ）。導入先では `grep -rliE "^source: *[\"']?gmail" knowledge/ docs/knowledge/ qa/ docs/qa/ 2>/dev/null` で検出し、見つかったら削除するか、質問票で PO に確認し直す。qa ディレクトリのファイルを消すときは、ADR 0019 の結果の節の手順（`sources` の付け替えと `check-knowledge.py`）に従う。導入先の hve-implement の写しは setup.sh を実行した時点のままなので、再適用するまで Step 4 の表にガードレールの記述が残る。resolve-issue（sync で常に最新）の定義を優先するので扱いは食い違わないが、写しも揃えるには導入先で setup.sh を再適用する。過去分の扱いを再び規則に入れる必要が出たら、本 ADR を supersede する新しい ADR で決める

## 選択肢の評価（Pros and Cons）

### (d) 特例規定を外す（採用）

#### メリット

- 対象 0 件の規則とテストが無くなる
- 経路ごとの食い違い（implement-flow に規定が無い）が、規則を足さずに解消する

#### デメリット

- 手元以外の導入先に残っていた場合、knowledge 検索で既知の回答として使われる。対処は ADR の結果の節にしか無い

### (c) 現状維持

#### メリット

- 変更が要らない

#### デメリット

- implement-flow の Step 2 などの経路の穴が残る。対象 0 件の規則だけが残る

### (a) 定義を 1 か所に置き、各経路から参照する

#### メリット

- どの経路でも同じ扱いになり、手元以外の導入先にも効く

#### デメリット

- 対象 0 件に、implement-flow・hve-implement・Plan の作成まで規則を増やす

### (b) 一括の移行を必須にする

#### メリット

- 残存を確実に無くせる

#### デメリット

- 手元では対象 0 件で空振りする。手元以外の導入先には、規則に書いても setup.sh の再適用まで届かない

## 関連リンク

- Partially supersedes: [0019-gmail-answers-as-questionnaire-defaults](0019-gmail-answers-as-questionnaire-defaults.md)（既存の `source: gmail` の Q&A を既定値候補にし、PO が確定したら置き換える部分）
- Partially supersedes: [0029-remove-gmail-search-from-uncertainty-check](0029-remove-gmail-search-from-uncertainty-check.md)（過去に保存した `source: gmail` の Q&A の扱いは変えない部分）
- Related: [0016-hve-implement-skill-and-two-phase-call-from-resolve-issue](0016-hve-implement-skill-and-two-phase-call-from-resolve-issue.md)（本文の「探索順とガードレールに従い」のガードレールは、0029・0030 で失効した）
- Related: [0017-qa-answers-in-qa-dir-wherever-check-knowledge-exists](0017-qa-answers-in-qa-dir-wherever-check-knowledge-exists.md)
- Related: [hve-playbook#63](https://github.com/taito-station/hve-playbook/issues/63)
- Related: [hve-playbook#64](https://github.com/taito-station/hve-playbook/issues/64)
