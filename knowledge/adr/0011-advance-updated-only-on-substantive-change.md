# knowledge の updated は本文または status が実質的に変わったときだけ進める

## ステータス

Accepted — 2026-10-04

## 背景と課題

`skills/hve-akm/SKILL.md` の蒸留手順は「frontmatter の `updated` を当日日付に更新する」としていた。この書き方だと、下流の本文に効かない上流の変更（source の誤字修正など）で `distilled_from_sha` を追従させるときにも日付が進み、「いつ確定した知か」という信号が濁る。

導入先の paddock は、次の規則で運用し、hve-akm の写しに注記を足して差を吸収していた（paddock #754 の決定、hve-playbook #28）。setup.sh を再適用するたびにこの注記は消える。

- `updated` は下流の本文が実質的に変わったときだけ進める
- `updated` はダブルクォートで囲む
- 移設後の再ベースラインでは日付を据え置き、Conflict を宣言するときは `updated` だけ進める

あわせて、クォート必須の理由として挙げられていた「mdq の索引化が date 型で失敗する」は、HypervelocityEngineering 8ab5a42（`json.dumps(..., default=str)` の導入）より前の mdq でしか起きない。setup.sh が入れる現行の mdq では再現しない。

問い: `updated` の規則と例外規約を、標準にどこまで入れるか。

## 意思決定の要因

- `updated` が「内容を実質的に更新した日」を表すこと
- 導入先が hve-akm の写しを編集しなくて済むこと
- どの導入先にも当てはまる規則だけを標準に入れる（no-overengineering）
- 未確認の事実を標準に書かない（no-fabrication）

## 検討した選択肢

- 一般規則と Conflict 宣言の規約を標準に入れる
- 一般規則・Conflict 宣言・移設後の再ベースラインの 3 つを標準に入れる
- 一般規則とクォート必須だけを入れ、例外規約は入れない

## 決定内容

選択した選択肢: **一般規則と Conflict 宣言の規約を標準に入れる**。どちらもどの導入先でも起きる AKM の手順で、再ベースラインの中身は一般規則に含まれるため。

- `updated` は本文または status が実質的に変わったときだけ進め、`distilled_from_sha` だけの追従では触らない。判断の例示を 4 通り載せる
- 値はダブルクォート必須。理由は「YAML が date 型に解釈し、文字列を前提にした JSON 化や比較で型が揺れる。旧版 mdq では索引化が失敗した」とする
- Conflict の文書では `distilled_from_sha` を進めない。hve-akm は蒸留（Step 2）の後に Conflict を宣言する（Step 3）ので、同じ回の蒸留で進めた sha は元に戻す
- 規則の正本は `rules/hve/knowledge-maturity.md` に置き、`skills/hve-akm/SKILL.md` からは参照する

### 結果（Consequences）

- 良い結果: `updated` が確定時期の信号として使えるようになる。paddock の hve-akm の写しにある `updated` の注記のうち、汎用の部分は不要になる
- 悪い結果: 「実質的」の判断は人に残る。機械検査はできず、例示で揃えるしかない。既存の導入先は setup.sh を再適用するまで旧文言のまま

## 選択肢の評価（Pros and Cons）

### 一般規則と Conflict 宣言の規約を標準に入れる（採用）

#### メリット

- どの導入先でも当てはまる規則だけで済む
- Conflict 宣言時に sha を据え置く理由（解消時の差分マージの起点を残す）が標準に残る

#### デメリット

- paddock の「原因が移設だけの文書に限る」という限定は標準に無いので、paddock は override 側に残す必要がある

### 一般規則・Conflict 宣言・移設後の再ベースラインの 3 つを標準に入れる（却下）

#### メリット

- paddock の規則をそのまま写せる

#### デメリット

- 再ベースラインの中身（sha だけ進めて日付は据え置く）は一般規則に含まれる。個別の例外として足すと規則が重複する
- 「原因が移設だけの文書に限る」という限定は paddock 固有の移設の経緯に依存する

### 一般規則とクォート必須だけを入れ、例外規約は入れない（却下）

#### メリット

- 標準が最も短い

#### デメリット

- hve-akm は Step 2 で sha を進めてから Step 3 で Conflict を宣言するので、規約が無いと Conflict の文書の sha が進んだまま残り、解消時の差分マージの起点が失われる

## 関連リンク

- Related: [hve-playbook #28](https://github.com/taito-station/hve-playbook/issues/28)
- Related: [knowledge-maturity ルールの「`updated` の規則」](../../rules/hve/knowledge-maturity.md)
