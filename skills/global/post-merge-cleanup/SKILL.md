---
name: post-merge-cleanup
description: |
  PR をマージしたあとに、マージ済みの作業ブランチと worktree を片付け、デフォルトブランチを最新にするとき。
  「ブランチ整理して」「worktree を片付けて」「マージ後の片付け」のような自然言語でも起動。
---

# post-merge-cleanup（マージ後の片付け）

## 目的

マージ済みの PR の作業ブランチと worktree を、取りこぼしなく、かつ失うものを出さずに片付ける。
次の事故を防ぐ。

- worktree の中で `gh pr merge --delete-branch` を実行すると、作業ブランチが消えたあと worktree がデフォルトブランチに切り替わる。そのまま worktree をブランチごと消すと、デフォルトブランチを消しかねない
- 並走している他セッションの worktree を消して、作業を失わせる
- マージ時の自動削除で消えているリモートブランチを消そうとして、hook に止められる

## 制約

- マージはこの skill で行わない。マージはユーザーの判断（create-pr・resolve-issue も「マージ判断してください」で止まる）
- `git worktree remove --force` を使わない。`git branch -D` は、デフォルトブランチに入っていることを確かめたあとにだけ使う。失うものがあれば止まって報告する
- リモートブランチを消さない。残っていたら報告して聞く
- 他セッションの worktree・clone を守る。消す worktree は次のものだけ
  - 手順 3 の自分の worktree（条件を確かめたもの）
  - 手順 4 の孤児の掃除の対象（lock の pid が死んだもの）
  - 手順 5 の条件をすべて満たすもの
  - 手順 5 でユーザーに確かめて許可を得たもの
- merge commit でのマージ（branching.md）を前提にする。squash・rebase でマージするリポジトリでは、ブランチの tip がデフォルトブランチの祖先にならないので、何も消さずに報告だけになる

## 手順

以下の `<default>` はデフォルトブランチ名。`gh repo view --json defaultBranchRef -q .defaultBranchRef.name` で取得する（`main` と決め打ちしない）。

worktree に隔離されたセッション（EnterWorktree の中）では、ほかの worktree や primary に対する `git -C` が拒否されることがある。そのため、自分の worktree の片付け（手順 3）を先に済ませ、primary に戻ってから手順 4 以降を行う。

### 1. 対象の PR を決める

- 引数に PR 番号があればその PR、無ければカレントブランチの PR を対象にする

  ```bash
  gh pr view [<N>] --json number,state,headRefName,headRefOid
  ```

- 対象の PR の `state` が `MERGED` でなければ（OPEN・CLOSED）、状態を報告して止まる
- 引数が無く、カレントブランチに PR も無い（primary のデフォルトブランチから呼んだとき、worktree が `--delete-branch` でデフォルトブランチに切り替わったときなど）ときは、対象の PR なしで進める。省くのは手順 7 だけで、ほかの手順はすべて行う

### 2. リモートとマージ済みの PR を取り込む

```bash
git fetch --prune origin
gh pr list --state merged --limit 200 --json number,headRefName,headRefOid
```

以降、「マージ済みの PR に対応する」とは、次の 2 つを両方満たすことを指す。

- PR 一覧に、`headRefName` がそのブランチ名と同じ PR がある
- そのブランチの tip（worktree なら HEAD）が、その PR の `headRefOid` と同じか、その祖先である（`git merge-base --is-ancestor <tip> <headRefOid>`）。同じ名前の PR が複数あれば、いずれか 1 つで満たせばよい

ブランチ名の一致だけで判定しないのは、マージ済みの名前を再利用して origin/`<default>` から切ったばかりの他セッションのブランチを、マージ済みと取り違えないため。デフォルトブランチ自体は常に対象外とする。一覧の 200 件より古い PR のブランチは「対応なし」になり、残る（安全側）。

### 3. 自分のいる worktree を片付ける

対象の PR の有無にかかわらず、このセッションが primary 以外の worktree の中にいれば、ほかの手順より先に行う。

1. worktree のパスと、いま checkout しているブランチ名（`git branch --show-current`。detached なら空）を控える。手順 6 で使う
2. 抜ける前に、worktree の中で手順 5 の条件（lock を除く。ignored のファイルの扱いを含む）を確かめる。worktree の中での `git status`・`git merge-base` と `gh` は拒否されない。ブランチがデフォルトブランチ・detached のときは、手順 5 の「PR を特定できない worktree」の扱い（確かめてから消す）に従う
3. 条件を満たさなければ、`ExitWorktree` の `keep` で抜け、残した理由を報告する
4. 条件を満たせば、worktree の入り方で分ける
   - このセッションの EnterWorktree で作った worktree: 先に HEAD を切り離す（`--delete-branch` で切り替わったデフォルトブランチを、worktree の削除に巻き込まないため）

     ```bash
     git switch --detach
     ```

     そのうえで `ExitWorktree` の `remove` で消す。「N コミットを破棄」と警告されたら、警告に出たコミットがすべて origin/`<default>` に入っていること（`git merge-base --is-ancestor <commit> origin/<default>`）を確かめてから `discard_changes: true` を渡す。入っていないコミットがあれば `keep` で抜けて報告する
   - `path` で入った worktree: HEAD を切り離さずに `ExitWorktree` の `keep` で抜ける。手順 5 で、ほかの worktree と同じ条件で判定して消す
   - `ExitWorktree` が no-op になる（前のセッションで作った worktree で再開したなど）: 自分の cwd は消さない。手順 4 以降に進まず、primary で別のセッションを開いて片付けるよう報告して終える

