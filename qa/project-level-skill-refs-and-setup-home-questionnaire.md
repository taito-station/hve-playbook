# Issue #52: project-level 導入先での skill 参照と setup.sh の $HOME 指定

- 対象スコープ: rules/hve/（implement-flow.md・knowledge-maturity.md・artifact-management.md）、skills/hve-implement/SKILL.md、setup.sh、tests/、README
- 対象ドキュメント:
  - `rules/hve/implement-flow.md`
  - `rules/hve/knowledge-maturity.md`
  - `rules/hve/artifact-management.md`
  - `skills/hve-implement/SKILL.md`
  - `setup.sh`
  - `README.md`
- 関連スコープ: hve-playbook#52（#40 / PR #47 のレビューで検出）
- 生成: aqod（規則が参照する user-level skill が無い導入先での手順の方式、setup.sh が止める条件、Issue を分けるかを決める）
- 状態: 回答済み
- 推論許可: 方式とスコープはオーナー判断。既定値は ADR-0007 の既存の決定と書き方に合わせた
- 作成日: 2026-10-15
- 回答確定日: 2026-10-15
- 反映先: `setup.sh`・`tests/`・`README.md`・ADR 起票（`knowledge/adr/`）は #52。Q01〜Q03 は切り出した Issue（`rules/hve/*.md`・`skills/hve-implement/SKILL.md`）

## サマリー

Issue #52 の未決事項（規則が参照する user-level skill が無い導入先での手順の方式、setup.sh が止める条件、Issue を分けるか）を決める。ADR-0007 は「global 配下は setup.sh では配らない」「導入先は setup.sh のコピーだけで自己完結する」と決めており、implement-flow の branching 参照は「規約があればそれに従い、無ければ〜」の書き方で解決している。

---

[Q01]
- 対象ドキュメント: rules/hve/implement-flow.md・knowledge-maturity.md・artifact-management.md
- 該当箇所: implement-flow.md 63・164 行、knowledge-maturity.md 11・110・133 行、artifact-management.md 57・72・91・92 行
- 問題種別: 重大な欠落
- 重大度: major
- 質問内容: 規則が参照する user-level skill（create-pr・review-pr・documentation-standards）が導入先に無いとき、どう辿れるようにしますか？
- 選択肢: A) (a) 規則に「skill があれば使い、無ければ <代替手順>」を書く（ADR-0007 の branching と同じ書き方。配布物は増えない） B) (b) create-pr・review-pr・documentation-standards を setup.sh で導入先にも配る（ADR-0007 の一部を覆す新 ADR が要る。Laravel 前提の記述も持ち込み、作者環境では同名 skill が二重になる） C) (c) README の注記（現状）で足りるとし、規則は変えない
- 未回答時の既定値候補: (a) 規則に「skill があれば使い、無ければ <代替手順>」を書く（ADR-0007 の branching と同じ書き方。配布物は増えない）
- 既定値候補の理由: ADR-0007 の「global は setup.sh で配らない・導入先は自己完結」と整合し、branching 参照で既に使っている書き方を踏襲できる。新しい ADR での supersede が要らない
- 未回答のまま進めた場合の影響: project-level だけの導入先で Step 8・ADR の書式・squash 後の追従を辿れない

