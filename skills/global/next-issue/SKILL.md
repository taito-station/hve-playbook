---
name: next-issue
description: |
  次に取り組む open の Issue を選ぶとき。並走している他セッションの作業と衝突しない候補を、
  推奨付きで並べたいとき。
  「次の issue 候補」「他セッション考慮して issue 候補出して」のような自然言語でも起動。
---

# next-issue（次に対応する Issue の候補出し）

## 目的

open の Issue から、次に着手する 1 件を推奨付きで選ぶ。並走セッションと同じ Issue・同じファイルに着手して互いに上書きする事故や、未マージの PR を前提にした Issue を推して着手できない手戻りを防ぐ。

## 制約

- 候補は **open の Issue だけ**から出す。「issue 候補」は「次に対応する Issue」の意味で、新しく起票する Issue の候補は出さない（取り違えた前例がある）
- 読み取りだけで完結させる。ファイル・ブランチ・Issue・PR を書き換えない。例外は、ユーザーの確認を得てから送る他セッションへの `SendMessage`（手順 1 の 5）だけ
- 他セッションの担当は推定であることが多い。推定は「（未確認）」と書く

## 手順

### 1. 他セッションの状況を集める

worktree に隔離されたセッション（EnterWorktree の中）では、ほかの worktree や clone に対する `git -C` が拒否されることがある。この skill は primary の checkout から実行する。拒否されて確かめられなかった項目は「未確認」と書く。

1. `ListAgents`（deferred tool なら ToolSearch で読み込む）で、同じリポジトリを扱う peer セッションの名前・busy かどうか・起動時刻を見る。使えない環境（サブエージェントなど）では飛ばし、「peer セッションは未確認」と書く
2. `git worktree list` で worktree ごとのブランチを見て、primary 以外の各 worktree で `git -C <wt> status --short` を見る。`.claude/worktrees/agent-*` はサブエージェントの一時 worktree なので、Issue の担当の判定から外し、件数だけ書く
3. 同じ remote を持つ別の clone（parallel-setup の並走 clone）を探し、各 clone の `git -C <clone> branch --show-current` と `git -C <clone> status --short` を見る。探す場所は primary の兄弟ディレクトリと、parallel-setup の置き場所（`~/repos/<project>-parallel-N`）。remote URL の末尾まで一致したものだけを数える

   ```bash
   find .. ~/repos -maxdepth 3 -path '*/.git/config' 2>/dev/null | xargs grep -lE '[/:]<owner>/<repo>(\.git)?$'
   ```

   glob（`../*/.git/config` など）は使わない。zsh では 1 つでも一致しない glob があるとコマンド全体が止まり、見つかった clone まで返らない。結果には primary 自身も出るので除く

4. open の PR と、PR が閉じる Issue を対応づける。GitHub が解釈したクローズ対象（本文のキーワードと Development 欄のリンク）を使う

   ```bash
   gh pr list --state open --limit 100 --json number,title,headRefName,closingIssuesReferences \
     --jq '.[] | "#\(.number)\t\(.headRefName)\t\(.title)\tcloses: \([.closingIssuesReferences[].number | "#\(.)"] | join(","))"'
   ```

5. ブランチ名（`feat/<issue 番号>-...`）・worktree 名・`closes #N` から、Issue ごとに「誰かが着手しているか」を判定する。PR が無く未コミットの変更だけがある場合は、Issue の最新コメントの日付や、作業ツリーのファイルの更新時刻から、進んでいるのか放置されているのかを推定する。busy のセッションの担当が判然とせず、判定が推奨を左右するときは、`SendMessage` でそのセッションに着手しているかを聞いてよい（他セッションの作業に割り込むので、送る前にユーザーに確かめる）

### 2. open の Issue を取る

```bash
gh issue list --state open --limit 100 --json number,title,labels,updatedAt \
  --jq '.[] | "#\(.number)\t\(.updatedAt[0:10])\t[\(.labels | map(.name) | join(","))]\t\(.title)"'
```

手順 1 の PR・ここの Issue の取得件数が 100 件に達したら、それより古いものを見ていないことを出力に書く。

タイトルで絞った上位の候補だけ、`gh issue view <N> --json body,comments` で本文と最新のコメントを読む。全件の本文は読まない。

### 3. 依存と衝突を調べる

候補ごとに確かめる:

- 依存: 本文やコメントが、未マージの PR や未完了の Issue を前提にしていないか（前提の PR は `gh pr view <N> --json state,mergeable` で状態を見る）
- 衝突: 他セッションのブランチ・PR が触るファイル（`gh pr view <N> --json files`）と、候補が触りそうなファイルが重ならないか
- 採番: ADR など連番の成果物を、他セッションと同時に採ることにならないか

### 4. 評価して並べる

次の順で評価する。

1. 他セッションと衝突しない
2. 依存が解けている
3. 未決事項が少ない（質問票が要らないか）
4. 規模が小さい
5. 実害の大きさ

順位とは別に、実害の大きい Issue やセキュリティの Issue（データの消失・秘密の漏洩・公開リポジトリでの露出など）は、順位が低くても出力で必ず触れ、推奨しない理由を書く。

プロジェクトの CLAUDE.md や handoff に優先順位（ロードマップなど）があれば、そちらを優先する。

### 5. 出力する

次の順で書く。

1. `## 他セッションの状況`: セッション・worktree・clone ごとに、担当している Issue・ブランチと、未コミットの変更の有無
2. 候補表

   | 順 | Issue | 理由・規模 | 未決事項 | 他セッションとの衝突 |
   |---|---|---|---|---|

3. `## 今は避けるもの`: 着手中・依存待ち・判断待ち・衝突のある Issue と、その理由
4. 推奨: 「おすすめは #N です」と 1 件に絞って言い切り、理由を 1〜2 行で添える
5. 着手の提案: `/resolve-issue N` で着手する。ブランチは branching.md の「作業開始時の手順」のとおり worktree に切り、primary の checkout（元の clone）のブランチは切り替えない

着手できる候補が無い（open の Issue が 0 件、またはすべて着手中・依存待ち・判断待ち）なら、候補表と 4・5 は省く。「今は着手できる Issue が無い」と伝えて 3 を示し、knowledge や直近の完了報告の範囲外の項目から起票候補を探すかを聞く。聞く前に探さない。

## 注意事項

- 選んだ Issue への着手は resolve-issue が担う。この skill は選ぶところまでで止まる
- マージ後の片付けに続けて呼ばれることが多い（post-merge-cleanup の最後で聞く）。片付けの直後でも、他セッションの状況は手順 1 で集め直す
