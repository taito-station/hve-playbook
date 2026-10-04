# knowledge 検査スクリプトの同梱（#27）

- Issue: https://github.com/taito-station/hve-playbook/issues/27
- ブランチ: `feat/27-knowledge-check-scripts`
- 進捗: タスク 1〜8 完了、ステップ間ゲート PASS（2 回目。sha 追従を --follow-rewritten に変更）。PR 作成へ

## 背景

knowledge の標準は、stale 検出と決定ログの不変性検査を「プロジェクトがスクリプトとして実装する」としている（`rules/hve/knowledge-maturity.md`、`rules/hve/artifact-management.md`）。導入先の paddock には CI と pre-push で運用中の実装があり（paddock #754 で hve-playbook への還元を決定）、その汎用部分を同梱して、導入先が自作せずに組み込めるようにする。

## 確定事項

| 論点 | 決定 | 出典 |
|---|---|---|
| 同梱範囲 | stale 判定・frontmatter 必須項目・sources 実在・bump・決定ログ不変性検査・hook 2 本。文書クラス登録簿・REQ-ID・相対リンク検査は paddock に残す | 2026-10-04 質問票（paddock #754 の還元計画） |
| sha の形式 | 文書ごとの単一 `distilled_from_sha`。source ごとの SHA マップは廃止し、後方互換は持たない | 同上 |
| 設定 | CLI 引数で渡す（既定値は hve の標準）。設定ファイル形式は作らない | 同上 |
| 配置 | 配置元 `hve-scripts/`（`scripts/*.py` は sync-dotclaude.sh が `~/.claude/scripts/` に配るので混ぜない）→ setup.sh が導入先の `.claude/scripts/hve/` に削除してからコピー | 同上 |
| hook | 2 本とも同梱し、settings.json への配線は導入先が手で行う。影響警告の hook は、PostToolUse で有効な出力形式に直す | 2026-10-04 回答 |
| Conflict | status が Conflict の文書は stale と分けて「解消待ち」と報告し、失敗にしない。bump も Conflict の文書を飛ばす（ADR 0011） | 2026-10-04 回答、#28 の申し送り |
| 独立ファイル方式の範囲外の変更 | 既存 ADR の `## ステータス` 節の外の、同じ行の中の差し替えは警告（exit 0）。節の外での行の追加・削除、ADR ファイルの削除・改名、一覧 README の行の削除は error。README のステータス列以外の変更は警告 | 2026-10-04 回答、改訂版の承認、PR #41 レビュー F8 の回答（2026-10-05） |
| GitHub のマージ方式 | knowledge 文書を持つリポジトリは PR を merge commit でマージする（squash・rebase merge では追従した sha が main から辿れない）。hve-playbook のリポジトリ設定の変更は別 issue | PR #41 レビュー F20 の回答（2026-10-05） |
| dogfood | `knowledge/adr/` は frontmatter 標準の対象外と明記する。tests/ でこのリポジトリに対して両検査を流し、hve-playbook 自身の pre-push にも配線する | 2026-10-04 回答 |
| 決定ログの方式 | #26（ADR 0013）の 2 方式を扱う。インライン方式でも `knowledge/adr/` に ADR が残っていれば独立ファイル方式の検査も当てる | #26 の申し送り |
| squash・rebase との両立 | create-pr の squash の後と、push 済みブランチの rebase の後に、この PR で変えた文書が stale なら bump して「sha 追従コミット」を 1 つ積む。ADR 0008（1 PR 1 コミット）に例外として足す（0008 は Partially superseded） | 2026-10-04 回答（敵対的レビュー C1） |
| sources が空の文書 | 既定は sources 必須。`--allow-empty-sources-with-decision-log` を付けたときだけ、`## 決定ログ` 節を持つ文書は sources・sha が空でよい（stale 判定しない） | 2026-10-04 回答（敵対的レビュー M1） |

前提（軽微。明示して進める）:

