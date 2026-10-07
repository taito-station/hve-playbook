# HVE 導入先では、質問の回答を経路を問わず qa/ に残す

## ステータス

Accepted — 2026-10-07

## 背景と課題

ADR 0016 は、resolve-issue が hve-implement の前段（`--phase pre`）を呼ぶときだけ、質問の回答を `knowledge/<domain>/` ではなく `qa/` に残すと決めた。前段を呼ばない経路は対象外で、HVE 導入先でも次の 2 つは従来どおり `knowledge/<domain>/` に Q&A 書式（`slug / question / source / last_verified`）で書いていた。

- resolve-issue の feature パスで前段を呼ばないとき（導入先に hve-implement が無い、または implement-flow の対象外の変更）
- create-issue の質問票ゲート

check-knowledge.py は `knowledge/` を再帰的に走査し、必須項目（`title,status,kind,sources,distilled_from_sha,updated`）を欠く Q&A のファイルを error にする（[hve-playbook#53](https://github.com/taito-station/hve-playbook/issues/53)。ADR 0016 の「悪い結果」に既知の制約として記録していた）。

問い: 前段を呼ばない経路で、HVE 導入先かどうかを何で判定し、回答をどこに残すか。

## 意思決定の要因

- HVE 導入先で、どの経路を通っても check-knowledge.py が回答のファイルで error にならない
- HVE が無いリポジトリでは、回答の保存先と書式を変えない
- resolve-issue と create-issue の Q&A の扱いが食い違わない
- ADR 0016 の決定（前段の回答は `qa/` に残し、PO の回答は questionnaire skill の `qa/*.md` を正とする。knowledge には AKM の蒸留で入れる）と整合する

## 検討した選択肢

- 判定: 検査スクリプト（`.claude/scripts/hve/check-knowledge.py` か `hve-scripts/check-knowledge.py`）の有無
- 判定: `.claude/rules/hve/` の有無
- 判定: `.claude/skills/hve-implement/SKILL.md` の有無（前段を呼ぶ条件と同じ）
- check-knowledge.py の側で Q&A のファイルを除外し、`knowledge/<domain>/` への書き込みを続ける

## 決定内容

選択した選択肢: **検査スクリプトの有無で判定し、HVE 導入先では回答を経路を問わず `qa/` に残す**。

- resolve-issue Step 2 [feature] 項目 1 に規則を定義する。`.claude/scripts/hve/check-knowledge.py`（導入先）か `hve-scripts/check-knowledge.py`（hve-playbook 自身）があれば HVE 導入先とみなし、`knowledge/` の有無に関わらず、手順 2（Gmail の回答）と 4（PO の回答）を `knowledge/<domain>/` に書かない
- 保存先は前段と同じで、前段の規則（resolve-issue の feature 前処理の冒頭）を正本とする。PO の回答は questionnaire skill が書く `qa/*.md` を正とし（手順 4 は Issue コメントへの反映だけ）、Gmail の回答は同じ qa ディレクトリに Q&A 書式と PII の規則のまま置く
- create-issue の質問票ゲートは、判定と保存先を resolve-issue の定義に従う
- `qa/` を回答の探索対象に加えない（ADR 0016 のとおり、knowledge には AKM の蒸留で入れる）
- 契約は `tests/test_qa_answer_destination.sh` で固定する

### 結果（Consequences）

- 良い結果: HVE 導入先では、前段を呼ぶかどうかや create-issue かどうかに関わらず、回答のファイルで check-knowledge.py が error にならない。判定が error の原因（検査スクリプト）そのものなので、hve-implement を配る前の古い導入先でも効く。判定の場所は hve-implement の Step 7 が検査スクリプトを探す場所と同じ
- 悪い結果: HVE 導入先では、`qa/` に置いた回答は AKM で蒸留するまで次の Issue の探索（`knowledge/<domain>/` の検索）にかからない。検査スクリプトを置かずに `knowledge/` だけを使う HVE 導入先は判定に当たらず、従来どおり `knowledge/<domain>/` に書く（その場合は検査が無いので error にもならない）。Gmail から見つけた回答も PO の回答と同じ qa ディレクトリに入り、AKM の source としては区別されない（ADR 0016 の前段から引き継いだ扱い。区別するかは [hve-playbook#56](https://github.com/taito-station/hve-playbook/issues/56) で扱う）

## 選択肢の評価（Pros and Cons）

### 検査スクリプトの有無（採用）

error の原因である検査スクリプト（`.claude/scripts/hve/check-knowledge.py` か `hve-scripts/check-knowledge.py`）があるかで判定する。

#### メリット

- error の原因そのものを見るので、判定に当たる・当たらないと error になる・ならないが一致する
- hve-implement を配る前の古い導入先でも効く

#### デメリット

- 検査スクリプトの置き場所が変わったら、判定の記述も直す必要がある

### `.claude/rules/hve/` の有無

HVE の規約を配ったかどうかで判定する。

#### メリット

- HVE を導入したかどうかを直接見る

#### デメリット

- 検査スクリプトを持たない古い導入先でも `qa/` に回り、error にならない環境で保存先だけが変わる

### `.claude/skills/hve-implement/SKILL.md` の有無

前段を呼ぶ条件と同じ判定を使う。

#### メリット

- 前段を呼ぶ条件と同じで、判定が 1 つで済む

#### デメリット

- hve-implement を配っていない導入先は判定に当たらず、検査スクリプトがあれば check-knowledge.py の error が残る

### check-knowledge.py で Q&A のファイルを除外する

skill の保存先は変えず、検査の側で Q&A 書式のファイルを対象から外す。

#### メリット

- skill の保存先を変えずに済む

#### デメリット

- knowledge には AKM の蒸留で入れるという ADR 0016 の決定と食い違い、蒸留していない Q&A が `knowledge/` に残り続ける

## 関連リンク

- Related: [0014-knowledge-check-scripts-and-sha-follow-up](0014-knowledge-check-scripts-and-sha-follow-up.md)
- Related: [0016-hve-implement-skill-and-two-phase-call-from-resolve-issue](0016-hve-implement-skill-and-two-phase-call-from-resolve-issue.md)
- Related: [hve-playbook#53](https://github.com/taito-station/hve-playbook/issues/53)
- Related: [hve-playbook#56](https://github.com/taito-station/hve-playbook/issues/56)
