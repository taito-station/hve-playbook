# knowledge の検査スクリプトを同梱し、stale は文書ごとの単一 sha の祖先判定にする

## ステータス

Accepted — 2026-10-04

## 背景と課題

knowledge の標準は、stale 検出と決定ログの不変性検査を「プロジェクトがスクリプトとして実装する」としていた（`rules/hve/knowledge-maturity.md`、`rules/hve/artifact-management.md`）。実装が同梱されていないので、導入先はそれぞれ書くことになる。導入先の paddock は CI と pre-push で運用中の実装を持っており、汎用部分を hve-playbook に還元することを決めた（[taito-station/paddock#754](https://github.com/taito-station/paddock/issues/754)、[hve-playbook#27](https://github.com/taito-station/hve-playbook/issues/27)）。

標準の stale 判定は「source ごとに、記録したフル SHA と現在の SHA が一致しなければ stale」だった。この方式は、source のリネームや frontmatter のメタデータだけの変更でも stale を出す。

問い: どの検査を、どの判定方式で同梱するか。同梱した判定方式が create-pr の squash・rebase と両立するか。

## 意思決定の要因

- 導入先がスクリプトを自作せずに、CI・pre-push・Claude Code の hook に組み込める
- リネームやメタデータだけの変更で偽の stale を出さない
- 既存の運用（Conflict の文書は sha を蒸留前に保つ ADR-0011、決定ログの 2 方式の ADR-0013）と矛盾しない
- create-pr は未 push のブランチを 1 コミットにまとめ（ADR-0008）、push 済みのブランチは rebase する
- 導入先固有の部分（paddock の文書クラス登録簿・REQ-ID・相対リンク検査）は持ち込まない

## 検討した選択肢

- paddock の祖先判定方式（文書ごとの単一 sha）を同梱し、squash・rebase の後は sha の追従コミットを積む
- source ごとの内容ハッシュを記録し、一致しなければ stale にする
- 祖先判定方式を同梱し、squash・rebase の後の追従は規則に書くだけにする

## 決定内容

選択した選択肢: **paddock の祖先判定方式（文書ごとの単一 sha）を同梱し、squash・rebase の後は sha の追従コミットを積む**。paddock で運用実績があり、リネームやメタデータだけの変更を正しく飛ばせる。

- 同梱物: `hve-scripts/` の `check-knowledge.py`（frontmatter の必須項目・sources の実在・祖先判定の stale）、`check-decision-log.py`（決定ログの不変性。2 方式を自動判定）、`bump-distilled-sha.py`（sha の追従）、`hooks/` の 2 本（SessionStart の stale 報告、PostToolUse の影響警告）。setup.sh が導入先の `.claude/scripts/hve/` に削除してから置き直す。配置元を `scripts/` にしないのは、sync-dotclaude.sh が `scripts/*.py` を `~/.claude/scripts/` に配るため
- `distilled_from_sha` は文書ごとに 1 つ（蒸留時点のコミット）。source ごとの SHA マップは廃止し、後方互換は持たない（この形式を使う導入先は paddock だけで、paddock はすでに単一 sha）
- 設定は CLI 引数で渡し、既定値は本標準にする。設定ファイルの形式は作らない。paddock のために `--allow-empty-sources-with-decision-log`（`## 決定ログ` 節を持つ文書は sources と sha が揃って空でよい）と、`.github/workflows/` の `uses:` ピン更新だけの変更を内容の変更と見なさない処理を入れる
- status が `Conflict` の文書は stale でも失敗にせず「解消待ち」として報告し、bump も飛ばす（ADR-0011）
- shallow clone・merge-base が取れないときは、スキップせず exit 2 にする（判定できないことを「問題なし」として通さない）
- 決定ログの検査は、独立ファイル方式のステータス節の外の、同じ行の中の差し替えを警告にする（誤字修正は許されるが機械では判定できない）。節の外での行の追加・削除（行の対応が取れない変更）、ADR の削除・改名、一覧 README の行の削除は error（誤字修正は同じ行の中で済むので、行の追加・削除は決定の書き足し・削除とみなす）。インライン方式のディレクトリ改名に伴うパスの書き換えは、パスとして書かれた部分（ディレクトリ名 1 つなら直後に `/` が続くもの）だけ許し、地の文の旧名は書き換えない
- 検査の目的は善意の誤操作（うっかりした書き換え・蒸留漏れ・リポジトリの破損）の検出に置き、悪意ある改ざんの防御は対象外とする。悪意のある作成者は同じ PR で検査スクリプトや CI を書き換えられ、stale 検査も本物のコミットの sha を書けば黙らせられるので、スクリプトだけでは防げない。改ざんへの備えは PR のレビューと branch protection に任せる
- squash・rebase の後の追従: コミットは自分の sha を含められないので、squash・rebase で sha の指すコミットが履歴から外れた文書は、もう 1 コミット積んで追従させるしかない。create-pr は squash の後に、review-pr（単独起動）は rebase の後の push の前に、`bump-distilled-sha.py --follow-rewritten` で追従コミットを積む。対象は、その PR で変えた文書のうち、sha が HEAD から辿れず、旧 sha と HEAD で sources の中身が同じもの。旧 sha のあとに source が変わった文書は追従しない（本当の stale を隠さないため）。sha が辿れるかで判定するのは、手元に古いコミットが残っていると stale の判定では外れたことが分からないため（新しく clone すると sha を解決できない）。これにより ADR-0008 の「未 push のブランチから作った PR は 1 コミット」に例外ができるので、ADR-0008 を Partially superseded にする
- push 済みのブランチは rebase のたびに sha が外れるので、追従コミットがそのたびに 1 つ増える
- この方式は、PR を merge commit でマージすることを前提にする。GitHub の squash merge・rebase merge でマージすると、追従させた sha（PR ブランチのコミット）が main から辿れず、以後の CI が落ち続ける（branching の規約は merge commit を定めている。hve-playbook のリポジトリ設定は別 issue で揃える）
- paddock の影響警告 hook は PostToolUse で無効な出力（`{"decision": "warn"}`）を返していたので、`systemMessage` と `hookSpecificOutput.additionalContext` で出すように直して同梱する
- hve-playbook 自身の `knowledge/` は `adr/` だけなので、`knowledge/adr/` と README は frontmatter 標準の対象外と明記する。dogfood は、tests/ での両検査の実行と、hve-playbook の pre-push（`.githooks/pre-push`）で行う

### 結果（Consequences）

- 良い結果: 導入先は `.claude/scripts/hve/` のスクリプトを CI・pre-push・hook から呼ぶだけで、stale 検出と決定ログの検査を組み込める。リネームやメタデータだけの変更で偽の stale が出ない。Conflict の文書が 1 本あるだけで CI が落ち続けることがない
- 悪い結果: squash・rebase の後に追従コミットが要り、knowledge 文書を変えた PR は 2 コミットになることがある。追従を create-pr・review-pr の手順に組み込んだので、手で squash・rebase したときは人が追従させる必要がある。source ごとの SHA マップを使っていた導入先があれば移行が要る（現時点では無い）。独立ファイル方式の誤字修正の判定は人に残る

## 選択肢の評価（Pros and Cons）

### 祖先判定方式を同梱し、squash・rebase の後は追従コミットを積む（採用）

paddock の実装の汎用部分を移植し、create-pr・review-pr に追従の手順を足す。

#### メリット

- paddock で運用実績がある
- paddock は同梱版へそのまま切り替えられる

#### デメリット

- create-pr・review-pr の手順と ADR-0008 に例外が増える

### source ごとの内容ハッシュを記録する（却下）

`distilled_from_sha` の代わりに、source ごとの内容のハッシュを frontmatter に記録する。

#### メリット

- squash・rebase の影響を受けない

#### デメリット

- メタデータだけの変更やリネームを飛ばすには、ハッシュの正規化を別に設計する必要がある
- paddock の全文書の移行が要り、paddock #754 で決めた単一 sha の運用を覆す

### 追従は規則に書くだけにする（却下）

祖先判定方式を同梱し、「squash・rebase の後は bump し直す」と knowledge-maturity に書くだけにする。

#### メリット

- create-pr・review-pr を変えなくてよい

#### デメリット

- 手順が人頼みになり、create-pr が squash した PR は CI で必ず stale になる。ADR-0008 の 1 コミットの規則とも食い違ったまま残る

## 関連リンク

- Partially supersedes: [0008-one-commit-per-pr-and-history-based-commit-format](0008-one-commit-per-pr-and-history-based-commit-format.md)
- Related: [0011-advance-updated-only-on-substantive-change](0011-advance-updated-only-on-substantive-change.md)
- Related: [0013-decision-log-file-or-inline-modes](0013-decision-log-file-or-inline-modes.md)
- Related: [knowledge-maturity ルール](../../rules/hve/knowledge-maturity.md)
