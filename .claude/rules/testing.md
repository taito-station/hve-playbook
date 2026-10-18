# テスト実行規律（hve-playbook の開発）

hve-playbook の `tests/`（hook・skill・規則の契約テストなど）は、CI でも git hook でも自動実行しない。PR を作る人が、ローカルで全件を実行する（ADR 0025）。この規則は hve-playbook の開発にだけ適用する（`.claude/rules/` 直下は導入先にも `~/.claude` にも配られない）。

## いつ流すか

- create-pr を呼ぶ前に、全件を流す
- create-pr の中では、Step 5（review-pr）が戻ったあと、Step 6（squash）の前に、そのときのコミットでもう一度全件を流し、`docs/temp/pr-body.md` の Test plan に結果を書く。review-pr の修正や base の取り込みでコミットが変わっていなければ、この回は省いてよい
- review-pr を単独で起動して PR のコミットを変えたときは、push の前に全件を流し、PR 本文の Test plan を更新する
- skill の手順の中の push ごとには流さない

変更がドキュメントだけでも流す。規則・skill の文面を固定する契約テストがあるため。resolve-issue の「ドキュメントのみの変更はテストをスキップする」より、このリポジトリではこの規則を優先する。

## どう流すか

```bash
bash tests/run-all.sh
```

- HOME を一時ディレクトリに向けて `tests/test_*.sh` を 1 本ずつ実行し、本ごとの PASS / FAIL と SKIP の有無を出す。FAIL が 1 本でもあれば exit 1
- 全件で約 7 分かかる。Bash の既定のタイムアウト（120 秒）では打ち切られるので、`timeout` を 600000 にするか `run_in_background` で流す。サブエージェントに任せるときは worktree を分けない（`isolation: "worktree"` の worktree は親 HEAD から作られ、未コミットの変更を見ない）
- worktree で作業しているときも worktree の中で流す。ただし `tests/test_review_pr_contracts.sh` だけは、worktree から実行してもメインの checkout の手順書を検査する（ファイル冒頭のコメント参照）。review-pr の手順書を変えたときは、この 1 本がブランチの変更を検査していないことを Test plan に書く

## 結果の扱い

- FAIL が出たら直してから進む。create-pr の中で FAIL が出たら Step 6 に進まず、直してから流し直すか、止まってユーザーに報告する
- テストが自分で SKIP を出して exit 0 で終わったもの（tmux・python3・node が無い、PATH に google-chrome / chromium が無いなど）は FAIL として扱わない。SKIP したテストと理由を結果に書く
- PR 本文の Test plan に、最後に流した結果（PASS・FAIL の数と SKIP したテスト）を書く
