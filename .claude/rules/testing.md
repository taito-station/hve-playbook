# テスト実行規律（hve-playbook の開発）

hve-playbook の `tests/`（hook・skill・規則の契約テストなど）は、CI でも git hook でも自動実行しない。PR を作る人が、ローカルで全件を実行する（ADR 0025）。この規則は hve-playbook の開発にだけ適用する（`.claude/rules/` 直下は導入先にも `~/.claude` にも配られない）。

## いつ流すか

- create-pr を呼ぶ前に、全件を流す
- そのあと PR のコミットが変わったら（review-pr の修正、base の取り込み）、PR を awaiting にする前に、最後のコミットでもう一度全件を流す
- skill の手順の中の push ごとには流さない

変更がドキュメントだけでも流す。規則・skill の文面を固定する契約テストがあるため。

## どう流すか

```bash
bash tests/run-all.sh
```

- HOME を一時ディレクトリに向けて `tests/test_*.sh` を 1 本ずつ実行し、本ごとの PASS / FAIL と SKIP の有無を出す。FAIL が 1 本でもあれば exit 1
- 全件で約 7 分かかる。サブエージェントに任せる
- worktree で作業しているときも worktree の中で流す。ただし `tests/test_review_pr_contracts.sh` だけは、worktree から実行してもメインの checkout の手順書を検査する（ファイル冒頭のコメント参照）。review-pr の手順書を変えたときは、この 1 本がブランチの変更を検査していないことを Test plan に書く

## 結果の扱い

- FAIL が出たら直してから進む（PR を作らない、awaiting にしない）
- tmux・Chrome が無い環境での SKIP は FAIL として扱わない。SKIP したテストを結果に書く
- PR 本文の Test plan に、最後に流した結果（PASS・FAIL の数と SKIP したテスト）を書く