[Q02]
- 対象ドキュメント: rules/hve/*.md
- 問題種別: 不明瞭
- 重大度: minor
- 質問内容: (a) を採る場合、代替手順はどこまで書きますか？
- 選択肢: A) 最小限: PR は `gh pr create`（本文は branching の雛形があればそれ）、ADR の様式は MADR の章立て（artifact-management の対応表の右列）と既存 ADR に倣う、squash 後の追従は既存の記述を指す B) 詳細: create-pr の要点（base 同期・squash・sha 追従・セルフレビュー）を規則に要約して書く
- 未回答時の既定値候補: 最小限
- 既定値候補の理由: 代替として必要な 1〜2 行に留め、create-pr の手順を複製しない（最小差分・二重管理の回避）
- 未回答のまま進めた場合の影響: 書きすぎると create-pr の手順と規則が二重管理になり、ずれる

[Q03]
- 対象ドキュメント: skills/hve-implement/SKILL.md
- 該当箇所: Step 8: PR 作成
- 問題種別: 一貫性欠落
- 重大度: major
- 質問内容: (a) を採る場合、配布される hve-implement の SKILL.md（Step 8 で create-pr を無条件に呼ぶ）も直しますか？
- 選択肢: A) 含める（Step 8 を「create-pr があれば呼び、無ければ <代替>」にする） B) 含めない（規則だけを直し、skill は別 Issue）
- 未回答時の既定値候補: 含める
- 既定値候補の理由: 規則と同じ欠落が配布物の skill にもあり、同じ要件（参照先を辿れる）の範囲に入る
- 未回答のまま進めた場合の影響: 直さないと、project-level だけの導入先で /hve-implement の Step 8 が存在しない skill を呼んで止まる

[Q04]
- 対象ドキュメント: setup.sh
- 該当箇所: 29 行目（TARGET_CLAUDE の決定）
- 問題種別: 重大な欠落
- 重大度: major
- 質問内容: setup.sh が止める条件はどこまでにしますか？
- 選択肢: A) `$TARGET/.claude` の実体（pwd -P）が `$HOME/.claude` の実体と同じなら止める（`setup.sh ~` と、.claude が ~/.claude を指す symlink の両方を防ぐ） B) `$TARGET` の実体が `$HOME` と同じときだけ止める
- 未回答時の既定値候補: `$TARGET/.claude` の実体（pwd -P）が `$HOME/.claude` の実体と同じなら止める
- 既定値候補の理由: Issue の要件（~/.claude を TARGET_CLAUDE にする指定）をそのまま判定でき、symlink 経由の同じ事故も 1 つの比較で防げる
- 未回答のまま進めた場合の影響: ~/.claude の rules/hve などを削除・上書きしうる

[Q05]
- 対象ドキュメント: setup.sh
- 問題種別: 不明瞭
- 重大度: minor
- 質問内容: Q04 の条件に当たったとき、止めますか、確認しますか？
- 選択肢: A) [ERROR] を出して exit 1（上書きの抜け道は設けない） B) y/N で確認し、y なら続ける
- 未回答時の既定値候補: [ERROR] を出して exit 1（上書きの抜け道は設けない）
- 既定値候補の理由: 既存の「hve-playbook 自身をターゲットにできない」と同じ扱いで単純。~/.claude に HVE を入れる正当な用途は無い（user-level は sync の役割）
- 未回答のまま進めた場合の影響: 確認方式は非対話の実行（適用プロンプト経由の Claude の実行）で扱いが難しい

[Q06]
- 問題種別: 不明瞭
- 重大度: minor
- 質問内容: 1（規則の参照先）と 2（setup.sh の $HOME）を Issue・PR で分けますか？
- 選択肢: A) 分ける: #52 は 2（setup.sh・テスト）で進め、1 は新しい Issue に切り出す B) 分ける: #52 は 1（規則）で進め、2 を新しい Issue に切り出す C) 分けずに #52 の 1 PR で両方を行う
- 未回答時の既定値候補: 分ける: #52 は 2（setup.sh・テスト）で進め、1 は新しい Issue に切り出す
- 既定値候補の理由: 性質（コード＋テスト / 規則の文面）が違い、1 PR = 1 トピックに合う。setup.sh 側は小さく先に閉じられる

---

## 回答（確定 2026-10-15）

PO は会話で「推奨」と回答し、全問の既定値候補を承認した。

| No. | 回答 | 判断 | 根拠 |
|---|---|---|---|
| Q01 | **(a) 規則に「skill があれば使い、無ければ <代替手順>」を書く** | 既定値承認 | ADR-0007 の「global は setup.sh で配らない・導入先は自己完結」と整合し、branching 参照で既に使っている書き方を踏襲できる |
| Q02 | **最小限** | 既定値承認 | 代替として必要な 1〜2 行に留め、create-pr の手順を複製しない |
| Q03 | **含める** | 既定値承認 | 規則と同じ欠落が配布物の skill にもあり、同じ要件の範囲に入る |
| Q04 | **`$TARGET/.claude` の実体（pwd -P）が `$HOME/.claude` の実体と同じなら止める** | 既定値承認 | Issue の要件をそのまま判定でき、symlink 経由の同じ事故も 1 つの比較で防げる |
| Q05 | **[ERROR] を出して exit 1** | 既定値承認 | 既存の「hve-playbook 自身をターゲットにできない」と同じ扱いで単純。~/.claude に HVE を入れる正当な用途は無い |
| Q06 | **分ける: #52 は setup.sh・テストで進め、規則側は新しい Issue に切り出す** | 既定値承認 | 性質が違い、1 PR = 1 トピックに合う |
