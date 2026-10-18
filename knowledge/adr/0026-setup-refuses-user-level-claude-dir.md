# setup.sh は導入先の .claude が ~/.claude と同じ実体なら [ERROR] で止める

## ステータス

Accepted — 2026-10-18

## 背景と課題

`setup.sh` は `TARGET_CLAUDE="$TARGET/.claude"` に HVE 資産を配る。導入先に `$HOME` を指定すると（`setup.sh ~`）、`~/.claude/rules/hve` などを削除してから置き直し、`~/.claude/CLAUDE.md` が無ければ作る。`~/docs` も作る。導入先の `.claude` が `~/.claude` を指す symlink の場合も同じことが起きる。誤操作に近いが、保護が無かった（Issue #52。#40 のレビューで検出）。

## 意思決定の要因

- `~/.claude` は user-level で、sync-dotclaude.sh の領分（ADR 0002・0007 の 2 段デプロイ）。setup.sh が書き換えてはいけない
- 適用プロンプト経由で Claude が非対話で実行する場合にも効くこと
- 既存の「hve-playbook 自身をターゲットにできない」の保護と同じくらい単純であること（no-overengineering）

## 検討した選択肢

- 判定: `.claude` の実体どうしを比べる／`$TARGET` と `$HOME` の実体を比べるだけ
- 止め方: `[ERROR]` と exit 1／y/N で確認する

## 決定内容

選択した選択肢: **`$TARGET/.claude` と `$HOME/.claude` が同じ実体なら `[ERROR]` を出して exit 1 にする。続ける抜け道は設けない**。質問票の回答（`qa/project-level-skill-refs-and-setup-home-questionnaire.md` の Q04・Q05）と、Plan・PR の敵対的レビューによる。

- 比較は bash の `-ef`（デバイスと inode。どちらかが存在しなければ偽）で行う。綴りの違い・symlink 経由の指定に加え、大文字小文字を区別しないファイルシステム（macOS の既定）での大文字小文字の違いも同じ実体とみなす（`pwd -P` の文字列比較は入力の大文字小文字を保つので、すり抜けた。PR のレビューで検出）
- 導入先が `$HOME` と同じ実体なら、`~/.claude` がまだ無くても止め、`~/.claude` を作らせない
- 導入先が `~/.claude` そのもの（`setup.sh ~/.claude`）のときも止める。`~/.claude` の中に `.claude/` と `docs/` を作らせない（PR のレビューで検出し、オーナーが判断した。`~/.claude` の配下全体には広げない）
- 導入先の `.claude` が `$HOME` そのものを指すとき（`ln -s ~ <target>/.claude`）も止める。`$HOME` 直下に `rules/`・`CLAUDE.md` などを作らせない（`$HOME/CLAUDE.md` は配下の全プロジェクトに効く。PR のレビューで検出し、オーナーが判断した）
- 判定は `mkdir -p "$TARGET_CLAUDE"` より前に置く。止まるときは何も書かないので、戻す操作は要らない
- `$HOME` が未設定・空のときは判定を飛ばす（`set -u` の下で `${HOME:-}` を使う）。`$HOME` が存在しないディレクトリのときは、`-ef` が偽になるので止めない
- 挙動は `tests/test_sync_rules_agents.sh` の節 10 で固定する（`$HOME`・`$HOME/`・`$HOME/.`・大文字小文字の違い・`~/.claude` を指す symlink・`$HOME` を指す symlink の `.claude`・`~/.claude` 未作成・導入先が `~/.claude` で止まり `~/.claude`（`$HOME`）が変わらないこと、`[ERROR]` の文言（適用プロンプトがこの文言で分岐する）、通常の導入先と、`HOME` が未設定・存在しないディレクトリのときは止めないこと）。適用プロンプトの手順 2 でも同じ判定で先に止め、`git init`・退避・ブランチを残さない

### 結果（Consequences）

- 良い結果: `setup.sh ~`・`setup.sh ~/.claude` の誤操作と、`.claude` を `~/.claude`・`$HOME` に向けた symlink の導入先で、`~/.claude` と `$HOME` 直下が書き換わらない
- 悪い結果・既知の限界:
  - 導入先の `.claude` 配下のサブディレクトリ（`.claude/rules` など）が `~/.claude` 配下を指す symlink の場合は防がない。適用プロンプト（`docs/prompts/apply-hve-playbook.md`）の手順 2 の symlink の確認が受け持つ
  - 導入先の `.claude` が、まだ無い `~/.claude` を指す dangling symlink の場合は、比較では止まらない。続く `mkdir -p` が失敗して止まり、何も書かない（`[ERROR]` の案内は出ない）
  - `~/.claude` 以外の場所を user-level として使う環境（sync-dotclaude.sh の `CLAUDE_HOME` で同期先を移した場合など）は、判定の対象外
  - `HOME` が未設定・空のときは判定を飛ばす。bash の `~` はその場合 passwd のホームに展開されるので、実際の `~/.claude` は守られない（HOME を外して setup.sh を実行する状況は現実的でないので、オーナーの判断で現状のままにした）

## 選択肢の評価（Pros and Cons）

### `.claude` の実体どうしを比べる（採用）

#### メリット

- `setup.sh ~`・綴りや大文字小文字の違い・`.claude` の symlink を、`-ef` の比較で防げる

#### デメリット

- `~/.claude` が無い場合・導入先が `~/.claude` の場合・`.claude` が `$HOME` を指す場合の比較が要る（4 つの `-ef` の OR）

### `$TARGET` と `$HOME` の実体を比べるだけ

#### メリット

- 比較が最も単純

#### デメリット

- 導入先の `.claude` が `~/.claude` を指す symlink の場合を防げない

### y/N で確認する

#### メリット

- 意図して `~/.claude` に入れたい利用者が続けられる

#### デメリット

- 適用プロンプト経由の非対話の実行で扱えない。`~/.claude` に project-level の HVE を入れる正当な用途も無い

## 関連リンク

- Related: [0002-integrate-dotclaude-public-into-hve-playbook](0002-integrate-dotclaude-public-into-hve-playbook.md)
- Related: [0007-consolidate-user-level-rules-and-agents](0007-consolidate-user-level-rules-and-agents.md)
- Related: [hve-playbook#52](https://github.com/taito-station/hve-playbook/issues/52)
