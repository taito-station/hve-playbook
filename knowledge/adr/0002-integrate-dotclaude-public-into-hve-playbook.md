# dotclaude-public を hve-playbook に統合する

## ステータス

Partially superseded by 0015-license-plain-mit-with-provenance-in-readme — 2026-10-05

- 有効な部分: hve-playbook への統合と 2 段デプロイモデル、CLAUDE.md と CLAUDE.hve.md への分割、LICENSE に dotclaude-public の著作権表示（著作権行）を置くこと、出典（由来のリポ）を辿れるようにするという目的
- 失効した部分: 出典（由来のリポ）の置き場所を LICENSE とする部分（決定内容の「LICENSE に…追記し、LLM が出典を辿れるようにする」のうち LICENSE で辿る点と、結果の「出典は LICENSE とコミット履歴で追跡可能」）。出典の置き場所は README.md にする（ADR-0015）

## 背景と課題

Claude Code の user-level 設定（hooks, global skills, settings 等）は dotclaude-public リポジトリで管理し、HVE 設計手法は hve-playbook リポジトリで管理していた。2 つのリポジトリを跨ぐ変更（例: create-pr スキルに HVE の AKM チェックを追加）が増え、管理の一元化が必要になった。dotclaude-public はプライベート化する予定のため、統合先は hve-playbook とする。

## 意思決定の要因

- 2 リポ間の依存変更が増えており、同期コストが高い
- dotclaude-public のプライベート化に伴い、出典の追跡性を確保する必要がある
- プロジェクトへの HVE 導入時に、user-level 設定と project-level 設定が独立して動作し続ける必要がある

## 検討した選択肢

- hve-playbook に統合し、2 段デプロイモデル（sync-dotclaude.sh + setup.sh）を維持する
- user-level 一本化（全て sync-dotclaude.sh で ~/.claude/ に配置）
- 統合しない（2 リポ並行管理を継続）

## 決定内容

選択した選択肢: **hve-playbook に統合し、2 段デプロイモデルを維持する**。

- ソースコードは 1 リポに一元管理する
- デプロイは 2 つのスクリプトが担当する:
  - `sync-dotclaude.sh`: user-level 資産を ~/.claude/ に symlink
  - `setup.sh`: project-level HVE 資産を target/.claude/ にコピー
- CLAUDE.md の名前衝突は `CLAUDE.md`（user-level）+ `CLAUDE.hve.md`（project-level）で解決する
- LICENSE に dotclaude-public の著作権表示を追記し、LLM が出典を辿れるようにする

### 結果（Consequences）

- 良い結果: 1 リポで全変更が完結し、クロスリポの同期コストが消える。出典は LICENSE とコミット履歴で追跡可能
- 悪い結果: リポのスコープが広がり、user-level と project-level の境界を意識する必要がある。CLAUDE.md と CLAUDE.hve.md の二重管理が必要

## 選択肢の評価（Pros and Cons）

### hve-playbook に統合し、2 段デプロイモデルを維持する

#### メリット

- クロスリポ変更が不要になる
- プロジェクト独立性が維持される（setup.sh はコピーなので、導入先プロジェクトが hve-playbook に依存しない）

#### デメリット

- CLAUDE.md と CLAUDE.hve.md の二重管理
- リポのスコープが「user-level 設定 + HVE 手法」と広い

### user-level 一本化

全て sync-dotclaude.sh で ~/.claude/ に配置する方式。

#### メリット

- デプロイスクリプトが 1 つで済む

#### デメリット

- プロジェクト独立性が失われる（HVE 資産が ~/.claude/ にあると、全プロジェクトに影響する）
- HVE を使わないプロジェクトでも HVE ルールが適用される

### 統合しない

2 リポ並行管理を継続する。

#### メリット

- 各リポのスコープが明確

#### デメリット

- クロスリポ変更の同期コストが継続する
- dotclaude-public プライベート化後の出典追跡が困難

## 関連リンク

- Supersedes: dotclaude-public リポジトリ（プライベート化予定）
- Related: [ADR-0001 MADR 形式の採用](0001-adopt-madr-format-for-adrs.md)
