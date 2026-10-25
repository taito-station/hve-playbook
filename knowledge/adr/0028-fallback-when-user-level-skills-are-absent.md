# HVE の規則と hve-implement は、user-level の skill が無いときの代替をその場に書く

## ステータス

Accepted — 2026-10-25

## 背景と課題

#40（PR #47）で、第三者には project-level（`setup.sh`）だけを勧めることにした。ところが、配っている HVE の規則（`rules/hve/`）と hve-implement skill は、user-level の skill（create-pr・review-pr・documentation-standards・resolve-issue）があることを前提にしていた。project-level だけの導入先には参照先の skill が無く、PR の作成（implement-flow の Step 8）・ADR の様式・Issue の対応の入口を辿れなかった。README には「無い場合は該当の手順を手で行う」とだけ書いてあった（Issue #74。#52 から切り出し）。

## 意思決定の要因

- ADR 0007: global 配下（create-pr など）は setup.sh で配らず、導入先は setup.sh のコピーだけで自己完結する
- implement-flow の branching 参照は、すでに「規約があればそれに従い、無ければ〜」の書き方で解決している（ADR 0007）
- 代替の手順が create-pr・documentation-standards の手順を複製すると、二重管理になってずれる（minimal-diff・no-overengineering）

## 検討した選択肢

- 規則と hve-implement に「skill があれば使い、無ければ <代替>」を書く
- create-pr・review-pr・documentation-standards を setup.sh で導入先にも配る
- README の注記（現状）で足りるとし、規則は変えない

## 決定内容

選択した選択肢: **規則と hve-implement に「skill があれば使い、無ければ <代替>」を書く。代替は最小限にし、skill の手順を複製しない**。質問票の回答（`qa/project-level-skill-refs-and-setup-home-questionnaire.md` の Q01〜Q03）と、Plan の敵対的レビューによる。

- PR の作成（`rules/hve/implement-flow.md` の Step 8、hve-implement の Step 8）: create-pr が無ければ、変更をコミットし、作業ブランチを push して `gh pr create` で作る（本文は導入先のブランチ運用規約の雛形があればそれ）。implement-flow のフロー図は、global 版との行の包含（`tests/test_implement_flow_drift.sh`）のため変えず、Step 8 の本文に行を足す
- ADR の様式（`rules/hve/artifact-management.md` の「書式」）: documentation-standards への参照（配置先・テンプレート・採番・ステータス値）の読み替えを 1 か所にまとめる。「既存の別配置」の意味、ファイル名の形、章の名前と順序、ステータス行の書式と 5 つの値、一覧への追記だけを書き、テンプレートは複製しない。`rules/hve/knowledge-maturity.md` の ADR の様式の参照は、この読み替えを指す
- Issue の対応の入口（hve-implement の「Issue を対応するときは resolve-issue を使う」、`docs/usage-prompts.md` の同じ案内）: resolve-issue が無ければ単独モードで行い、Step 1 で `gh issue view` で Issue を読む。Issue への記録や `Closes` の付与など resolve-issue の役目は写さない
- README の一部取り込みの注記に、hook の skill-enforcer を取り込むときは create-pr skill も取り込むことを書く。skill-enforcer は `gh pr create` の直接の実行を止めるため、create-pr が無いと代替を辿れず、`# via:create-pr` を経路を通らずに付ける運用（ADR 0023 に反する）を招く。規則（rules/hve）は hook を前提にしないので、規則側には書かない（PR #83 のセルフレビューの escalate へのオーナー判断）
- 代替を書かない参照:
  - knowledge-maturity の squash・rebase 後の sha の追従（review-pr を含む）。既存の「手で squash・rebase したときも同じように実行する」で足りる
  - knowledge-maturity のパース契約。hve-playbook の保守者への注意で、導入先が辿る手順ではない
  - 「resolve-issue 経由のときは」「resolve-issue から呼ばれたときは」の条件付きの記述。resolve-issue があるときだけ通る
  - implement-flow のフロー図の「create-pr スキルで PR 作成」。global 版との行の包含を drift テストが検査するため変えない。代替は Step 8 の本文にある（PR #83 のセルフレビューの escalate へのオーナー判断）
- skill の有無は、Claude Code が読み込める skill にあるかで判断する。既存の「commit-workflow skill があれば」と同じ読み方で、判定方法は規則に書かない

### 結果（Consequences）

- 良い結果: project-level だけの導入先でも、Step 8・ADR の様式・Issue の対応を規則だけで辿れる。user-level の skill がある環境の動きは変わらない（既存の文は消さず、条件を足しただけ）
- 悪い結果・既知の限界:
  - 代替の `gh pr create` には、create-pr の base の同期・squash・セルフレビューが無い。導入先はそれらを必要に応じて手で行う
  - ADR の読み替えのステータス値は documentation-standards の値の写しになる。documentation-standards のステータス値を変えるときは、artifact-management の読み替えも直す
  - 代替が書いてあることは契約テストで固定していない（Issue の要件にないため）
  - 代替の PR の作成は remote と gh を前提にする。remote の無い導入先では、create-pr があるときと同じく PR を作れない

## 選択肢の評価（Pros and Cons）

### 「あれば使い、無ければ代替」を書く（採用）

#### メリット

- ADR 0007 と整合し、配布物が増えない。branching 参照と同じ書き方を踏襲できる

#### デメリット

- 代替は skill の手順より簡素で、create-pr のセルフレビューなどは受けられない

### setup.sh で skill を配る

#### メリット

- 導入先でも user-level と同じ手順を辿れる

#### デメリット

- ADR 0007 の「global は setup.sh で配らない」と衝突する。Laravel 前提の記述も持ち込み、作者の環境では同名の skill が二重になる

### README の注記だけで済ませる

#### メリット

- 変更が要らない

#### デメリット

- 規則を読む Claude は README を読まないので、Step 8 で存在しない skill を呼んで止まる

## 関連リンク

- Related: [0007-consolidate-user-level-rules-and-agents](0007-consolidate-user-level-rules-and-agents.md)
- Related: [0026-setup-refuses-user-level-claude-dir](0026-setup-refuses-user-level-claude-dir.md)
- Related: [hve-playbook#74](https://github.com/taito-station/hve-playbook/issues/74)