- 書き込む sha はフル 40 桁。読むときは `git rev-parse` で解決できれば短縮形も受け付ける（paddock の既存の値を壊さない）
- 必須項目と対象ディレクトリは CLI 引数。既定は hve の標準（`title,status,kind,sources,distilled_from_sha,updated`）、`knowledge/` を再帰し `adr/` と `README.md` を除く
- merge-base が取れないときはスキップせず exit 2（#26 の申し送り。paddock は `HEAD~1` に落として exit 0）
- Python は標準ライブラリだけ。3.9 以上を想定し、検証は手元の 3.13 で行う
- 比べる対象: 既定は merge-base と作業ツリー（AKM の未コミットの編集と手での実行を見る）。pre-push は stdin の push する ref を読み、`--head <sha>` で渡す
- git の出力を固定する: `--no-ext-diff --no-textconv --no-color --text`、`-c core.quotePath=false -c diff.noprefix=false -c diff.mnemonicPrefix=false`。リネーム検出は、インライン方式のディレクトリ付け替えの許容と、独立ファイル方式の ADR 改名の検出に使う呼び出しだけで有効にする
- shallow clone で履歴が足りないときは、stale 検査・決定ログ検査とも exit 2。CI の例には `fetch-depth: 0` を必須として書く
- 独立ファイル方式: 一覧 README のステータス列以外の変更も、ADR 本文と同じく WARN（誤字修正を許す標準と揃える）。README のステータス列と ADR のステータス節の食い違いも WARN。error は ADR ファイルの削除・改名と README の行の削除。どの検査も `--warn-only` で exit 0 にできる
- 決定ログの方式は自動判定だけにする（`--mode` と見出しの正規表現の引数は作らない。見出しは `## 決定ログ` と `## ステータス` に固定）
- `uses:` のピン更新だけの変更のスキップは、paddock の移行に要るので残す（ADR に理由を書く）
- 解消待ち（Conflict）の件数は、0 件でもサマリーに必ず出す

## 構成

```
hve-scripts/
├── check-knowledge.py          # frontmatter 必須項目・sources 実在・祖先判定 stale・Conflict 分離
├── check-decision-log.py       # 決定ログの不変性（file / inline / auto）
├── bump-distilled-sha.py       # stale 文書の sha を一括で追従（Conflict は飛ばす）
└── hooks/
    ├── session-stale-check.sh  # SessionStart で stale を報告
    └── check-knowledge-impact.py  # source 編集時の影響警告、knowledge 直接編集時の SoT 逆転警告
tests/
├── test_hve_scripts.sh         # 下の Python テストと dogfood をまとめて実行（既存の bash 流儀）
└── hve_scripts/test_*.py       # 自走式（標準ライブラリだけ。fixture は一時 git リポジトリ）
.githooks/pre-push              # hve-playbook 自身の pre-push（core.hooksPath で有効化）
```

## タスク

