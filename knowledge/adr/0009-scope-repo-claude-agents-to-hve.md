# このリポジトリの .claude/agents も HVE の agent だけを指す

## ステータス

Accepted — 2026-09-29

## 背景と課題

ADR-0007 では、このリポジトリの `.claude/rules` を `rules/hve` だけに向けた。一方 `.claude/agents` は `agents/` 全体への symlink のまま残し、「`agents/global/` が project-level として探索されるかは確認していない」としていた。

2026-09-29 に Claude Code 2.1.282 で実測した（一時プロジェクトの `.claude/agents/sub/` に置いた agent が `claude -p` で利用可能になった）。その結果、Claude Code は `.claude/agents/` のサブディレクトリも読み込むと分かった。このリポジトリでは `agents/global/impl-sonnet.md` が、user レベル（sync の symlink）と project レベルの両方で定義されていた。

## 意思決定の要因

- global 配下を project-level で重ねて読み込ませない（ADR-0007 の rules と同じ扱い）
- HVE の agent（`agents/hve-*.md`）は、このリポジトリでの dogfooding のため project-level で使えるようにしておく

## 検討した選択肢

- `.claude/agents` を実ディレクトリにし、`agents/hve-*.md` をファイル単位で symlink する
- `agents/` 全体への symlink のまま残す（定義は同一なので実害は小さい）

## 決定内容

選択した選択肢: **`.claude/agents` を実ディレクトリにし、`agents/hve-*.md` をファイル単位で symlink する**。採用理由: global 配下を project-level で重ねて読み込ませないため（ADR-0007 の rules と同じ扱い）。`.claude/skills` は ADR-0007 のとおり `skills/` 全体を指したままにする（同名の skill は定義が同一で、サブディレクトリの skill が読まれるかは確かめていないため、今回は agents だけを直す）。`tests/test_sync_rules_agents.sh` が、`.claude/agents` の中身が `agents/hve-*.md` と一致することを検査する。

### 結果（Consequences）

- 良い結果: impl-sonnet の二重定義が無くなり、rules と agents の扱いが揃う。
- 悪い結果: sync-dotclaude.sh を実行していない環境では、このリポジトリで impl-sonnet が使えなくなる（`agents/global` は sync で配る前提。ADR-0007）。`agents/hve-*.md` を追加したときは、`.claude/agents/` にもリンクを張る必要がある（張り忘れはテストが検出する）。

## 選択肢の評価（Pros and Cons）

### ファイル単位で symlink する（採用）

#### メリット

- global 配下を重ねて読み込ませない

#### デメリット

- HVE の agent を追加するたびにリンクが要る

### agents/ 全体への symlink のまま（却下）

#### メリット

- 追加の手間が無い

#### デメリット

- impl-sonnet が user レベルと project レベルで二重に定義される

## 関連リンク

- Supersedes: [ADR-0007 user-level の rules・agents・個人 skill をリポジトリ管理に集約する](0007-consolidate-user-level-rules-and-agents.md)（`.claude/agents` の扱いのみ）
