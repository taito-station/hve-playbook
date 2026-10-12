# Issue #55 hook によるルール順守ゲートの対象範囲

- 対象スコープ: Issue #55: hooks/ に新設する 2 本の hook（A: PermissionRequest/ExitPlanMode で計画本文を検査、B: main/master 上の操作を止める）
- 対象ドキュメント:
  - `hooks/`
  - `settings.json`
  - `rules/global/git/branching.md`
  - `rules/hve/implement-flow.md`
  - `skills/hve-implement/SKILL.md`
- 関連スコープ: Issue #55
- 生成: aqod（Issue #55 の implement-flow Step 4 で見つかったブロッキングな論点。hook B の対象範囲、hook A の適用範囲と見出しの判定方法を決める）
- 状態: 回答済み
- 推論許可: 3 問とも人間判断（既定値は推奨解）
- 作成日: 2026-10-07
- 回答確定日: 2026-10-12
- 反映先: `knowledge/adr/0020-gate-plan-headings-and-main-commit-with-hooks.md`、`CLAUDE.md`、`rules/global/git/branching.md`、`skills/hve-implement/SKILL.md`、`skills/global/resolve-issue/SKILL.md`

## サマリー

Issue #55 の implement-flow Step 4（ギャップ分析）で見つかったブロッキングな論点。hook B（main 上の操作を止める）の対象範囲、hook A（ExitPlanMode の計画本文検査）の適用範囲と見出しの判定方法を決める。

---

[Q01]
- 対象ドキュメント: rules/global/git/branching.md
- 該当箇所: 作業開始時の手順（:14, :23）
- 問題種別: 一貫性欠落
- 重大度: critical
- 質問内容: hook B（main/master 上の操作を止める）の対象をどこまでにしますか？
- 選択肢: A) git commit だけを止める（Edit/Write は止めない）。逃げ道は既存の慣習どおり `# via:main-commit-ok: <理由>` B) Issue 原文どおり Edit/Write も止める。ただし git 追跡済みのファイルに限り、docs/temp/・qa/・session_logs/ を除外する C) Edit/Write も止め、resolve-issue のブランチ作成を Step 1 の直後に早める
- 未回答時の既定値候補: git commit だけを止める（Edit/Write は止めない）
- 既定値候補の理由: 実害である main へのコミットは commit で防げる。branching.md:23 の「退避してから commit」とも整合し、除外リストの保守が要らない
- 未回答のまま進めた場合の影響: Edit/Write まで止めると、resolve-issue・create-issue・edit-issue が全リポで止まる

[Q02]
- 対象ドキュメント: rules/hve/implement-flow.md
- 該当箇所: 適用条件
- 問題種別: 不明瞭
- 重大度: major
- 質問内容: hook A（ExitPlanMode の計画本文検査）をどの計画に適用しますか？
- 選択肢: A) 全計画で 2 見出しを必須にする。implement-flow の対象外の計画は「ゲートの確認結果」に「対象外: <理由>」と書けば通す B) HVE のリポジトリだけで検査する C) 全計画で検査するが、専用のマーカーがあれば見出しの検査自体を省く
- 未回答時の既定値候補: 全計画で 2 見出しを必須にし、対象外の計画は「対象外: <理由>」と書けば通す
- 既定値候補の理由: HVE かどうかの判定などの分岐が要らず、規則を 1 本に保てる。ルール準拠表は対象外のタスクでも有効
- 未回答のまま進めた場合の影響: 対象外の計画まで一律に止めると、形だけの見出しを書く運用になる

[Q03]
- 対象ドキュメント: hooks/（新設する A）
- 問題種別: 不明瞭
- 重大度: major
- 質問内容: hook A は、計画本文の見出しをどう判定しますか？
- 選択肢: A) 見出しレベル #〜#### のどれかで、見出しの文字列に「ゲートの確認結果」「ルール準拠表」を含めば可。ルール準拠表の節には表の行（| を含む行）が 1 行以上必要 B) 完全一致 C) 見出しの文字列を含むかだけを見る
- 未回答時の既定値候補: 見出しの文字列を含めば可、ルール準拠表の節に表の行が 1 行以上必要
- 既定値候補の理由: 表記揺れによる誤検知を抑えつつ、表の行を求める最小限の内容検査で、見出しだけ置いて空にする抜け道を塞げる
- 未回答のまま進めた場合の影響: 厳しすぎると誤検知が増え、緩すぎると見出しだけ置いて中身を空にする抜け道が残る

---

## 回答（確定 2026-10-12）

HTML のエクスポートではなく、会話での「推奨」という回答で 3 問とも推奨解に確定した。

| No. | 回答 | 判断 | 根拠 |
|---|---|---|---|
| Q01 | **git commit だけを止める（Edit/Write は止めない）。逃げ道は `# via:main-commit-ok: <理由>`** | 既定値承認 | 実害である main へのコミットは commit で防げる。branching.md:23 の「退避してから commit」とも整合し、除外リストの保守が要らない |
| Q02 | **全計画で 2 見出しを必須にし、implement-flow の対象外の計画は「ゲートの確認結果」に「対象外: <理由>」と書けば通す** | 既定値承認 | HVE かどうかの判定などの分岐が要らず、規則を 1 本に保てる。ルール準拠表は対象外のタスクでも有効 |
| Q03 | **見出しレベル #〜#### で、見出しの文字列に「ゲートの確認結果」「ルール準拠表」を含めば可。ルール準拠表の節に表の行が 1 行以上必要** | 既定値承認 | 表記揺れによる誤検知を抑えつつ、見出しだけ置いて空にする抜け道を塞げる |
