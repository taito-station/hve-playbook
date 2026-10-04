# プロジェクト固有の補足は .claude/rules/hve-local/ に書く

## ステータス

Accepted — 2026-10-04

## 背景と課題

`setup.sh` は導入先の `.claude/rules/hve/`・`skills/hve-*`・`agents/hve-*.md`・`workflows/hve-*.js` を削除してから置き直す。導入先が写しに書き足した注記は、再適用のたびに消える。

導入先の paddock は、rules/hve の 4 本と hve-akm の写しに固有の注記を足しており、再適用（paddock #753）のあとに手作業で戻していた（[taito-station/paddock#754](https://github.com/taito-station/paddock/issues/754)、[hve-playbook#29](https://github.com/taito-station/hve-playbook/issues/29)）。注記には、標準の改善として還元すべきもの（#26・#27・#28）と、検索コマンドのパスや検証コマンドの一覧のようにどうしてもプロジェクト固有のものがある。後者を置く場所が無いことが根本の問題。

問い: プロジェクト固有の補足を、再適用で消えない形でどこに、どう書くか。

## 意思決定の要因

- setup.sh の再適用で補足が消えない
- override を持たない既存の導入先の動作を変えない
- 補足と標準が食い違ったとき、どちらに従うかが判定できる
- 導入先が hve-playbook や作者の環境に依存しない（ADR-0002 の自己完結）

## 検討した選択肢

- `.claude/rules/hve-local/` に書き、置き場所・書式・優先順位を配布する rule 1 本に定める
- rules/hve の写しを直接編集し続ける
- setup.sh で写しと hve-playbook 版を差分マージする
- 導入先の CLAUDE.md に書く

## 決定内容

選択した選択肢: **`.claude/rules/hve-local/` に書き、置き場所・書式・優先順位を配布する rule 1 本に定める**。setup.sh が `.claude/rules/` 配下で削除するのは `hve/` だけなので、隣のディレクトリは再適用で消えない。Claude Code は `.claude/rules/` 配下を再帰的に読み込むので、特別な設定も要らない。

- 新しい rule `rules/hve/local-overrides.md` を配る。rules/hve への補足は同名ファイル、skill への補足は skill 名のファイルに書く
- 見出し `## <対象> の「<節名>」を上書き` の節だけが標準の該当節に代わる。それ以外は標準と併せて読む。上書きは節の中身の差し替えで、rule 同士の優先順位（捏造禁止を最優先とするなど）は変えない。local-overrides.md 自身は上書きの対象にしない
- hve-local のファイルに `paths:` frontmatter を付けない。hve-* skill を使う前に `hve-local/<skill 名>.md` を確かめる
- implement-flow の Step 7 に、プロジェクト固有の検証コマンドを `hve-local/implement-flow.md` に列挙する旨を足す
- setup.sh は hve-local を作らず、完了メッセージで案内するだけにする

Claude Code には、矛盾する指示のどちらに従うかを強制する仕組みが無い。そのため優先順位は rule の文面で示すしかない。2026-10-04 に一時 target で確かめた。hve-local に「output-quality の『フォーマット』を上書き: 出力言語は英語」を置いて `claude -p` に出力言語を尋ねると、「English」と答え、根拠として hve-local と local-overrides.md を挙げた。

### 結果（Consequences）

- 良い結果: 導入先は写しを編集せずに固有の補足を書け、再適用で消えない。override を持たない導入先との差は、新しい rule 1 本、implement-flow の Step 7 の 1 行、完了メッセージの 1 行だけ
- 悪い結果: 優先順位に強制力は無く、文面と 1 回の実測で確かめたにとどまる。hve-local の「上書き」節は標準の改定に自動では追従しないので、再適用のたびに見直しが要る

## 選択肢の評価（Pros and Cons）

### `.claude/rules/hve-local/` に書き、rule 1 本に定める（採用）

置き場所・書式・優先順位を `rules/hve/local-overrides.md` にまとめ、hve-local は導入先が管理する。

#### メリット

- setup.sh の変更は完了メッセージの 1 行だけで済む
- rules/hve の 9 本すべてに同じ 1 文を足すより差分が小さく、文言のずれも起きない

#### デメリット

- 標準と hve-local の両方がコンテキストに入る。優先順位は文面に頼る

### rules/hve の写しを直接編集し続ける（却下）

現状の運用のまま、写しに注記を足す。

#### メリット

- 変更が要らない

#### デメリット

- 再適用のたびに消え、手作業で戻す必要がある。今回の問題そのもの

### setup.sh で写しと hve-playbook 版を差分マージする（却下）

再適用時に、導入先の写しへの変更を残したまま hve-playbook 側の変更を取り込む。

#### メリット

- 導入先は今までどおり写しを編集できる

#### デメリット

- 衝突したときの扱いが要り、setup.sh が複雑になる。どれが標準でどれが固有の注記かも見分けにくい

### 導入先の CLAUDE.md に書く（却下）

固有の補足を CLAUDE.md（CLAUDE.hve.md を手作業でマージしたもの）に書く。

#### メリット

- 新しい仕組みが要らない

#### デメリット

- rules/hve の節単位の補足が書きにくく、CLAUDE.md が肥大化する

## 関連リンク

- Related: [0002-integrate-dotclaude-public-into-hve-playbook](0002-integrate-dotclaude-public-into-hve-playbook.md)
- Related: [0006-generate-settings-json-with-machine-overlay](0006-generate-settings-json-with-machine-overlay.md)
- Related: [local-overrides ルール](../../rules/hve/local-overrides.md)
