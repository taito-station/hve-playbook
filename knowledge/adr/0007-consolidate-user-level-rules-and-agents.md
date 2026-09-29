# user-level の rules・agents・個人 skill をリポジトリ管理に集約する

## ステータス

Partially superseded by 0009-scope-repo-claude-agents-to-hve — 2026-09-29

- 有効な部分: rules・agents・個人 skill の集約と sync での配布、implement-flow の扱い、このリポジトリの `.claude/rules` を `rules/hve` に向けること、`.claude/skills` の扱い
- 失効した部分: このリポジトリの `.claude/agents` を `agents/` 全体に向けたままにすること、および `agents/global/` が project-level として探索されるかを確認していないとした記述（決定内容・結果）（ADR-0009 で実測し、`agents/hve-*.md` だけを指す形に変えた）

## 背景と課題

`~/.claude` のうち hooks・global skill・scripts・settings はこのリポジトリから `sync-dotclaude.sh` で配っている（ADR-0002 / ADR-0006）。一方で次の実ファイルはリポジトリ管理外に残っていた。

- `~/.claude/rules/` の git / php / rust / sql / workflow
- `~/.claude/agents/impl-sonnet.md`
- `~/.claude/skills/` の brew-update-all / learn / review-doc

そのため Opus 5.5 向けのプロンプト監査（ADR-0004）の対象から漏れていた。また `~/.claude/rules/workflow/implement-flow.md` は `rules/hve/implement-flow.md` と同じ規則のコピーで、内容が食い違っていた（Knowledge の置き場所の書き方、結果表・frontmatter・Issue 確認行の有無）。両方とも `~/.claude/rules/git/branching.md` を参照しており、この参照は導入先プロジェクトでは解決しない。

## 意思決定の要因

- このリポジトリは個人の dotclaude として運用しており、user-level の資産を 1 か所で管理・監査したい
- ADR-0002 の 2 段デプロイを保つ。導入先プロジェクトは setup.sh のコピーだけで自己完結し、作者の `~/.claude` に依存しない
- 重複して食い違う規則は揃える（ADR-0004）

## 検討した選択肢

### 配置と配布

- `rules/global/<category>/`・`agents/global/` に置き、sync で symlink する（`skills/global/` と同じ命名）
- 管理外のまま残す

### implement-flow の重複

- 両方を自己完結のまま残し、global 版の全行が hve 版に含まれることをテストで検査する
- hve 版を「global 版に従う + HVE 固有の差分」に縮める
- global 版を削除して hve 版だけにする

## 決定内容

- 配置と配布 — 選択した選択肢: **`rules/global/`・`agents/global/`・`skills/global/` に置き、sync で symlink する**。
  - rules はカテゴリ単位、agents はファイル単位で symlink する。dangling 検査の対象にも加える。
  - `rules/hve`・`agents/hve-*`・`skills/hve-*` は従来どおり setup.sh が導入先にコピーする project-level 資産で、sync では配らない。global 配下は setup.sh では配らない。
  - `~/.claude/skills/synced/` は Claude アプリが同期する公式 skill の置き場なので対象外。
- implement-flow の重複 — 選択した選択肢: **両方を自己完結のまま残し、ずれをテストで検査する**。
  - global 版（汎用）の空行以外の全行を hve 版にそのまま含め、HVE 固有の置き場所・結果表・frontmatter は hve 版にだけ足す。
  - 両方とも `~/.claude/rules` 配下のファイルを参照しない（ブランチ運用は「規約があればそれに従い、無ければ `<type>/<short-kebab-description>`」と書き、規約が無い導入先でも読めるようにする）。
  - `tests/test_implement_flow_drift.sh` が、global 版の行が hve 版に無ければ失敗する。検査は行の包含だけで、順序やセクションの所属は見ない。
- このリポジトリ自身の `.claude/rules` は `rules/hve` だけを指す（`rules/global` は sync で user-level に配るので、project-level として重ねて読み込ませない）。`.claude/agents`・`.claude/skills` は従来どおり `agents/`・`skills/` 全体を指す。skills は同名の user-level skill と重なっても定義が同一で、agents はサブディレクトリの `agents/global/` が project-level として探索されるかを確認していないため、今回は rules だけを直す。

### 結果（Consequences）

- 良い結果: user-level の rules・agents・個人 skill がリポジトリで版管理され、監査・レビューの対象になる。implement-flow の食い違いがテストで検出される。導入先プロジェクトの自己完結は保たれる。
- 悪い結果: sync 済みの環境（作者の環境）では、このリポジトリ自身と HVE を導入したプロジェクトで implement-flow が 2 回読み込まれる（global 版の内容はすべて hve 版に含まれ、hve 版は HVE 固有の記述を足したもの）。このリポジトリの `.claude/agents` は `agents/` 全体を指すので、`agents/global/` が探索される場合は impl-sonnet が user-level と project-level の両方で読み込まれる（未確認。定義は同一）。implement-flow を変えるときは、global 版を先に直してから hve 版に反映する手順が要る。既存環境では、`~/.claude` の実ディレクトリ・実ファイルを退避して symlink に置き換える一度きりの移行が要る（sync は実体が居座ると WARN でスキップする）。

## 選択肢の評価（Pros and Cons）

### 配置と配布: rules/global・agents/global に置き sync で配る（採用）

#### メリット

- skills/global と同じ仕組み・命名で、sync の実在検査・dangling 検査がそのまま効く。

#### デメリット

- 既存環境で一度きりの移行作業が要る。

### 配置と配布: 管理外のまま残す（却下）

#### メリット

- 変更が無い。

#### デメリット

- 監査・版管理の対象外のまま残り、implement-flow の食い違いも解消できない。

### implement-flow: 両方自己完結 + ずれ検査（採用）

#### メリット

- 導入先の自己完結（ADR-0002）を保ったまま、食い違いを機械的に防げる。

#### デメリット

- HVE 導入先では同じ規則が 2 回読み込まれる。

### implement-flow: hve 版を差分に縮める（却下）

#### メリット

- 重複が消える。

#### デメリット

- 導入先プロジェクトが作者の `~/.claude/rules` を前提にすることになり、ADR-0002 が採用理由とした自己完結とぶつかる。

### implement-flow: global 版を削除する（却下）

#### メリット

- 重複が消え、導入先の自己完結も保てる。

#### デメリット

- HVE を導入していないリポジトリで implement-flow が効かなくなる。

## 関連リンク

- Related: [ADR-0002 dotclaude-public を hve-playbook に統合する](0002-integrate-dotclaude-public-into-hve-playbook.md)
- Related: [ADR-0004 Opus 5.5 向けにプロンプト文面を監査し、規則の食い違いを揃える](0004-audit-prompts-for-opus-5-5.md)
