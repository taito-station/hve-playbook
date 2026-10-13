# Issue #46: 導入先に配る HVE 資産の著作権表示と許諾表示

- 対象スコープ: setup.sh が導入先に配る HVE 資産（rules/hve・skills/hve-*・agents/hve-*.md・workflows/hve-*.js・scripts/hve・CLAUDE.hve.md）
- 対象ドキュメント:
  - `setup.sh`
  - `docs/prompts/apply-hve-playbook.md`
  - `LICENSE`
  - `knowledge/adr/0015-license-plain-mit-with-provenance-in-readme.md`
- 関連スコープ: hve-playbook#46
- 生成: aqod（導入先に配る HVE 資産に MIT の条件を満たす表示を付けるための、Issue の未決事項の確認）
- 状態: 回答済み
- 推論許可: 全問を PO が判断する（推奨は既定値候補として提示）
- 作成日: 2026-10-12
- 回答確定日: 2026-10-12
- 反映先: 新規 ADR（`knowledge/adr/0021-*.md`）、`setup.sh`、`docs/prompts/apply-hve-playbook.md`

## サマリー

setup.sh は導入先の .claude/ に HVE 由来の資産をコピーするが、LICENSE（著作権表示と許諾表示）は一緒にコピーしない。MIT の条件を満たす配り方を決めるため、Issue の未決事項 4 点を確認する。ここでの判断は法的助言ではない。

---

[Q01]
- 対象ドキュメント: setup.sh
- 該当箇所: setup.sh の 34〜94 行目（資産のコピー）
- 問題種別: 重大な欠落
- 重大度: major
- 質問内容: 著作権表示と許諾表示を、導入先にどの形で置きますか？
- 選択肢: A) リポの LICENSE をそのまま .claude/LICENSE-hve-playbook に 1 ファイルでコピーする B) rules/hve・skills/hve-*・scripts/hve の各ディレクトリに LICENSE を置く（agents・workflows には置けない） C) CLAUDE.hve.md の出典行を著作権表示と許諾文の全文にする（毎セッションのコンテキストを消費する）
- 未回答時の既定値候補: リポの LICENSE をそのまま .claude/LICENSE-hve-playbook に 1 ファイルでコピーする
- 既定値候補の理由: 最も単純で、全資産を 1 ファイルで覆える。LICENSE を丸ごとコピーするので 3 者の著作権行と許諾文が欠けない。各ディレクトリ案は agents/workflows に置けず、CLAUDE.hve.md 案は毎セッションのコンテキストを消費する
- 未回答のまま進めた場合の影響: 配置の形が決まらず実装に入れない

[Q02]
- 対象ドキュメント: docs/prompts/apply-hve-playbook.md
- 該当箇所: 手順 2「git 管理外の HVE 資産を守る」、手順 6 の gitignore の例
- 問題種別: 一貫性欠落
- 重大度: major
- 質問内容: 導入先の git 管理で、新しく置くファイルをどう扱いますか？
- 選択肢: A) 手順 6 の ignore の例外に !/.claude/LICENSE-hve-playbook を足し、手順 2 の退避対象と手順 7 の確認にも加える B) ignore の例外にだけ足す C) apply-hve-playbook.md は変えない
- 未回答時の既定値候補: 手順 6 の ignore の例外に !/.claude/LICENSE-hve-playbook を足し、手順 2 の退避対象と手順 7 の確認にも加える
- 既定値候補の理由: 例外に足さないと、.claude/ を ignore している導入先では表示がコミットされず、公開・再配布される複製に含まれない。退避・確認の対象も他の HVE 資産と揃える
- 未回答のまま進めた場合の影響: ignore されたまま表示がコミットされず、導入先の公開リポに表示が残らない

[Q03]
- 対象ドキュメント: LICENSE
- 該当箇所: hve-scripts/（setup.sh の 74〜79 行目で scripts/hve に配る）
- 問題種別: 不明瞭
- 重大度: minor
- 質問内容: HVE 由来でない資産（hve-scripts は taito-station/paddock からの移植）も、同じ LICENSE 1 本で覆ってよいですか？
- 選択肢: A) 同じ LICENSE 1 本でよい（paddock のスクリプトの著作権者はオーナー本人だけ） B) paddock に他の著作権者がいる（その表示を追加する）
- 未回答時の既定値候補: 同じ LICENSE 1 本でよい（paddock のスクリプトの著作権者はオーナー本人だけ）
- 既定値候補の理由: paddock は taito-station のリポジトリで、移植した本人がオーナー。taito-station の著作権行で覆われ、追加の表示は要らない
- 未回答のまま進めた場合の影響: paddock に他の著作権者がいた場合、その表示が欠ける

[Q04]
- 対象ドキュメント: knowledge/adr/（新規 ADR）
- 該当箇所: Issue #46 の未決事項「法的な解釈」
- 問題種別: 不明瞭
- 重大度: major
- 質問内容: 導入先に配る資産が MIT の「substantial portions」に当たるかを問わず、表示を含める側に倒しますか？
- 選択肢: A) 含める（解釈を問わず表示を配る） B) 含めない（含めなくてよい根拠を ADR に記録する）
- 未回答時の既定値候補: 含める（解釈を問わず表示を配る）
- 既定値候補の理由: コストが 1 ファイルのコピーで済み、「含めなくてよい」根拠を立てて維持するより安全
- 未回答のまま進めた場合の影響: 表示の要否が決まらず、ADR の決定内容が書けない

---

## 回答（確定 2026-10-12）

PO が会話で「推奨」と回答し、全問の既定値候補を承認した（ブラウザの回答ファイルは使っていない）。

| No. | 回答 | 判断 | 根拠 |
|---|---|---|---|
| Q01 | **リポの LICENSE をそのまま .claude/LICENSE-hve-playbook に 1 ファイルでコピーする** | 既定値承認 | 最も単純で、全資産を 1 ファイルで覆える。3 者の著作権行と許諾文が欠けない |
| Q02 | **手順 6 の ignore の例外に !/.claude/LICENSE-hve-playbook を足し、手順 2 の退避対象と手順 7 の確認にも加える** | 既定値承認 | 例外に足さないと、.claude/ を ignore している導入先で表示がコミットされない |
| Q03 | **同じ LICENSE 1 本でよい（paddock のスクリプトの著作権者はオーナー本人だけ）** | 既定値承認 | paddock は taito-station のリポジトリで、taito-station の著作権行で覆われる |
| Q04 | **含める（解釈を問わず表示を配る）** | 既定値承認 | コストが 1 ファイルのコピーで済み、含めない根拠を立てて維持するより安全 |