| # | 内容 | 完了条件 | 依存 | 担当 |
|---|---|---|---|---|
| 1 | `check-knowledge.py` と テスト。paddock `check-doc-classes.py` の汎用部分（frontmatter 解析、sources の正規形・実在・大文字小文字、祖先判定の stale、R100 リネーム・メタデータだけ・`uses:` ピンだけの変更のスキップ、走査打ち切りの fail-closed）を移植。Conflict を「解消待ち」に分離。対象ディレクトリの再帰と除外。`--required`・`--allow-empty-sources-with-decision-log`・`--warn-only`。STALE 行の書式を paddock と同じにし docstring にパース契約を書く | テストで、stale 系・リネーム・メタデータ・ピン・予算超過・Conflict（件数 0 でもサマリー）・必須項目欠落・sources 不在・空 sources の例外・shallow で exit 2 のケースが PASS。終了コード 0 / 1 / 2 | — | impl-sonnet |
| 2 | `check-decision-log.py` と テスト。インライン方式は paddock の前方一致比較（コードフェンス除外・ディレクトリのリネーム許容）を移植し、`knowledge/` を再帰。独立ファイル方式は ADR 全文をステータス節を除いて比較（範囲外は WARN）、一覧 README（ステータス列以外は WARN、ステータス節との食い違いも WARN）、ADR の削除・改名と README の行の削除は error。方式は自動判定。`--base`・`--head`・`--warn-only`。merge-base が取れなければ exit 2。git の出力を固定する（前提を参照） | テストで、正規の supersede が通る、範囲外が WARN、削除・改名・行削除が error、インライン方式の改変・挿入が error、末尾追記が通る、日本語ファイル名、ext-diff / textconv / noprefix の設定下でも検出、merge-base なしで exit 2、作業ツリーと `--head` の両方が PASS | — | impl-sonnet |
| 3 | `bump-distilled-sha.py` と テスト。checker を `check-knowledge.py` に向け、フル SHA を書く。Conflict の文書は飛ばして報告 | テストで、`--all-stale --dry-run`、`--sha`、Conflict を飛ばす、checker の他の error で exit 1、出力文言（「STALE な文書は無い」「（dry-run）」）が PASS | 1 | impl-sonnet |
| 4 | hook 2 本と テスト。パスはスクリプトの位置から解決。影響警告は PostToolUse で有効な形式（`systemMessage` と `hookSpecificOutput`（`hookEventName: "PostToolUse"`、`additionalContext`））で出す | テストで、stale あり・なしの報告、source 編集・knowledge 直接編集の警告形式が PASS | 1, 3 | impl-sonnet |
| 5 | `setup.sh` で `hve-scripts/` を `.claude/scripts/hve/` に配置（削除してからコピー）。完了メッセージで CI・pre-push・hook の組み込み方を案内 | `tests/test_sync_rules_agents.sh` に、配置と再適用での置き直しのケースを追加して PASS。一時 target で各スクリプトが `--help` で動く | 1〜4 | メインループ |
| 6 | create-pr・review-pr: squash の後と rebase の後に、この PR で変えた knowledge 文書が stale なら（`.claude/scripts/hve/` か `hve-scripts/` に checker があるときだけ）bump して sha 追従コミットを積む | `tests/test_review_pr_contracts.sh` などの既存テストが PASS。手順が create-pr Step 6・review-pr Step 1 と矛盾しない | 3 | メインループ |
| 7 | 文書: `knowledge-maturity.md`（単一 sha の形式、祖先判定、Conflict の扱い、STALE 行のパース契約、`knowledge/adr/` は frontmatter 標準の対象外、squash・rebase 後の追従、CI（`fetch-depth: 0`）/ pre-push / hook（`"$CLAUDE_PROJECT_DIR"` で絶対パス）の組み込み例、空 sources の引数）、`artifact-management.md` の「機械検査」をスクリプトに差し替え（手のコマンドは補助として残す）、`hve-akm` の Step 1〜3（stale 検出・sha の書き方と bump の時機・機械検査）、`local-overrides.md`・`apply-hve-playbook.md`・`README.md` の写し一覧に `.claude/scripts/hve/` を追加、ADR 0014（ADR 0008 を Partially superseded に）と一覧の行 | 文書の参照先が実在し、drift テストを含む全テストが PASS | 1〜6 | メインループ |
| 8 | dogfood: `.githooks/pre-push`（stdin の ref を読んで両検査を実行）、`.gitattributes` に `.githooks/*` と `*.py` の `eol=lf`、README に `git config core.hooksPath .githooks` の案内、`tests/test_hve_scripts.sh` でこのリポジトリに対して両検査を実行 | このリポジトリで stale 検査が対象 0 本で成功、不変性検査が成功（96f73b1 相当の書き換えも通る）。pre-push が違反を止めることを一時リポジトリで確認 | 1, 2 | メインループ |

タスク 1 と 2 は並列可（別ファイル）。各タスクの後にレビューゲート（完了条件と計画からの逸脱の確認）を挟む。PR は 1 本（create-pr `--depth full`）。

## 検証

- `for f in tests/*.sh; do bash "$f" || echo "FAIL $f"; done` で FAIL 0 件
- `python3 hve-scripts/check-knowledge.py` と `python3 hve-scripts/check-decision-log.py` をこのリポジトリで実行して exit 0
- setup.sh を一時 target に実行し、`.claude/scripts/hve/` の各スクリプトが `--help` で動く

## 申し送り（範囲外）

- paddock 側で同梱版へ切り替える作業（再適用・CI と pre-push の呼び出し先の変更・paddock 固有の検査の残し方）は paddock #756
- paddock の `check-knowledge-impact.py` の出力形式の不具合は paddock 側にも伝える
