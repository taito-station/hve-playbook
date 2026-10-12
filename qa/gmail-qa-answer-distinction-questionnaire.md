# Issue #56 Gmail 由来の回答を qa/ で PO の回答と区別する方式

- 対象スコープ: Issue #56: HVE 導入先で qa/ に置く Gmail 由来の Q&A と、PO の回答（questionnaire の qa/*.md）の扱いの区別
- 対象ドキュメント:
  - `skills/global/resolve-issue/SKILL.md`
  - `skills/global/create-issue/SKILL.md`
  - `skills/hve-implement/SKILL.md`
  - `skills/hve-akm/SKILL.md`
  - `rules/hve/knowledge-maturity.md`
- 関連スコープ: Issue #56（関連: #53、ADR 0016、ADR 0017）
- 生成: aqod（Issue #56 の implement-flow Step 4 で見つかったブロッキングな論点。Gmail 由来の回答を PO の確認を経ずに確定知にしない方式・示し方・AKM 側の扱いを決める）
- 状態: 回答済み
- 推論許可: 3 問とも人間判断（既定値は推奨解）
- 作成日: 2026-10-12
- 回答確定日: 2026-10-12
- 反映先: `knowledge/adr/` の新規 ADR、`rules/hve/knowledge-maturity.md`、`skills/hve-akm/SKILL.md`、`skills/global/resolve-issue/SKILL.md`、`skills/global/create-issue/SKILL.md`、`skills/hve-implement/SKILL.md`

## サマリー

現状、HVE 導入先では Gmail で見つけた回答を PO の回答と同じ qa ディレクトリに Q&A 書式（`slug / question / source / last_verified`）で置く（ADR 0016・0017）。SoT は `docs-original > qa（Confirmed 回答）> knowledge` で、hve-akm は qa/ を区別なく source とする。PO の確認を経ていない外部メール由来の回答が確定知として扱われないよう、方式・示し方・AKM 側の扱いを決める。

---

[Q01]
- 対象ドキュメント: rules/hve/knowledge-maturity.md
- 該当箇所: SoT（Single Source of Truth）優先順位
- 問題種別: 一貫性欠落
- 重大度: critical
- 質問内容: Gmail 由来の回答を PO の確認を経ずに確定知にしないための方式をどれにしますか？
- 選択肢: A) qa に置き続け、未確定であることを規則で示す。AKM は Gmail 由来だけを根拠に Confirmed にしない B) Gmail 由来は qa に置かず Issue コメントだけに記録する C) 現状維持とし、理由を ADR に残す
- 未回答時の既定値候補: A) qa に置き続け、未確定であることを規則で示す。AKM は Gmail 由来だけを根拠に Confirmed にしない
- 既定値候補の理由: 見つけた事実を捨てずに残せ、蒸留の source にもできる。既存の source フィールドで判別できるので書式の変更が小さい
- 未回答のまま進めた場合の影響: 変更する skill・rules・ADR の範囲が決まらない

[Q02]
- 対象ドキュメント: skills/global/resolve-issue/SKILL.md
- 該当箇所: Step 2 [feature] 項目 1 のナレッジファイルの形式
- 問題種別: 不明瞭
- 重大度: major
- 質問内容: (a) を選ぶ場合、qa のファイルで Gmail 由来（未確定）であることをどう示しますか？
- 選択肢: A) 既存の `source: gmail (日付)` を判定に使う（書式は変えない） B) frontmatter に status などの項目を追加する C) ファイル名に接頭辞を付ける
- 未回答時の既定値候補: A) 既存の `source: gmail (日付)` を判定に使う（書式は変えない）
- 既定値候補の理由: 既にある項目で判別でき、項目の追加を避けられる。既存の Gmail Q&A もそのまま判定に当たる
- 未回答のまま進めた場合の影響: AKM 側の判定条件と契約テストが書けない

[Q03]
- 対象ドキュメント: rules/hve/knowledge-maturity.md
- 該当箇所: SoT 優先順位・status の 3 段階、skills/hve-akm/SKILL.md Step 2
- 問題種別: 一貫性欠落
- 重大度: major
- 質問内容: (a) を選ぶ場合、AKM（蒸留・SoT）で Gmail 由来の qa をどう扱いますか？
- 選択肢: A) SoT の「qa（Confirmed 回答）」に含めない。蒸留は可だが、それだけを根拠にした内容は Tentative に留め、他の source と食い違えば他を優先する B) Tentative に留めるだけを定め、SoT の順位は変えない C) PO が確認するまで蒸留の source にしない
- 未回答時の既定値候補: A) SoT の「qa（Confirmed 回答）」に含めない。蒸留は可だが、それだけを根拠にした内容は Tentative に留め、他の source と食い違えば他を優先する
- 既定値候補の理由: 要件（PO の確認を経ずに確定知にしない）を、昇格と矛盾時の両面で満たす。既存の Tentative/Confirmed の仕組みを使い、新しい status を作らない
- 未回答のまま進めた場合の影響: Gmail 由来の回答と他の source が食い違ったときの扱いが決まらない

---

## 回答（確定 2026-10-12）

| No. | 回答 | 判断 | 根拠 |
|---|---|---|---|
| Q01 | **A) qa に置き続け、未確定であることを規則で示す。AKM は Gmail 由来だけを根拠に Confirmed にしない** | 既定値承認 | 見つけた事実を捨てずに残せ、蒸留の source にもできる。既存の source フィールドで判別できるので書式の変更が小さい（会話で「推奨」と回答） |
| Q02 | **A) 既存の `source: gmail (日付)` を判定に使う（書式は変えない）** | 既定値承認 | 既にある項目で判別でき、項目の追加を避けられる。既存の Gmail Q&A もそのまま判定に当たる（会話で「推奨」と回答） |
| Q03 | **A) SoT の「qa（Confirmed 回答）」に含めない。蒸留は可だが、それだけを根拠にした内容は Tentative に留め、他の source と食い違えば他を優先する** | 既定値承認 | 要件を昇格と矛盾時の両面で満たす。既存の Tentative/Confirmed の仕組みを使い、新しい status を作らない（会話で「推奨」と回答） |
