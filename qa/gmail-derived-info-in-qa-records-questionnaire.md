# Issue #64 質問票の記録に載る Gmail 由来の情報の扱い

- 対象スコープ: Issue #64: resolve-issue / create-issue の Gmail 検索 → 質問票 → qa/*.md
- 対象ドキュメント:
  - `skills/global/resolve-issue/SKILL.md`
  - `skills/global/create-issue/SKILL.md`
  - `skills/global/questionnaire/SKILL.md`
  - `skills/hve-implement/SKILL.md`
  - `tests/test_qa_answer_destination.sh`
  - `tests/test_hve_implement_contract.sh`
- 関連スコープ: #56（ADR 0019）、#63（過去の source: gmail の Q&A）
- 生成: aqod（Issue #64 の implement-flow Step 4 で見つかったブロッキングな論点。Gmail 検索の仕組みの要否、PUBLIC リポジトリでの機密な業務情報の扱い、送信元の区分を決める）
- 状態: 回答済み
- 推論許可: すべて人間判断（既定値は推奨として提示）
- 作成日: 2026-10-25
- 回答確定日: 2026-10-31
- 反映先: `knowledge/adr/0029-remove-gmail-search-from-uncertainty-check.md`（新規）、`knowledge/adr/0019-gmail-answers-as-questionnaire-defaults.md`（ステータス）、`knowledge/adr/README.md`、`skills/global/resolve-issue/SKILL.md`、`skills/global/create-issue/SKILL.md`、`skills/hve-implement/SKILL.md`、`tests/test_qa_answer_destination.sh`、`tests/test_hve_implement_contract.sh`

## サマリー

resolve-issue・create-issue は Gmail で見つけた事実を質問票の既定値候補とその理由（「Gmail（日付）に記載: …」）として示し、questionnaire skill がそれを git 管理の qa/*.md に残す（ADR 0019）。PUBLIC リポジトリでは公開される。抽出時の除外は個人情報とメール文面だけが対象で、機密な業務情報と送信元の区分は定めていない。Gmail 検索の仕組みそのものの要否を含めて決める。

---

[Q01]
- 対象ドキュメント: skills/global/resolve-issue/SKILL.md
- 該当箇所: Step 2 [feature] 項目 1 の手順 2（Gmail 検索）、create-issue の 1.5 の 3 の手順 2
- 問題種別: 前提の確認（仕組みの要否）
- 重大度: major
- 質問内容: resolve-issue・create-issue の不確定点チェックで、Gmail から回答候補を探す手順を続けますか？
- 選択肢: A) 外す（Gmail 検索の手順と allowed-tools の Gmail を削除。探索は knowledge → PO の質問票の 2 段に） B) 続ける（Q2・Q3 で機密情報と送信元の扱いを決める） C) 既定では行わず、PO が Issue 対応時に明示したときだけ行う
- 未回答時の既定値候補: A) 外す（Gmail 検索の手順と allowed-tools の Gmail を削除。探索は knowledge → PO の質問票の 2 段に）
- 既定値候補の理由: 使われた形跡が見つからない。外せば公開リスクが原理的に無くなり、機密・送信元の規則を足さずに済む（規則を増やさない。ADR 0019 の要因と同じ）。必要になったら別 Issue で戻せる
- 未回答のまま進めた場合の影響: 続けるか外すかで、規則の変更範囲（機密・送信元の規則を足すのか、手順を消すのか）が変わる

[Q02]
- 対象ドキュメント: skills/global/resolve-issue/SKILL.md
- 該当箇所: Step 2 [feature] 項目 1 の手順 2 の抽出時の除外
- 問題種別: 重大な欠落
- 重大度: major
- 質問内容: Q1 で「続ける」「明示したときだけ」を選んだ場合、PUBLIC リポジトリで機密な業務情報（契約条件・金額など）をどう扱いますか？
- 選択肢: A) PUBLIC リポジトリでは機密な業務情報も除外し、要約の粒度に留める B) PUBLIC リポジトリでは Gmail の事実を既定値候補にしない C) 現状維持（questionnaire skill の「公開リポジトリでは .gitignore するか非公開リポで運用する」の注意に任せる）
- 未回答時の既定値候補: A) PUBLIC リポジトリでは機密な業務情報も除外し、要約の粒度に留める
- 既定値候補の理由: PO の判断材料を残しつつ、公開リスクを抑えられる。除外の規則に 1 項目足すだけで済む
- 未回答のまま進めた場合の影響: PUBLIC リポジトリの qa/*.md に取引先の契約条件などが公開されうる

[Q03]
- 対象ドキュメント: skills/global/resolve-issue/SKILL.md
- 該当箇所: Step 2 [feature] 項目 1 の手順 2 の defaultReason の書式
- 問題種別: 不明瞭
- 重大度: minor
- 質問内容: Q1 で「続ける」「明示したときだけ」を選んだ場合、既定値候補の理由に送信元の区分（社内／取引先などの、個人を特定しない区分）を加えますか？
- 選択肢: A) 加える（例: 「Gmail（YYYY-MM-DD、社外）に記載: …」） B) 加えない
- 未回答時の既定値候補: A) 加える（例: 「Gmail（YYYY-MM-DD、社外）に記載: …」）
- 既定値候補の理由: 個人を特定せずに、PO が出所の信頼度を判断できる。書式の変更が小さい
- 未回答のまま進めた場合の影響: PO が既定値候補の信頼度を判断する材料が無い

---

## 回答（確定 2026-10-31）

| No. | 回答 | 判断 | 根拠 |
|---|---|---|---|
| Q01 | **外す（Gmail 検索の手順と allowed-tools の Gmail を削除。探索は knowledge → PO の質問票の 2 段に）** | 既定値承認 | 使われた形跡が見つからない。外せば公開リスクが原理的に無くなり、機密・送信元の規則を足さずに済む（会話で「1 はずす」と回答） |
| Q02 | **不要（Q01 で Gmail 検索を外すため）** | 人間判断 | Q01 の回答に伴う |
| Q03 | **不要（Q01 で Gmail 検索を外すため）** | 人間判断 | Q01 の回答に伴う |
