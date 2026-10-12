# Gmail 由来の qa の回答は、SoT で knowledge より下に置き、それだけでは Confirmed にしない

## ステータス

Accepted — 2026-10-12

## 背景と課題

HVE 導入先では、resolve-issue と create-issue が Gmail で見つけた質問の回答を、PO の回答と同じ qa ディレクトリに Q&A 書式（`slug / question / source / last_verified`）で置く（ADR 0016・0017）。

`rules/hve/knowledge-maturity.md` の SoT は `docs-original > qa（Confirmed 回答）> knowledge` で、`skills/hve-akm/SKILL.md` は `docs-original/` と `qa/` を区別せずに蒸留の source として扱う。このため、PO が確認していない外部メール由来の回答が、PO の回答と区別されないまま蒸留の source になりうる（[hve-playbook#56](https://github.com/taito-station/hve-playbook/issues/56)。#53 のセルフレビューの Security 指摘から切り出した）。

問い: Gmail 由来の回答が PO の確認を経ずに確定知として扱われないようにするには、どの方式を採り、Gmail 由来であることをどう示し、AKM ではどう扱うか。

## 意思決定の要因

- Gmail 由来の回答が、PO の確認を経ずに確定知（`Confirmed`）にならない
- 見つけた事実を捨てない（蒸留の source として使える）
- Q&A 書式・status・検査スクリプトを増やさない（オーバーエンジニアリングをしない）
- resolve-issue・create-issue・hve-implement の扱いが食い違わない
- ADR 0016・0017 の決定（Gmail の回答も qa に置く。qa は回答の探索対象に加えない）と整合する

## 検討した選択肢

- 方式 (a): qa に置き続け、未確定であることを規則で示す。AKM は Gmail 由来だけを根拠に Confirmed にしない
- 方式 (b): Gmail 由来は qa に置かず、Issue コメントだけに記録する
- 方式 (c): 現状維持とし、理由を ADR に残す
- 示し方（(a) の場合）: 既存の `source: gmail (YYYY-MM-DD)` で判定する／frontmatter に status などの項目を追加する／ファイル名に接頭辞を付ける
- AKM での扱い（(a) の場合）: SoT で knowledge より下に置き、それだけを根拠にした記述を含む文書は Tentative に留める／Tentative に留めることだけを定める／PO が確認するまで蒸留の source にしない

## 決定内容

選択した選択肢: **方式 (a)。既存の `source: gmail (YYYY-MM-DD)` で判定し、SoT で knowledge より下に置き、それだけを根拠にした記述を含む文書は Tentative に留める**。Issue #56 の質問票（`qa/gmail-qa-answer-distinction-questionnaire.md`）で、3 問とも推奨解のとおり確定した。

- `rules/hve/knowledge-maturity.md` の SoT を `docs-original > qa（Confirmed 回答）> knowledge > qa（Gmail 由来の回答）` とする。Gmail 由来の回答は蒸留の source にしてよい。他の source・knowledge と食い違っても `Conflict` を宣言せず、上位を採って報告する
- 同じファイルの「status の 3 段階」で、Gmail 由来の qa だけを根拠にした記述を含む文書は、文書全体を `Tentative` に留める（status は文書単位）。その記述を PO が確認したら `Confirmed` にしてよい。確認の経路は既存の 2 つ（questionnaire の qa に回答として記録する、ユーザーのレビュー承認でその記述を確認する）を使う
- `skills/hve-akm/SKILL.md` の Step 2（蒸留）と Step 3（矛盾検出時の対応）は、この扱いを参照する
- resolve-issue の feature 前処理（前段の規則の Gmail の回答の保存先）に、Gmail の回答は PO の回答ではない（未確定の回答）こと、AKM での扱いは knowledge-maturity に従うことを書く。create-issue と hve-implement は resolve-issue の定義を指す
- 効果は AKM の側（確定知への昇格と SoT）に限る。Issue 対応中に Gmail の回答を Plan の前提に使う扱いは変えない（feature の Plan は PO の承認を経る）
- 契約は `tests/test_qa_answer_destination.sh` で固定する。ADR は番号でなく slug で探す

### 結果（Consequences）

- 良い結果: Gmail 由来の回答が PO の確認なしに Confirmed にならない。また、矛盾したときに PO の回答や一次資料に勝つこともない。書式は変えずに既存の `source` で判定するので、すでに qa にある Gmail の Q&A にもそのまま効く。昇格の経路は既存のものを使い、新しい status や手順を作らない
- 悪い結果: Gmail 由来の記述を 1 つでも含む文書は、PO がその記述を確認するまで文書全体が Tentative に留まる。HVE が無いリポジトリで `knowledge/<domain>/` に置いた Gmail の Q&A は対象外で、次の Issue で既知ナレッジとして PO の回答と同列に使われ続ける（qa と AKM が無いため）。resolve-issue・create-issue（sync で常に最新）は導入先の写し（`.claude/rules/hve/knowledge-maturity.md`・`.claude/skills/hve-akm/`）を参照するので、導入先で setup.sh を再適用するまでは、写しにこの扱いが無い

## 選択肢の評価（Pros and Cons）

### 方式 (a): qa に置き、未確定であることを規則で示す（採用）

#### メリット

- 見つけた事実を残し、蒸留の source として使える
- ADR 0016・0017 の決定（Gmail の回答も qa に置く）を変えずに済む

#### デメリット

- AKM の規則（SoT・昇格・矛盾時）に書き足す箇所が増える

### 方式 (b): qa に置かず Issue コメントだけに記録する

#### メリット

- 規則が最も単純で、qa に未確定の回答が入らない

#### デメリット

- 見つけた事実が AKM の source にならず、次の蒸留で使えない
- ADR 0017 の決定（Gmail の回答も qa に置く）を覆す

### 方式 (c): 現状維持

#### メリット

- 変更が無い。初回蒸留は Tentative で、昇格にはレビュー承認が要る

#### デメリット

- 規則の字面では、Gmail の Q&A が PO の回答と同じ「qa」になり、SoT で knowledge より上に立つ。要件を満たさない

### 示し方: frontmatter に status などの項目を追加／ファイル名に接頭辞

#### メリット

- 未確定であることがファイル単体で明示的に見える

#### デメリット

- 既存の `source` で判別できるのに、書式・既存ファイル・テストの変更が増える。接頭辞は規則を命名に依存させる

### AKM での扱い: Tentative に留めることだけを定める／蒸留の source にしない

#### メリット

- 前者は書き足しが少ない。後者は未確定の内容が knowledge に入らない

#### デメリット

- 前者は矛盾したときの扱いが決まらない。後者は見つけた事実を蒸留に使えず、方式 (b) と同じ欠点を持つ

## 関連リンク

- Extends: [0017-qa-answers-in-qa-dir-wherever-check-knowledge-exists](0017-qa-answers-in-qa-dir-wherever-check-knowledge-exists.md)
- Related: [0016-hve-implement-skill-and-two-phase-call-from-resolve-issue](0016-hve-implement-skill-and-two-phase-call-from-resolve-issue.md)
- Related: [hve-playbook#56](https://github.com/taito-station/hve-playbook/issues/56)
- Related: [hve-playbook#53](https://github.com/taito-station/hve-playbook/issues/53)
