# ADR（Architecture Decision Record）一覧

このディレクトリは設計上の意思決定を MADR 形式で記録する。配置先・フォーマット・ステータス値・採番・作成手順は documentation-standards スキルの「## ADR（Architecture Decision Record）」を参照。

ステータス列にはステータス値表の生値をそのまま記載する（置き換えられた ADR は `Superseded by 0005-...` のように後続 ADR の ID 込みで書く）。

| 連番 | タイトル | ステータス | 日付 |
|---|---|---|---|
| [0001](0001-adopt-madr-format-for-adrs.md) | ADR を MADR 形式で記録する | Accepted | 2026-06-18 |
| [0002](0002-integrate-dotclaude-public-into-hve-playbook.md) | dotclaude-public を hve-playbook に統合する | Accepted | 2026-09-20 |
| [0003](0003-add-session-cost-and-akm-to-create-pr.md) | create-pr にセッション費用表示と AKM チェックを追加する | Accepted | 2026-09-20 |
| [0004](0004-audit-prompts-for-opus-5-5.md) | Opus 5.5 向けにプロンプト文面を監査し、規則の食い違いを揃える | Accepted | 2026-09-26 |
| [0005](0005-default-permission-mode-auto.md) | 既定の権限モードを auto にし、既定モデルを opus エイリアスにする | Accepted | 2026-09-26 |
