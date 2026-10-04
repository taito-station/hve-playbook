---
description: Knowledge 成熟度モデル — frontmatter 標準・status 管理・SoT 優先順位・Stale 検出の仕組み。
---

# Knowledge 成熟度モデル

knowledge/ 配下の文書の信頼度と鮮度を管理する仕組み。

## frontmatter 標準

knowledge/ 配下の各ファイルは以下の frontmatter を持つ:

```yaml
---
title: 文書タイトル
status: Confirmed | Tentative | Conflict
kind: knowledge | specification
sources:
  - docs-original/NNN-xxx.md
  - qa/QA-yyy.md
distilled_from_sha:
  docs-original/NNN-xxx.md: a1b2c3d4...  # フル SHA（40 文字）
  qa/QA-yyy.md: e5f6a7b8...              # git log -1 --format=%H で取得
updated: "YYYY-MM-DD"
doc_class: プロジェクト定義の分類コード
tags: [分類コード]
---
```

### 各フィールドの定義

| フィールド | 必須 | 説明 |
|---|---|---|
| `title` | Yes | 文書タイトル |
| `status` | Yes | 信頼度（下記参照） |
| `kind` | Yes | `knowledge`（ドメイン知識）または `specification`（仕様） |
| `sources` | Yes | 蒸留元ファイルのパス一覧 |
| `distilled_from_sha` | Yes | source ごとの蒸留時点の git commit sha |
| `updated` | Yes | 本文または status を実質的に更新した日（ISO 8601、ダブルクォート必須）。下記「`updated` の規則」参照 |
| `doc_class` | No | 文書の役割分類（プロジェクトが定義する） |
| `tags` | No | 検索用タグ |

### `updated` の規則

`updated` は、本文または status を実質的に更新した日を示す。本文または status が実質的に変わったときだけ当日日付に進め、`distilled_from_sha` だけを追従させるときは触らない。下流の本文に効かない上流の変更まで日付を進めると、「いつ内容が変わったか」という信号が濁る。

| 変更 | `distilled_from_sha` | `updated` |
|---|---|---|
| source の誤字修正など、下流の本文に効かない上流の変更 | 進める | 据え置く |
| 本文の事実・判断が変わる差分マージ | 進める | 進める |
| Tentative → Confirmed への昇格だけ | 据え置く | 進める |
| Conflict の宣言（同じ回に差分マージしていたら、本文ごと取り消す。下記「status の 3 段階」参照） | 蒸留前の値のまま | 進める |
| knowledge 本文の、意味の変わらない表記揺れ・誤字の修正 | 据え置く | 据え置く |

値は必ずダブルクォートで囲む（`updated: "2026-10-04"`）。クォートしないと YAML が date 型に解釈し、文字列を前提にした JSON 化や比較で型が揺れる。HVE の mdq も `default=str` の導入前（HypervelocityEngineering 8ab5a42 より前）は、frontmatter の JSON 化が `Object of type date is not JSON serializable` で失敗し、索引化できなかった。

## status の 3 段階

| status | 定義 | 運用 |
|---|---|---|
| `Confirmed` | 確定知。運用の前提にしてよい | QA で Confirmed された回答、またはレビュー済みの蒸留結果 |
| `Tentative` | 暫定。前提に使えるが変更の可能性あり | 初回蒸留の結果、未レビューの推論補完 |
| `Conflict` | 矛盾あり。放置せず解消が必要 | source 間の矛盾、または蒸留時に検出した不整合 |

- `Conflict` は発見次第ユーザーに報告し、解消するまで該当部分を前提にしない
- `Conflict` の文書は、本文と `distilled_from_sha` を蒸留前の状態に保つ。同じ回の蒸留で差分マージしていたら、本文と sha をどちらも蒸留前に戻し、status と `updated`（宣言した日）だけを変える。こうすると解消時に、蒸留前の sha から最新の source までの差分をそのまま取り込める
- `Conflict` の文書は解消するまで蒸留しない。解消して差分マージしたときに sha を進める
- `Tentative` → `Confirmed` への昇格は、QA 回答の確認またはユーザーのレビュー承認による

## SoT（Single Source of Truth）優先順位

情報が矛盾する場合、上位が勝つ:

```
docs-original（一次資料）> qa（Confirmed 回答）> knowledge（蒸留済み確定知）
```

- `docs-original/`: ユーザー提供の原本。最も信頼度が高い
- `qa/`: 質問票に対するユーザーの回答。Confirmed ステータスのもの
- `knowledge/`: 上記を蒸留・統合した文書。派生物であり、source に従う

## Stale 検出の仕組み

knowledge 文書が stale（source より古い）かどうかを frontmatter の `distilled_from_sha` で判定する。

### 判定ロジック

1. knowledge の frontmatter から `distilled_from_sha` を読む
2. 各 source ファイルの現在の sha を取得: `git log -1 --format=%H -- <file>`
3. sha が一致しなければ stale

### 実装例（シェルワンライナー）

```bash
# 特定ファイルの現在の sha を取得
git log -1 --format=%H -- docs-original/NNN-xxx.md

# knowledge/ 配下の全ファイルについて stale 判定（概念）
# 各ファイルの frontmatter から distilled_from_sha を読み、
# 対応する source の現在の sha と比較する
```

stale 検出の自動化はプロジェクトがスクリプトとして実装する。AKM スキル（`skills/hve-akm/SKILL.md`）の Step 1 で実行する。

## doc_class（文書分類）

文書を役割で分類し、カバレッジ（どの役割の文書が揃っているか）を測る仕組み。

- 分類体系はプロジェクトが独自に定義する
- 各文書の frontmatter `doc_class` フィールドに分類コードを記載する
- AKM スキルの Step 4（カバレッジ分析）で、分類ごとの充足状況を検査する
