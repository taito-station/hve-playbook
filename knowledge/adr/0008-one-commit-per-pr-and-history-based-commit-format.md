# 未 push のブランチは PR 作成時に 1 コミットにまとめ、コミット形式は既存履歴に合わせる

## ステータス

Accepted — 2026-09-29

## 背景と課題

`rules/global/git/branching.md` と、同じリポジトリの skill の間で規則が食い違っていた（ADR-0007 で取り込んだファイルの監査で判明）。

- コミットの作り方: branching.md は「1 コミット = 1 機能単位。PR 前に `git rebase -i` で機能単位に再構成する」。create-pr skill の Step 6 は「未 push のブランチは `git reset --soft` で 1 コミットにまとめる。`rebase -i` は使わない」。この環境では対話的な `rebase -i` を実行できない。
- コミット形式: branching.md は Conventional Commits・日本語固定。commit-workflow skill は「既存履歴の形式に合わせ、無い・混在時は Conventional Commits」としつつ、「user-level の規約があればそれに従う」と譲っていたため、既存の形式を持つ他のリポジトリでも Conventional Commits が強制される読み方になっていた。

## 意思決定の要因

- 規則は実際に実行できる手順にする
- 1 PR = 1 トピック（branching.md の既存規則）とレビュー・bisect のしやすさを保つ
- 他チームのリポジトリの既存の履歴形式を壊さない

## 検討した選択肢

### コミットの作り方

- branching.md を create-pr に合わせる（粒度の単位を PR にし、未 push のブランチは 1 コミットにまとめる。分けたい単位は PR を分ける）
- create-pr を branching.md に合わせる（機能単位のコミットを残し、レビュー対応のコミットだけを `--fixup` + `--autosquash` で畳む）

### コミット形式

- branching.md に「既存履歴に別の形式・言語があれば、コミットメッセージと PR タイトルをそれに合わせる」を足し、branching.md をコミット形式の正本にする
- Conventional Commits 固定のまま、commit-workflow の履歴合わせを削る

## 決定内容

- コミットの作り方 — 選択した選択肢: **branching.md を create-pr に合わせる**。採用理由: 1 PR = 1 トピックなので、粒度の単位を PR にすればレビューと bisect のしやすさを保てる。レビュー対応のコミットを該当の機能コミットに畳む方法（`--fixup` + `GIT_SEQUENCE_EDITOR=: git rebase -i --autosquash`）は非対話でも実行できるが、fixup の宛先を正しく選ぶ判定と競合時の失敗モードが増え、`reset --soft` による 1 コミット化より壊れやすい。push 済みのブランチは公開済みのコミットを保つため畳まない（複数コミットのまま PR になる。create-pr が base に rebase したあとのリース固定の `--force-with-lease` だけは、branching.md の禁止事項の例外として認める）。マージ戦略（Merge commit）は変えない。
- コミット形式 — 選択した選択肢: **branching.md に例外を足す**。採用理由: 自分のリポジトリでは従来どおり Conventional Commits になり、既存の形式を持つリポジトリの履歴も揃ったまま保てる。言語の既定は ADR-0004 の「件名はプロジェクトの言語」に揃える（branching.md の日本語固定を改める）。

### 結果（Consequences）

- 良い結果: 規則と skill の手順が一致し、実行できない手順が無くなる。他リポジトリの履歴形式を崩さない。
- 悪い結果: 未 push のブランチから作る PR の中で、機能単位のコミットを分けて残すことはできなくなる（PR を分けて対応する）。push 済みのブランチでは、それまでのコミットがそのまま残る。

## 選択肢の評価（Pros and Cons）

### コミットの作り方: branching.md を create-pr に合わせる（採用）

#### メリット

- 追加の仕組みなしで、今の create-pr の挙動がそのまま規則になる

#### デメリット

- PR の中の段階的なコミット履歴は残らない

### コミットの作り方: create-pr を branching.md に合わせる（却下）

#### メリット

- PR の中で機能単位のコミットを残せる

#### デメリット

- fixup の宛先を正しく選ぶ判定が要り、競合時の失敗モードが増える（非対話の `--autosquash` で実行自体はできる）

### コミット形式: branching.md に例外を足す（採用）

#### メリット

- 自分のリポジトリの規約を変えずに、他リポジトリの履歴と揃えられる

#### デメリット

- 形式の判断に既存履歴の確認が要る

### コミット形式: Conventional Commits 固定（却下）

#### メリット

- 形式が常に一定になる

#### デメリット

- 既存の形式を持つリポジトリの履歴が混在する

## 関連リンク

- Related: [ADR-0004 Opus 5.5 向けにプロンプト文面を監査し、規則の食い違いを揃える](0004-audit-prompts-for-opus-5-5.md)
- Related: [ADR-0007 user-level の rules・agents・個人 skill をリポジトリ管理に集約する](0007-consolidate-user-level-rules-and-agents.md)
