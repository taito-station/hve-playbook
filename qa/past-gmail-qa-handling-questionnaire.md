# 過去に保存した source: gmail の Q&A の扱い（Issue #63）

- 対象スコープ: resolve-issue / create-issue / hve-implement の source: gmail の特例規定と、implement-flow Step 2 の knowledge 検索
- 対象ドキュメント:
  - `skills/global/resolve-issue/SKILL.md`
  - `skills/global/create-issue/SKILL.md`
  - `skills/hve-implement/SKILL.md`
  - `rules/global/workflow/implement-flow.md`
  - `rules/hve/implement-flow.md`
  - `tests/test_qa_answer_destination.sh`
  - `knowledge/adr/`
- 関連スコープ: hve-playbook#63（関連: #56・#64、ADR 0019・0029）
- 生成: aqod（Issue #63 の未決事項（方式・qa/*.md の写しの扱い）を決める）
- 状態: 回答済み
- 推論許可: 方式は人間判断。既定値候補は手元の実在調査（0 件）に基づく
- 作成日: 2026-10-31
- 回答確定日: 2026-10-31
- 反映先: `knowledge/adr/0030-drop-past-gmail-qa-special-rules.md`（新規）、`knowledge/adr/0019-gmail-answers-as-questionnaire-defaults.md`（ステータス）、`knowledge/adr/0029-remove-gmail-search-from-uncertainty-check.md`（ステータス）、`knowledge/adr/README.md`、`skills/global/resolve-issue/SKILL.md`、`skills/global/create-issue/SKILL.md`、`skills/hve-implement/SKILL.md`、`tests/test_qa_answer_destination.sh`、`tests/test_hve_implement_contract.sh`

## サマリー

Gmail の回答を `knowledge/<domain>/` に `source: gmail` で保存する手順は、2026-09-21（9e53552）〜2026-10-12（eea0cb3）の約 3 週間だけ存在した。`knowledge/` を持つ手元の全リポジトリ（hve-playbook を含む 6 本）で、`source: gmail` の Q&A は作業ツリーにも git 履歴にも 0 件。Gmail 検索そのものは ADR 0029 で廃止済み。この事実を踏まえ、過去分の扱いの方式と、qa/*.md に残る写しの扱いを決める。

---

[Q01]
- 対象ドキュメント: skills/global/resolve-issue/SKILL.md
- 該当箇所: Step 2 [feature] 項目 1
- 問題種別: 一貫性欠落
- 重大度: major
- 質問内容: 過去に保存した source: gmail の Q&A を、どの方式で扱いますか？
- 選択肢: A) (d) 特例規定を全部削除し、実在 0 件の確認と理由を ADR に残す（規則・テストが減る。万一残っていた導入先では通常の Q&A として扱われうる） B) (c) 現状維持（特例規定は残し、ADR だけ書く。implement-flow 側の穴は残る） C) (a) 未確認扱いの定義を 1 か所に置き、implement-flow Step 2・hve-implement・Plan 作成からも参照する（規則が増える） D) (b) 一括の移行（削除または質問票での再確認）を必須にする（0 件なので実質空振り）
- 未回答時の既定値候補: (d) 特例規定を全部削除し、実在 0 件の確認と理由を ADR に残す（規則・テストが減る。万一残っていた導入先では通常の Q&A として扱われうる）
- 既定値候補の理由: 保存期間は約 3 週間で、手元の全リポで実在 0 件。使われていない仕組みに規則を残さない（ADR 0029 と同じ判断軸。no-overengineering）。Issue の要件『どの経路でも確定前提に使われない』も、対象が存在しないので満たされる
- 未回答のまま進めた場合の影響: 方式が決まらず、Issue #63 に着手できない

[Q02]
- 対象ドキュメント: knowledge/adr/
- 問題種別: 不明瞭
- 重大度: minor
- 質問内容: source: gmail の Q&A を既定値候補にした質問票の記録（qa/*.md）の写しの扱いを定めますか？
- 選択肢: A) 定めない（写しが 0 件であることを ADR に記録して閉じる） B) 写しも削除・書き換える手順を規則に定める（qa の記録の改変規則が要る）
- 未回答時の既定値候補: 定めない（写しが 0 件であることを ADR に記録して閉じる）
- 既定値候補の理由: 対象が存在しない。存在しないものに手順を定めるのは YAGNI
- 未回答のまま進めた場合の影響: ADR で論点が閉じられず、#64 からの引き継ぎが残る

[Q03]
- 対象ドキュメント: knowledge/adr/
- 問題種別: 不明瞭
- 重大度: minor
- 質問内容: (d) を選んだ場合、手元にない導入先に source: gmail の Q&A が万一残っていたときの扱いをどこに書きますか？
- 選択肢: A) ADR の結果（Consequences）にだけ書く（見つけたら削除するか、質問票で PO に確認し直す） B) resolve-issue の knowledge 検索に 1 行だけ残す（source が po 以外の Q&A は既知の回答に使わない）
- 未回答時の既定値候補: ADR の結果（Consequences）にだけ書く（見つけたら削除するか、質問票で PO に確認し直す）
- 既定値候補の理由: 規則を増やさずに判断の記録は残る。ADR 0029 が導入先の写しの扱いを結果の節に書いたのと同じ形
- 未回答のまま進めた場合の影響: 残存時の扱いが誰にも分からない

---

## 回答（確定 2026-10-31）

| No. | 回答 | 判断 | 根拠 |
|---|---|---|---|
| Q01 | **(d) 特例規定を全部削除し、実在 0 件の確認と理由を ADR に残す** | 既定値承認 | 保存期間は約 3 週間で、手元の全リポで実在 0 件。使われていない仕組みに規則を残さない（会話で「推奨」と回答） |
| Q02 | **定めない（写しが 0 件であることを ADR に記録して閉じる）** | 既定値承認 | 対象が存在しない（会話で「推奨」と回答） |
| Q03 | **ADR の結果（Consequences）にだけ書く（見つけたら削除するか、質問票で PO に確認し直す）** | 既定値承認 | 規則を増やさずに判断の記録は残る（会話で「推奨」と回答） |
