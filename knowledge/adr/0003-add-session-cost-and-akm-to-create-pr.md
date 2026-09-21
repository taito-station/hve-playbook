# create-pr にセッション費用表示と AKM チェックを追加する

## ステータス

Accepted — 2026-09-20

## 背景と課題

PR 作成フロー（create-pr skill）に 2 つの機能が不足していた:

1. **セッション費用の可視化**: PR 作成にかかったトークン使用量と費用が不明で、コスト意識を持てない
2. **Knowledge 同期チェック（AKM）**: implement-flow Step 7 に相当する「コード変更が確定知の前提を変えていないか」の確認が create-pr フローに組み込まれていない

## 意思決定の要因

- 費用の可視化は事後でなく PR 作成完了時に即座に見たい
- AKM チェックは自動化可能な範囲に留め、STOP ではなく注意喚起にとどめる（過剰なブロックを避ける）
- セッション JSONL は既にローカルに存在し、追加のインフラ不要で集計可能

## 検討した選択肢

### 費用表示

- スクリプト（session-cost.py）を create-pr に組み込む
- Claude Code の API / CLI 機能で取得する（該当機能なし）
- 手動で JSONL を確認する

### AKM チェック

- diff ベースの自動チェック（コード変更あり + docs/ 変更なし → 注意喚起）
- 人間が毎回手動で確認する
- STOP ゲートにする（docs/ 変更がなければ PR 作成をブロック）

## 決定内容

- **費用表示**: `scripts/session-cost.py` を新規作成し、create-pr の Step 1 でスナップショット、Step 8 で差分表示する。スクリプトは `sync-dotclaude.sh` で `~/.claude/scripts/` にも配置する
- **AKM チェック**: Step 5.1 として diff ベースの自動チェックを追加する。注意喚起のみで STOP はしない

### 結果（Consequences）

- 良い結果: PR 完了時に費用が自動表示され、コスト意識が向上する。Knowledge 同期の見落としが減る
- 悪い結果: session-cost.py の料金テーブルは手動更新が必要（API 料金変更時）。AKM チェックは false positive がありうる（コード変更が docs/ に影響しないケース）

## 関連リンク

- Related: [ADR-0002 dotclaude-public 統合](0002-integrate-dotclaude-public-into-hve-playbook.md)
- Related: [implement-flow 規約](../../rules/hve/implement-flow.md)（Step 7: Knowledge 同期）
