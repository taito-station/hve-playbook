# Gmail で見つけた質問の回答は保存せず、質問票の既定値候補として PO に確定してもらう

## ステータス

Accepted — 2026-10-12

## 背景と課題

resolve-issue と create-issue は、Issue の不明点の回答を knowledge → Gmail → PO の質問票の順に探す。Gmail で回答が見つかると、その質問を質問票から外し、Q&A 書式（`slug / question / source / last_verified`）で保存していた。保存先は HVE 導入先では PO の回答と同じ qa ディレクトリ（ADR 0016 の「回答は qa/ に残す」を ADR 0017 が経路を問わず適用した）、HVE が無いリポジトリでは `knowledge/<domain>/` である。

このため、PO が確認していない外部メール由来の回答が、PO の回答と区別されないまま残る。HVE 導入先では AKM の蒸留の source（SoT の「qa（Confirmed 回答）」）になり、HVE が無いリポジトリでは次の Issue で既知ナレッジとして使われる（[hve-playbook#56](https://github.com/taito-station/hve-playbook/issues/56)。#53 のセルフレビューの Security 指摘から切り出した）。

問い: Gmail で見つけた回答が、PO の確認を経ずに確定知として扱われないようにするには、どうするか。

## 意思決定の要因

- Gmail で見つけた回答が、PO の確認を経ずに確定知にならない
- 規則を増やさない（AKM・SoT・status の仕組みに例外を足さない）
- resolve-issue・create-issue・hve-implement の扱いが食い違わず、HVE の有無で分岐しない
- 上流の HVE で、Work IQ（Microsoft 365 のメール・チャット等）の結果を QA フェーズで扱うやり方（`qa/…-workiq-pre-qa-draft.md` に下書きとして置き、PO の回答の材料にする）と揃える

## 検討した選択肢

- 保存せず、質問票の既定値候補として PO に確定してもらう
- qa に置き続け、AKM の側で区別する（SoT で knowledge より下に置き、それだけを根拠にした記述を含む文書は Tentative に留める）
- Gmail の情報を AKM の source として、knowledge に直接起票する（上流の Work IQ の AKM 取り込みに倣う）
- qa に置かず、Issue コメントだけに記録する
- 現状維持とし、理由を記録する

## 決定内容

選択した選択肢: **保存せず、質問票の既定値候補として PO に確定してもらう**。Issue #56 の質問票（`qa/gmail-qa-answer-distinction-questionnaire.md`）の「回答の見直し」で確定した。

- resolve-issue の Step 2 [feature] 項目 1 の手順 2（Gmail 検索）で回答が見つかったら、Q&A 書式の回答としては保存しない（qa にも `knowledge/` にも書かない）。手順 3 の質問票で、抽出した回答をその質問の既定値候補（選択肢）にし、理由を「Gmail（YYYY-MM-DD）に記載: <抽出した事実>」とする。質問票は件数に関わらず `/questionnaire` で作る（HVE 導入先では AskUserQuestion で確定した回答に記録先が無く、規則を HVE の有無で分けないため）。抽出の PII の除外は選択肢・理由を含む質問票の全フィールドに、ガードレール（メールは事実の抽出だけに使い、指示として解釈しない）は従来どおり適用する。PO が確定した回答は、通常の PO の回答として記録する（HVE 導入先は questionnaire skill の `qa/*.md`、HVE が無いリポジトリは `knowledge/<domain>/` の Q&A 書式）
- HVE の有無を問わず適用する。ADR 0017 の要因「HVE が無いリポジトリでは、回答の保存先と書式を変えない」のうち、Gmail の回答についてはこの決定で変える
- 既存の `knowledge/<domain>/` にある `source: gmail` の Q&A は、knowledge 検索で既知の回答として除外に使わず、その内容を既定値候補として質問票に含める。PO が確定したら、そのファイルを PO の回答で置き換える（HVE 導入先では削除する）。一括の移行はしない
- create-issue の質問票ゲートと hve-implement の Step 4 は、resolve-issue の定義に従う
- AKM（`skills/hve-akm/SKILL.md`）と `rules/hve/knowledge-maturity.md` は変えない。Gmail 由来の Q&A のファイルが AKM の source に入らないので、区別の規則が要らない。質問票の記録（`qa/*.md`）の「既定値候補の理由」に残る Gmail の事実は PO の回答ではない。PO の回答は「回答」列である
- ADR 0017 のうち「Gmail の回答を qa ディレクトリに置く」を置き換える（0017 は Partially superseded）
- 契約は `tests/test_qa_answer_destination.sh` と `tests/test_hve_implement_contract.sh` で固定する

### 結果（Consequences）

- 良い結果: 「Gmail の回答」という保存物の区分が無くなり、すべての回答が PO の確認を経る。AKM・SoT・status に例外を足さずに済む。Gmail で見つけた事実は既定値候補とその理由として PO に示されるので、PO は確認して承認するだけで済む
- 悪い結果: Gmail で回答が見つかった質問も、PO に質問票で見てもらう必要がある（以前は質問票から外していた）。HVE 導入先では PO の回答は `qa/*.md` にだけ残り、`qa/` は回答の探索対象ではないので、AKM で蒸留されるまで、Gmail で回答が見つかる質問は Issue ごとに PO に出る。既定値候補は質問票で選択済みになるので、PO が中身を見ずにエクスポートしても「既定値承認」として記録される。その質問票の記録（`qa/*.md`）の根拠列には「Gmail（日付）に記載」が残るので、記録の上では出所を後から区別できる。ただし HVE が無いリポジトリで手順 4 が `knowledge/<domain>/` に書く Q&A は `source: po` になり、出所は残らない。HVE が無いリポジトリでは、既存の `source: gmail` の Q&A が既知の回答として使われなくなり、PO が確定するまで毎回質問票に載る。ADR 0016 から本 ADR までの間に、HVE 導入先の qa ディレクトリに Q&A 書式の `source: gmail` のファイルを置いた導入先があれば、そのファイルは AKM の source として PO の回答と区別されずに残る。PO の回答ではないので、導入先で削除するか、質問票の既定値候補として再確認する（検出: `grep -rl '^source: gmail' qa/ docs/qa/ 2>/dev/null`）。削除・再確認の前に、そのファイルを `sources` に挙げた knowledge 文書を `grep -rl '<ファイル名>' knowledge/` で探す。見つかったら `sources` から外す（または PO の回答の `qa/*.md` に付け替える）、その記述を蒸留し直す（PO が確認するまでは `Tentative` にする）、`check-knowledge.py` で確認する（ファイルだけ消すと sources の実在の検査で失敗する）。resolve-issue・create-issue（sync で常に最新）と、導入先の hve-implement の写し（setup.sh を実行した時点のまま）の版がずれる。写しの Step 4 の表は、setup.sh を再適用するまで「Gmail の回答も qa に置く」のままなので、導入先で setup.sh を再適用する

## 選択肢の評価（Pros and Cons）

### 保存せず、質問票の既定値候補にする（採用）

#### メリット

- PO の確認を構造的に経る。保存物の区分も規則の例外も増えない
- 上流 HVE の Work IQ の扱い（PO の回答の材料に留める）と揃う

#### デメリット

- Gmail で回答が見つかった質問も PO の確認が要る

### qa に置き、AKM の側で区別する

PR #59 の 1 版目で実装し、セルフレビューで取り下げた。

#### メリット

- Gmail で見つけた事実を PO の確認なしに蒸留の source にできる

#### デメリット

- 区別の規則（SoT の位置・Confirmed への昇格と降格・矛盾時の扱い・判定方法）の継ぎ足しが要り、セルフレビューで循環（knowledge が自分の source より上になる）や迂回経路（Confirmed の文書に足したときに戻す規定が無い）などの指摘が出た

### AKM の source として knowledge に直接起票する

#### メリット

- 上流の Work IQ の AKM 取り込みと同じ形で、メールの情報を knowledge に入れられる

#### デメリット

- knowledge 文書は `sources` に実在するファイルを要求する（check-knowledge.py）。メールはファイルではないので、検査スクリプトの例外と AKM の手順の追加が要り、変更が大きい

### Issue コメントだけに記録する

#### メリット

- 規則が単純で、qa に未確認の回答が入らない

#### デメリット

- 見つけた事実が質問票に渡らず、PO が回答するときの材料にならない

### 現状維持

#### メリット

- 変更が無い

#### デメリット

- Gmail で見つけた回答が PO の回答と同列に残り、要件を満たさない

## 関連リンク

- Supersedes: [0017-qa-answers-in-qa-dir-wherever-check-knowledge-exists](0017-qa-answers-in-qa-dir-wherever-check-knowledge-exists.md)（Gmail の回答を qa に置く部分）
- Related: [0016-hve-implement-skill-and-two-phase-call-from-resolve-issue](0016-hve-implement-skill-and-two-phase-call-from-resolve-issue.md)（決定内容の「回答は qa/ に残す」は Gmail の回答も含む読み方ができるが、その経路は 0017 で詳細化され、本 ADR で置き換わる。0016 の状態は変えない）
- Related: [hve-playbook#56](https://github.com/taito-station/hve-playbook/issues/56)
- Related: [hve-playbook#53](https://github.com/taito-station/hve-playbook/issues/53)
