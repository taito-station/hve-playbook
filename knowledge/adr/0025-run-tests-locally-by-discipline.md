# テストは CI・hook で自動実行せず、PR を作る前にローカルで全件を流す規律にする

## ステータス

Accepted — 2026-10-15

## 背景と課題

hve-playbook には `.github/workflows/` が無く、pre-push（`.githooks/pre-push`）が実行するのは knowledge の検査（ADR 0014 の dogfood）だけだった。`tests/` の契約テスト（`tests/test_*.sh` の 20 本。`tests/hve_scripts` の Python のテストは `test_hve_scripts.sh` から実行される）は、手で流したときにしか効かない。PR #69（#62）で足した見出しの語の契約テストも、手で流さない限り hook の定数と規則の正本のずれを検出しない（Issue #72）。

手元（macOS）で HOME を一時ディレクトリに向けて全件を流すと、全 PASS で約 405 秒かかった（SKIP は tmux 不在・Chrome 不在の 2 件）。

## 意思決定の要因

- リポジトリオーナーの指示（2026-10-15）: リモートでのテスト（CI）はしない。hook ではなく、規律としてローカルでテストする
- 契約テストの多くは規則・skill の文面を固定するので、ドキュメントだけの変更でも流す必要がある
- 規則は hve-playbook の開発にだけ効き、導入先や `~/.claude` には配られないこと
- 全件で約 7 分かかるので、push のたびや skill の中の push ごとには流さないこと

## 検討した選択肢

- 実行の仕組み: ローカルの規律／GitHub Actions／pre-push／両方
- 規律の置き場所: `.claude/rules/testing.md`（リポジトリ専用）／`.claude/rules/hve-local/implement-flow.md` の検証コマンド／`rules/hve/verification.md`／README だけ
- 実行の方法: 一括実行のスクリプト `tests/run-all.sh`／規則にループを書く

## 決定内容

選択した選択肢: **CI・hook ではテストを実行しない。`.claude/rules/testing.md` に、PR を作る前にローカルで全件を流す規律を書き、全件は `bash tests/run-all.sh` で流す**。

- 流す時点: create-pr を呼ぶ前と、そのあと PR のコミットが変わったら（review-pr の修正、base の取り込み）awaiting にする前の最後のコミット。skill の手順の中の push ごとには流さない。変更がドキュメントだけでも流す
- `tests/run-all.sh` は HOME を一時ディレクトリに向けて `tests/test_*.sh` を 1 本ずつ実行し、本ごとの PASS / FAIL と SKIP の有無を出す。FAIL が 1 本でもあれば exit 1。`scripts/` は sync が `~/.claude/scripts/` に配るので、`tests/` に置く
- FAIL が出たら直してから進む。tmux・Chrome が無い環境での SKIP は FAIL として扱わない。PR 本文の Test plan に最後に流した結果を書く
- `.githooks/pre-push`（knowledge の検査）は変えない
- ADR 0007 の「このリポジトリ自身の `.claude/rules` は `rules/hve` だけを指す」は、`rules/global` を project-level で重ねて読み込ませないための決定で、リポジトリ専用の規則を置くことは妨げない。`tests/test_sync_rules_agents.sh` の検査を「`.claude/rules` 直下は `hve` と `testing.md` だけ」に改め、global を重ねないことは引き続き固定する

### 結果（Consequences）

- 良い結果: PR を作るたびに契約テストが流れ、結果が PR 本文に残る。ドキュメントだけの変更でも流れる。push は遅くならず、CI の設定・保守も要らない
- 悪い結果・既知の限界:
  - 強制力が無い。流し忘れれば、契約テストが落ちる状態のまま main に入りうる。PR 本文の Test plan に結果が無いことで、レビューで気づく
  - 手元の環境（macOS）でしか検証しない。Linux での移植性は確かめない
  - `tests/test_review_pr_contracts.sh` は worktree から流してもメインの checkout の手順書を検査する。worktree で review-pr の手順書を変えたときは、その旨を Test plan に書く

## 選択肢の評価（Pros and Cons）

### ローカルの規律（採用）

#### メリット

- オーナーの指示どおり。CI の設定・費用・保守が要らない
- 規則・skill の文面だけの変更でも流せる

#### デメリット

- 強制力が無い

### GitHub Actions

#### メリット

- 流し忘れが無く、branch protection の必須チェックにすればマージを止められる

#### デメリット

- オーナーの指示（リモートでのテストはしない）に反する
- 手元の macOS 以外で通るかは未検証

### pre-push

#### メリット

- clone ごとに有効にすれば、push の前に必ず流れる

#### デメリット

- オーナーの指示（hook ではなく規律で）に反する
- 全件で約 7 分かかり、`--no-verify` は branching 規約で禁止なので、push のたびに待つことになる
- 有効にしていない clone では効かない

### `.claude/rules/hve-local/implement-flow.md` の検証コマンドに書く

#### メリット

- hve-implement の Step 7 が既に読む仕組みに乗る

#### デメリット

- implement-flow はドキュメントだけの変更を対象外にしており、規則・skill の文面だけを変えたときに流れない
- hve-local は導入先が HVE の標準を補足する置き場所で、hve-playbook 自身は標準を直接編集する（local-overrides.md）

### `rules/hve/verification.md` に書く

#### メリット

- 既存の検証の規則にまとまる

#### デメリット

- 導入先に配られ、hve-playbook のテストを持たない導入先に無関係な指示が届く

### 規則にループを書く（一括実行のスクリプトを作らない）

#### メリット

- ファイルが増えない

#### デメリット

- HOME を差し替えるループは、worktree で動く Claude Code のセッションではガードに止められる
- 実行条件（HOME の隔離）が人によってばらつく

## 関連リンク

- Related: [0007-consolidate-user-level-rules-and-agents](0007-consolidate-user-level-rules-and-agents.md)
- Related: [0014-knowledge-check-scripts-and-sha-follow-up](0014-knowledge-check-scripts-and-sha-follow-up.md)
- Related: [hve-playbook#72](https://github.com/taito-station/hve-playbook/issues/72)
