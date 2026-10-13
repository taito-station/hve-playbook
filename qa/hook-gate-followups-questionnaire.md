# Issue #62: #55 の範囲外の改善の進め方

- 対象スコープ: hve-playbook の skill・rule・hook・tests（Issue #62）
- 対象ドキュメント:
  - `skills/hve-akm/SKILL.md`
  - `skills/global/commit-workflow/SKILL.md`
  - `rules/global/git/branching.md`
  - `hooks/skill-enforcer.py`
  - `skills/global/add-hook/SKILL.md`
  - `tests/test_plan_gate_check.sh`
- 関連スコープ: hve-playbook#62、#55、PR #61、ADR 0020
- 生成: aqod（#55 の範囲外とした 5 件の実装方針を決める）
- 状態: 回答済み
- 推論許可: 既定値候補はコードと ADR 0020 から推論した。PO が承認または変更する
- 作成日: 2026-10-13
- 回答確定日: 2026-10-13
- 反映先: `skills/hve-akm/SKILL.md`、`skills/global/commit-workflow/SKILL.md`、`rules/global/git/branching.md`、`skills/global/add-hook/SKILL.md`、`tests/test_plan_gate_check.sh`、ADR 起票（`knowledge/adr/`）

## サマリー

#55（PR #61）のセルフレビューで範囲外とした 5 件（hve-akm の作業ブランチ、「コミットして」と main への via、見出しの語の契約テスト、skill-enforcer の via の名前空間、add-hook (d) の sync の注意）について、実装方針を決めるための質問票。

---

[Q01]
- 対象ドキュメント: rules/global/git/branching.md
- 該当箇所: PR とコミットの粒度
- 問題種別: 不明瞭
- 重大度: minor
- 質問内容: 5 件を何本の PR に分けますか？
- 選択肢: A) 1 PR（#55 のフォローアップを 1 トピックとして扱う。Issue 1 本のまま閉じられる） B) 2 PR（hook とテストの変更（4・3）／skill と rule の文面（1・2・5）） C) 5 PR（1 件 1 PR。フローを 5 回まわす）
- 未回答時の既定値候補: 1 PR（#55 のフォローアップを 1 トピックとして扱う。Issue 1 本のまま閉じられる）
- 既定値候補の理由: 5 件とも #55 で入れたゲートとの整合を取るフォローアップで、変更は小さい。Issue の成功条件 5 つを 1 回の Plan・レビューで確かめられる
- 未回答のまま進めた場合の影響: レビューの単位と、resolve-issue のフロー（Plan・レビュー）を何回まわすかが変わる

[Q02]
- 対象ドキュメント: skills/global/commit-workflow/SKILL.md
- 該当箇所: コミット指示の判定
- 問題種別: 一貫性欠落
- 重大度: major
- 質問内容: main 上で「コミットして」とだけ言われたとき、どうしますか？
- 選択肢: A) 作業ブランチを切って（git switch -c、規約どおりの名前を自分で決める）退避してから commit し、ブランチ名を報告する B) 退避する前にブランチ名をユーザーに確認する C) via を付けて main に commit する（「コミットして」を main への明示指示とみなす）
- 未回答時の既定値候補: 作業ブランチを切って（git switch -c、規約どおりの名前を自分で決める）退避してから commit し、ブランチ名を報告する
- 既定値候補の理由: 「コミットして」は commit の指示で、main への commit の指示ではない。branching.md の「main に残さず退避する」に沿い、追加の確認なしで指示を果たせる
- 未回答のまま進めた場合の影響: モデルが via を付けて main に commit するか、毎回止まって尋ねるかが場面ごとに揺れる

[Q03]
- 対象ドキュメント: rules/global/git/branching.md
- 該当箇所: 作業開始時の手順
- 問題種別: 一貫性欠落
- 重大度: minor
- 質問内容: q2 の規則をどこに書きますか？
- 選択肢: A) branching.md に規則を 1 文書き、commit-workflow の「即座にコミット実行」に「main 上なら branching.md に従って退避してから」と添える B) branching.md だけに書く C) commit-workflow だけに書く
- 未回答時の既定値候補: branching.md に規則を 1 文書き、commit-workflow の「即座にコミット実行」に「main 上なら branching.md に従って退避してから」と添える
- 既定値候補の理由: 正本は branching.md に置いたまま、commit-workflow の「即座に」だけを読んで main に commit する誤読を防げる。差分は 2 行
- 未回答のまま進めた場合の影響: 片方だけに書くと、もう片方だけを読んだときに規則が効かない

[Q04]
- 対象ドキュメント: skills/hve-akm/SKILL.md
- 該当箇所: 実行手順（Step 2 の前）
- 問題種別: 不明瞭
- 重大度: minor
- 質問内容: hve-akm で切る作業ブランチの名前をどう定めますか？
- 選択肢: A) 導入先のブランチ運用規約に従い、無ければ docs/akm-<YYYYMMDD> B) 導入先の規約に従い、無ければ chore/akm-<YYYYMMDD> C) 名前は定めず「作業ブランチを切る」とだけ書く
- 未回答時の既定値候補: 導入先のブランチ運用規約に従い、無ければ docs/akm-<YYYYMMDD>
- 既定値候補の理由: hve-implement の Step 0 と同じ書き方（規約があれば従い、無ければ既定）。knowledge の更新は docs 型に当たる
- 未回答のまま進めた場合の影響: 導入先ごとにブランチ名が揺れる。規約のある導入先で規約から外れた名前になる

