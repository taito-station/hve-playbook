# 決定ログは独立ファイル方式を既定とし、インライン方式を宣言で選べるようにする

## ステータス

Accepted — 2026-10-04

## 背景と課題

`rules/hve/artifact-management.md` の「決定ログの不変性」は、`knowledge/adr/` に 1 決定 1 ファイルで置く独立ファイル方式だけを定めていた。導入先の paddock は、決定を各 `knowledge/*.md` の末尾の `## 決定ログ` 節に追記するインライン方式で運用している。そのため paddock は rules/hve の写しに注記を足しており、setup.sh を再適用するたびに注記が消えていた（[taito-station/paddock#754](https://github.com/taito-station/paddock/issues/754)、[hve-playbook#26](https://github.com/taito-station/hve-playbook/issues/26)）。

標準の中にも矛盾があった。

- append-only の検査 `git diff origin/main..HEAD -- knowledge/adr/ | grep '^-'` はすべての削除行を違反として拾う。一方、documentation-standards の作成手順は、supersede のときに旧 ADR のステータスを書き換えるよう求めている。このリポジトリでも ADR-0007 のステータス書き換え（96f73b1）がこの検査に掛かる
- 検査が 2 ドット比較なので、作業ブランチを切ったあとに main へ入った ADR が削除行として出る

問い: 決定ログの置き方を導入先が選べるようにしつつ、append-only の規則と supersede の手順をどう両立させるか。

## 意思決定の要因

- 独立ファイル方式の既存の導入先の動作を変えない
- インライン方式の導入先が、rules/hve の写しを編集せずに運用できる
- インライン方式のエントリは追記のみで、既存のエントリを後から直せない
- 旧 ADR を読んだ人が、その決定が失効していることに気づける

## 検討した選択肢

- 独立ファイル方式を既定とし、インライン方式を hve-local の宣言で選べるようにする。書き換えてよい範囲は方式ごとに定める
- インライン方式にも MADR の章立てとステータス値を強いる
- supersede を新しいエントリの追加だけで表し、独立ファイル方式でもステータスの書き換えを禁止する

## 決定内容

選択した選択肢: **独立ファイル方式を既定とし、インライン方式を hve-local の宣言で選べるようにする**。既定の動作を変えずに、paddock の写しの注記を不要にできる。

- 配置: 独立ファイル方式が既定で、宣言は要らない。インライン方式は `.claude/rules/hve-local/artifact-management.md` で「配置」を補足して宣言する（ADR-0012 の仕組み）
- 書き換えてよい範囲: 独立ファイル方式は、旧 ADR の `## ステータス` 節、一覧 README のステータス列、誤字修正。インライン方式は追記のみで、誤字修正もしない。supersede は新しいエントリで表す
- 書式: インライン方式は見出し `### <ID>: 要約 (YYYY-MM-DD) — ステータス` と `####` の節で書く。節と MADR の章の対応表を rules に置く。新しいエントリはコンテキスト・決定・理由・影響を書き、代替案を検討したら却下した代替案も書く。表にない節は足してよく、規則より前のエントリには遡って適用しない
- ID とステータス語: インライン方式の ID の既定は `ADR NNNN` で、導入先は別の形式と採番（issue 番号など）を宣言してよい。ステータス語の既定は documentation-standards のステータス値で、導入先は方式を問わず独自の語を定めてよい。ステータス値に対応する語は対応も書く
- 検査: merge-base 基準（3 ドット）の diff を使う。許された範囲かどうかの判定は人が行う。機械判定のスクリプトは #27 で扱う

ADR-0001 は「プロジェクト独自フォーマット」を却下している。これは、標準が新しく書く ADR の様式を決めたもの。インライン方式は、すでにその方式で運用している導入先が続けるための opt-in で、既定の様式は MADR のまま変わらない。そのため ADR-0001 と衝突しない。

この決定により、ADR-0007 のステータス書き換え（96f73b1）は正規の操作になる。

### 結果（Consequences）

- 良い結果: 独立ファイル方式の導入先は何も変えずに済む。インライン方式の導入先は hve-local に宣言を書くだけで、rules/hve と矛盾せずに運用できる。supersede の手順と append-only の規則が両立する。2 ドット比較の偽陽性がなくなる
- 悪い結果: 規則が方式ごとに分かれ、読む量が増える。独立ファイル方式の誤字修正と、インライン方式の改変が `## 決定ログ` 節の中かどうかは、手検査では人の判定に頼る

## 選択肢の評価（Pros and Cons）

### 独立ファイル方式を既定とし、インライン方式を宣言で選べるようにする（採用）

#### メリット

- 既定の動作が変わらない
- 宣言の置き場所に hve-local をそのまま使える

#### デメリット

- 方式ごとの規則を読む必要がある

### インライン方式にも MADR の章立てとステータス値を強いる（却下）

#### メリット

- 様式が 1 つで済む

#### デメリット

- インライン方式は追記のみなので、既存のエントリを直せない。導入先の写しの注記が残り、課題が解消しない

### supersede を新しいエントリだけで表し、ステータスの書き換えを禁止する（却下）

#### メリット

- 検査が単純になる（すべての削除行が違反）

#### デメリット

- documentation-standards の双方向更新と一覧 README の運用が崩れる。旧 ADR を読んだ人が失効に気づけない

## 関連リンク

- Related: [0001-adopt-madr-format-for-adrs](0001-adopt-madr-format-for-adrs.md)
- Related: [0004-audit-prompts-for-opus-5-5](0004-audit-prompts-for-opus-5-5.md)
- Related: [0007-consolidate-user-level-rules-and-agents](0007-consolidate-user-level-rules-and-agents.md)
- Related: [0012-project-local-overrides-in-hve-local](0012-project-local-overrides-in-hve-local.md)
- Related: [artifact-management ルール](../../rules/hve/artifact-management.md)