### 4. 孤児の worktree を掃除する

review-pr の Step 8 と同じスクリプトを、primary から実行する。

```bash
bash ~/.claude/skills/review-pr/scripts/sweep-orphan-worktrees.sh
```

このスクリプトは、`.claude/worktrees/` の下にあり、lock の pid が死んでいる worktree を、手順 5 の条件を見ずに消す。未コミットの変更がある worktree は残す。`worktree-<name>` のブランチは、独自のコミットが無いときだけ消す。detached の worktree で、どのブランチにも無いコミットは、このスクリプトでは守られない（既存の review-pr Step 8 と同じ挙動）。残したものは `[sweep]` で始まる行で出力されるので、手順 10 でそのまま報告する。

### 5. 残りの worktree を判定して消す

`git worktree list --porcelain` で並べ、primary（先頭の 1 つ）以外を 1 つずつ判定する。`branch refs/heads/<x>` の行からブランチ名 `<x>` を取る。

| 条件 | 確かめ方 | 理由 |
|---|---|---|
| lock されていない | porcelain に `locked` の行が無い | lock は生きているセッションが使っている印 |
| マージ済みの PR に対応する | 手順 2 の定義 | lock されていない他セッションの worktree もある。origin/`<default>` から切ったばかりの worktree は、下の 2 条件を満たしてしまう |
| 未コミットの変更が無い | `git -C <wt> status --porcelain` が空 | 未コミットの変更は git から復旧できない |
| HEAD がデフォルトブランチに入っている | `git -C <wt> merge-base --is-ancestor HEAD origin/<default>` が真 | マージ後に積んだコミットを失わない |

- ignored のファイル（`.env`・ローカルの DB・`docs/temp/` など）は、`git worktree remove` で一緒に消える。`git -C <wt> status --porcelain --ignored` で `!!` の行があれば、一覧で示し、消してよいかを確かめてから消す
- ブランチがデフォルトブランチの worktree や、detached の worktree（`--delete-branch` のマージの後など）は、PR を特定できない。lock されていない・未コミットの変更が無い・HEAD がデフォルトブランチに入っている、の 3 つを満たすものだけを一覧で示し、消してよいかを確かめてから消す
- ListAgents に busy な peer セッションがいるとき、または ListAgents が使えないときは、消す候補の一覧を示し、まとめて 1 回確かめてから消す（lock されていない worktree を、他のセッションが使っているかは機械的に判定できない）

消すときは primary から実行する。

```bash
git -C <primary> worktree remove <wt>
git -C <primary> worktree prune
```

条件を満たさないものは残し、どの条件で残したかを報告する。

### 6. ローカルブランチを消す

次のブランチが対象。デフォルトブランチと、いずれかの worktree で checkout されているブランチは除く。

- 対象の PR のブランチ
- 手順 3・5 で消した worktree のブランチ（手順 3 で控えたもの、手順 5 の porcelain で取ったもの）
- worktree の無いローカルブランチ

どれも、マージ済みの PR に対応するもの（手順 2 の定義）だけを消す。`git branch --merged` だけでは選ばない（コミットの無い他セッションのブランチも出るため）。手順 4 の掃除が扱ったブランチは、スクリプト自身が判断するので対象にしない。

`git branch -d` は、古いローカルのデフォルトブランチや、prune 済みの upstream と比べて失敗しやすい。そのため、origin/`<default>` に入っていることを確かめてから `-D` で消す。

```bash
if git -C <primary> merge-base --is-ancestor <branch> origin/<default>; then
  git -C <primary> branch -D <branch>
else
  echo "残した: <branch>（origin/<default> に入っていない）"
fi
```

### 7. 対象の PR のリモートブランチを確かめる

対象の PR があるときだけ行う。

```bash
git ls-remote origin refs/heads/<対象の PR のブランチ>
```

何も出なければよい（マージ時の自動削除で消えている）。残っていれば報告し、消すかどうかを聞く。

### 8. primary のデフォルトブランチを最新にする

次のすべてを満たすときだけ、primary のデフォルトブランチを最新にする。

- primary が `<default>` を checkout している
- `git -C <primary> status --porcelain` が空
- ListAgents で、同じリポジトリを扱う peer セッションが無い（peer がどの worktree にいるかは ListAgents では分からないので、別の worktree にいる peer でも止める）

```bash
git -C <primary> pull --ff-only
```

満たさないとき（ListAgents が使えないときを含む）は pull せず、理由を添えて「pull してよいか」を聞く。

### 9. プロジェクト固有の後続作業

プロジェクトの CLAUDE.md にマージ後の作業（handoff の更新、ビルド、マイグレーションなど）が書かれていれば、それに従う。

### 10. 報告する

- 消した worktree・ブランチ
- 残したものと、その理由（どの条件か）。手順 4 の `[sweep]` 行はそのまま載せ、残すか消すかをユーザーに聞く
- デフォルトブランチの状態（pull したか、しなかった理由）

最後に「続けて next-issue で次の Issue 候補を出しますか」と聞く。

## 注意事項

- 破壊的な操作は hook（destructive-guard）に止められることがある。この手順にはリモートブランチの削除が無い。`git worktree remove` と `git branch -d` / `-D` は hook の対象外なので、通常は止まらない
- 「マージして整理して」と頼まれたときは、この skill を起動する前に、ユーザーの指示としてメインの会話でマージを済ませる（`gh pr merge <N> --merge`。worktree の中では `--delete-branch` を付けない）
