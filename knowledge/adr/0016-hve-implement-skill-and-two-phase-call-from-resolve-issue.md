# implement-flow の実行手順を hve-implement skill として配り、resolve-issue からは 2 段で呼ぶ

## ステータス

Accepted — 2026-10-05

## 背景と課題

`rules/hve/implement-flow.md` は Step 0〜8 のゲートを定めるが、それを順に実行する手順は配布していなかった。導入先の paddock は自前の `/implement` skill を持ち、そこに検索コマンドのパスや固有の検証コマンドを書き込んでいた。同じ手順を他の導入先でも使えるよう、汎用化して還元する（[hve-playbook#45](https://github.com/taito-station/hve-playbook/issues/45)）。

一方、Issue 対応は global の resolve-issue skill が Step 0〜8 に相当する流れ（Issue 分析・Plan・PO 承認・実装・PR）を持つ。implement-flow の Knowledge 検索・棄却済み案チェック・質問票（Step 2〜4）を計画の段階で飛ばして差し戻された事故があり、それを防ぐことも目的に含む。

問い: 実行手順をどこに置き、resolve-issue とどう分担するか。

## 意思決定の要因

- 導入先が作者の `~/.claude` や paddock 固有の値に依存しない（ADR-0002・ADR-0007）
- Step 2〜4 の STOP（既存実装との矛盾・棄却済み案との衝突・ブロッキングな不明点）が、PO の承認より前に出る
- resolve-issue と hve-implement で、質問票・ADR・テスト失敗時の止め方を二重に持たない
- プロジェクト固有の差分は hve-local に書ける（ADR-0012）

## 検討した選択肢

- hve-implement を単独でも使え、resolve-issue からは Step 2〜4（計画の前）と Step 5〜7（実装）の 2 段で呼ぶ
- resolve-issue からは Step 3 で Step 2〜7 を 1 回で呼ぶ
- resolve-issue を hve-implement に置き換え、Issue 対応も hve-implement が担う
- skill を配らず、規約（implement-flow.md）だけを配り続ける

## 決定内容

選択した選択肢: **hve-implement を単独でも使え、resolve-issue からは 2 段で呼ぶ**。

- `skills/hve-implement/SKILL.md` を配る（setup.sh の `skills/hve-*` の一括コピーに乗る）。規約の正本は implement-flow.md のままで、skill は実行手順だけを持つ
- 単独モードは Step 0〜8 を実行する。Step 1〜4 を Plan モードで進め、Step 4 の後に計画の承認を得てから Step 5 へ進む。`--depth` はブランチの type で決める（`fix` → lightweight、それ以外 → full）
- resolve-issue は `.claude/skills/hve-implement/SKILL.md` があるときだけ、bug / feature パスで `--phase pre`（Step 2〜4）を計画・修正方針の前に、`--phase post`（Step 5〜7）を Step 3 の実装で呼ぶ。Step 0・1・8 は resolve-issue が持つ。ops パスとドキュメントのみの変更は対象外
- 重なる手順は hve-implement 側に寄せる: 質問票は Step 4（回答の探索順は resolve-issue の手順）、ADR は Step 7、テストの 3 回失敗は Step 6 の STOP のあと resolve-issue の revert とエスカレーション
- 固有の差分は `.claude/rules/hve-local/hve-implement.md` と `.claude/rules/hve-local/implement-flow.md` に書く。Step 7 は hve-local に検証コマンドがあればそれだけを実行し、無ければ同梱の検査スクリプト（`.claude/scripts/hve/`、hve-playbook 自身は `hve-scripts/`）を実行する
- create-pr / review-pr は、hve-implement の単独モードを `--depth` の決定者として認める

### 結果（Consequences）

- 良い結果: Step 2〜4 の STOP が承認前に出るので、承認済みの計画を作り直さずに済む。他の導入先も同じ手順で implement-flow を実行できる
- 悪い結果: resolve-issue の手順に分岐が増える。導入先に自前の実装 skill がある間は、自然言語のトリガーが衝突しうる（paddock は [paddock#756](https://github.com/taito-station/paddock/issues/756) で置き換える）

## 選択肢の評価（Pros and Cons）

### 2 段で呼ぶ

#### メリット

- implement-flow の順序（Step 2〜4 を計画の前に）を resolve-issue でも守れる

#### デメリット

- resolve-issue からの呼び出しが 2 か所になる

### Step 3 で 1 回で呼ぶ

#### メリット

- resolve-issue の変更が 1 か所で済む

#### デメリット

- Step 2〜4 が PO の承認後に回り、STOP のたびに承認済みの計画を作り直すことになる

### resolve-issue を置き換える

#### メリット

- 実装の流れが 1 つの skill にまとまる

#### デメリット

- resolve-issue が持つパス選択・本番データ調査・ブラウザテスト・ステップ間ゲートを移す必要があり、Issue の範囲を超える

### 規約だけを配る

#### メリット

- 配布物が増えない

#### デメリット

- 導入先ごとに実行手順を書くことになり、固有の値が手順に混ざる（paddock の現状）

## 関連リンク

- Related: [0012-project-local-overrides-in-hve-local](0012-project-local-overrides-in-hve-local.md)
- Related: [0014-knowledge-check-scripts-and-sha-follow-up](0014-knowledge-check-scripts-and-sha-follow-up.md)
- Related: [hve-playbook#45](https://github.com/taito-station/hve-playbook/issues/45)