[Q05]
- 対象ドキュメント: tests/test_plan_gate_check.sh
- 該当箇所: 契約テスト
- 問題種別: 重大な欠落
- 重大度: minor
- 質問内容: 見出し「ゲートの確認結果」「ルール準拠表」の契約テストを足しますか？
- 選択肢: A) 足す（test_plan_gate_check.sh で hook の定数を読み、正本 3 か所が 2 語を含むことを検査する） B) 足さない（見出しは固定と決めているので変わりにくい。理由を記録する）
- 未回答時の既定値候補: 足す（test_plan_gate_check.sh で hook の定数を読み、正本 3 か所が 2 語を含むことを検査する）
- 既定値候補の理由: 数行で書け、改名したときの deny という影響の大きい事故を CI 前に検出できる。語を hook から読むので、テスト側に語を重複させずに済む
- 未回答のまま進めた場合の影響: 片方だけを改名すると、規則どおりの計画が deny される（または、ずれに気づかない）

[Q06]
- 対象ドキュメント: skills/global/add-hook/SKILL.md
- 該当箇所: Step 3 (d)
- 問題種別: 重大な欠落
- 重大度: major
- 質問内容: add-hook の検証手順 (d) に、作業ブランチ／worktree での sync についてどの注意を足しますか？
- 選択肢: A) 作業ブランチ／worktree では CLAUDE_HOME=<一時ディレクトリ> で sync し、sync の FATAL 判定で確かめる（~/.claude への sync と python 検証はマージ後に main で行う） B) ~/.claude に sync してよいが、main に戻した直後に同じコマンドで sync --prune する手順を足す
- 未回答時の既定値候補: 作業ブランチ／worktree では CLAUDE_HOME=<一時ディレクトリ> で sync し、sync の FATAL 判定で確かめる（~/.claude への sync と python 検証はマージ後に main で行う）
- 既定値候補の理由: ~/.claude を作業ブランチに向けないので、実体が消える状況自体が起きない。ADR 0020 の「symlink 先の clone は main のまま」と一致する
- 未回答のまま進めた場合の影響: 作業ブランチから sync して main に戻すと hook の実体が消え、その hook が発火する tool が全面的に止まる

[Q07]
- 対象ドキュメント: knowledge/adr/
- 該当箇所: 新規 ADR
- 問題種別: 不明瞭
- 重大度: minor
- 質問内容: 決定ログ（ADR）を書きますか？
- 選択肢: A) 1 本書く（q2 の規則と skill-enforcer の bypass の範囲を記録する） B) 書かない（文面の補足と hook の判定の修正なので、PR の説明で足りる）
- 未回答時の既定値候補: 1 本書く（q2 の規則と skill-enforcer の bypass の範囲を記録する）
- 既定値候補の理由: どちらも via という逃げ道の範囲を決める判断で、ADR 0020 の補足に当たる。implement-flow の Step 7 は設計判断を決定ログに残すとしている
- 未回答のまま進めた場合の影響: 判断の理由が後から辿れない

---

## 回答（確定 2026-10-13）

PO が会話で「推奨」と回答し、全問の既定値候補を承認した（HTML のエクスポートは経ていない）。

| No. | 回答 | 判断 | 根拠 |
|---|---|---|---|
| Q01 | **1 PR（#55 のフォローアップを 1 トピックとして扱う。Issue 1 本のまま閉じられる）** | 既定値承認 | 5 件とも #55 で入れたゲートとの整合を取るフォローアップで、変更は小さい。Issue の成功条件 5 つを 1 回の Plan・レビューで確かめられる |
| Q02 | **作業ブランチを切って（git switch -c、規約どおりの名前を自分で決める）退避してから commit し、ブランチ名を報告する** | 既定値承認 | 「コミットして」は commit の指示で、main への commit の指示ではない。branching.md の「main に残さず退避する」に沿い、追加の確認なしで指示を果たせる |
| Q03 | **branching.md に規則を 1 文書き、commit-workflow の「即座にコミット実行」に「main 上なら branching.md に従って退避してから」と添える** | 既定値承認 | 正本は branching.md に置いたまま、commit-workflow の「即座に」だけを読んで main に commit する誤読を防げる。差分は 2 行 |
| Q04 | **導入先のブランチ運用規約に従い、無ければ docs/akm-<YYYYMMDD>** | 既定値承認 | hve-implement の Step 0 と同じ書き方（規約があれば従い、無ければ既定）。knowledge の更新は docs 型に当たる |
| Q05 | **足す（test_plan_gate_check.sh で hook の定数を読み、正本 3 か所が 2 語を含むことを検査する）** | 既定値承認 | 数行で書け、改名したときの deny という影響の大きい事故を CI 前に検出できる。語を hook から読むので、テスト側に語を重複させずに済む |
| Q06 | **作業ブランチ／worktree では CLAUDE_HOME=<一時ディレクトリ> で sync し、sync の FATAL 判定で確かめる（~/.claude への sync と python 検証はマージ後に main で行う）** | 既定値承認 | ~/.claude を作業ブランチに向けないので、実体が消える状況自体が起きない。ADR 0020 の「symlink 先の clone は main のまま」と一致する |
| Q07 | **1 本書く（q2 の規則と skill-enforcer の bypass の範囲を記録する）** | 既定値承認 | どちらも via という逃げ道の範囲を決める判断で、ADR 0020 の補足に当たる。implement-flow の Step 7 は設計判断を決定ログに残すとしている |
