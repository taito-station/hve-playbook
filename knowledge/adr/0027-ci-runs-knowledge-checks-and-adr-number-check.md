# PR の CI で knowledge の検査と ADR の番号の重複検査を流し、main の必須チェックにする

## ステータス

Accepted — 2026-10-18

## 背景と課題

ADR の番号は、配置先の最大値 +1 で採番する（documentation-standards）。並行して進む 2 本のブランチが、どちらも同じ時点の main を見て採番すると、同じ番号を取る。ブランチを 1 本ずつ見れば正常なので、ローカルの規律（ADR 0025）や pre-push（`.githooks/pre-push`）では検出できない。どちらも一覧 `README.md` の末尾に行を足すので、多くはまず README の merge conflict として表に出る。しかし衝突を解くときに両方の行を残すと、番号の重複はそのまま main に入る。2026-10-18 の時点で、main と remote の全ブランチを横断しても番号の重複は無かった。

`check-decision-log.py` は ADR の削除・改名・本文の書き換えを検査するが、番号の重複は見ていなかった（ステータスの突き合わせは番号をキーにしているので、重複があると片方が黙って上書きされる）。

hve-playbook には CI が無い。ADR 0025 で、リポジトリオーナーの指示（リモートでのテストはしない）により GitHub Actions を却下した。

## 意思決定の要因

- リポジトリオーナーの指示（2026-10-18）: 番号の重複を CI で検出したい。CI で流すのは軽い検査だけにし、`tests/` の全件はローカルの規律のままにする。main の必須チェックにして、「Require branches to be up to date」も有効にする
- 番号の重複は、main と合わせた状態で検査しないと検出できない
- knowledge の検査（ADR 0014）は数秒で終わり、macOS 固有の前提を持たない
- リポジトリオーナーの判断（2026-10-19）: 番号は 4 桁連番だけを前提にし、日付で名付ける運用は想定しない（日付にすると、更新や supersede のときに番号の扱いで迷う）。管理者にも必須チェックを課す（`enforce_admins`）

## 検討した選択肢

- 軽い検査だけを CI で流す（`check-knowledge.py`・`check-decision-log.py`。番号の重複検査は `check-decision-log.py` に足す）
- `tests/` の全件も CI で流す（ADR 0025 をほぼ全面的に置き換える）
- CI は置かず、番号の重複検査をローカルのスクリプト・pre-push に足すだけにする

## 決定内容

選択した選択肢: **軽い検査だけを CI で流す**。

- `check-decision-log.py` の独立ファイル方式に、ファイル名の先頭の 4 桁連番（`NNNN-`。documentation-standards の採番）が同じ ADR が複数あれば error にする検査を足す。名前の途中の数字（`adopt-iso-8601.md` の 8601 など）は番号とみなさない。4 桁連番で始まらない名前は検査しない。base に ADR ディレクトリが無い（この変更で作った）ときも検査する。その番号のファイルがすべて base にあった（base の時点から重複していた）なら警告にとどめ、1 本でも新しく足していれば error にする（解消できない既存の重複のせいで、無関係な PR を通せなくなるのを避ける。`## 決定ログ` 見出しの重複と同じ扱い）。インライン方式の ID（`### ADR NNNN`）は、導入先が hve-local で形式を変えられるので対象にしない
- `.github/workflows/knowledge-check.yml` を置き、main への pull request で `check-knowledge.py` と `check-decision-log.py --base origin/<base> --head HEAD` を流す。`pull_request` の HEAD は main との merge commit なので、他の PR が先に main へ入れた番号との重複は「base に無い重複」として error になる。履歴を遡るので `fetch-depth: 0` で取得する
- main の branch protection で、この job（`knowledge-check`）を必須チェックにし、「Require branches to be up to date」（`strict`）を有効にする。チェックが通ったあとに別の PR が main に入ったら、base を取り込んで流し直さないとマージできない。workflow が main に入る前に必須チェックにすると、他の PR が来ないチェックを待ち続けるので、設定はこの決定を入れた PR のマージ後に行う。設定と確認は次のとおり（外れたときもこれで戻す）

  ```bash
  # 設定（保護が無い状態から。既存の保護があるときは、先に読み出して他の項目を引き継ぐ）。
  # app_id 15368 は GitHub Actions（gh api /apps/github-actions）。報告元を固定し、同じ名前の別の status では通さない
  echo '{"required_status_checks":{"strict":true,"checks":[{"context":"knowledge-check","app_id":15368}]},"enforce_admins":true,"required_pull_request_reviews":null,"restrictions":null}' | gh api -X PUT repos/taito-station/hve-playbook/branches/main/protection --input -
  # 確認（strict が true、checks に knowledge-check と app_id 15368、enforce_admins が true であること）
  gh api repos/taito-station/hve-playbook/branches/main/protection --jq '{strict: .required_status_checks.strict, checks: .required_status_checks.checks, enforce_admins: .enforce_admins.enabled}'
  ```
- 管理者にも必須チェックと `strict` を課す（`enforce_admins: true`）。マージするのは主にリポジトリオーナー自身なので、管理者が迂回できると番号の重複を止める目的が効かない
- `tests/` の全件は、ADR 0025 のとおり CI・hook で流さない

### 結果（Consequences）

- 良い結果: 並行ブランチの番号の重複を、マージの前に止められる。knowledge 文書の stale・sources の欠落・決定ログの書き換えも、pre-push を有効にしていない clone からの PR で検出できる
- 悪い結果・既知の限界:
  - 他の PR が main に入るたびに、base を取り込んで CI を流し直す手間が増える（create-pr は base を同期するので、作成時の影響は小さい）
  - 管理者もこの CI が通るまでマージできない。CI が動かないときなどの緊急時は、`gh api` で保護を一時的に外し、上の設定コマンドで戻す
  - 4 桁連番で始まらない名前（日付始まりなど、規約外の名前）の ADR は番号の重複を検査しない。日付始まり（`2026-10-18-x.md`）は先頭の 4 桁が年になり、同じ年の ADR が同じ番号に見える。どちらもこの検査の前提の外にする
  - 一覧 README の行の番号の重複は検査しない（ファイルの番号が一意なら、README の行も別の番号になるため）
  - 番号を振り直すときは、旧い番号の ADR を消して新しい番号で足すことになる。base に無い ADR なので、決定ログの不変性の検査には掛からない
  - base の時点からある重複は解消できない（解消には base の ADR の改名・削除が要り、決定ログの不変性の検査が error にする）。そのまま残し、警告は出続ける

## 選択肢の評価（Pros and Cons）

### 軽い検査だけを CI で流す（採用）

#### メリット

- 番号の重複を検出できる唯一の位置（main との merge commit）で検査できる
- 数秒で終わり、Linux への移植の手間がほぼ無い

#### デメリット

- 契約テスト（`tests/`）の流し忘れは、引き続き CI では止まらない

### `tests/` の全件も CI で流す

#### メリット

- 契約テストの流し忘れも止められる

#### デメリット

- オーナーの指示（tests はローカルの規律のまま）に反する
- 全件で約 7 分かかり、Linux で通るかは未検証（ADR 0025）

### CI は置かず、ローカル・pre-push に足すだけにする

#### メリット

- ADR 0025 を変えずに済む

#### デメリット

- ブランチ単体では重複が起きていないので、並行ブランチの番号の重複を検出できない

## 関連リンク

- Supersedes: [0025-run-tests-locally-by-discipline](0025-run-tests-locally-by-discipline.md)（一部。CI を置かない部分）
- Related: [0014-knowledge-check-scripts-and-sha-follow-up](0014-knowledge-check-scripts-and-sha-follow-up.md)
