---
name: tailwind-enforcement
description: |
  HTML / テンプレート / JSX / Vue SFC / Blade / Livewire コンポーネント等、
  UI 要素を編集するとき。style 属性を書こうとしているとき。スタイル指定のたびに参照。
---

# Tailwind CSS 必須ルール

Tailwind CSS を導入しているプロジェクトでは、HTML 要素のスタイルは Tailwind の class 属性で指定し、
style 属性によるインラインスタイルは使わない（例外は後述）。Tailwind 未導入のプロジェクトには適用しない。

## 例

NG:
```html
<div style="background-color: #3b82f6; padding: 16px; color: white;">
```

OK:
```html
<div class="bg-blue-500 p-4 text-white">
```

## 例外（style 属性が許可される場合）

### 動的な色表示

DB から取得した色値を直接表示する場合のみ:

```html
<div style="background-color: {{ $category['color_code'] }}"></div>
```

### Tailwind では表現不可能な動的スタイル

計算値や外部 API からの値をそのまま CSS に流す必要がある場合のみ。

## 適用対象

- すべての HTML / テンプレートファイル（Blade / JSX / Vue SFC / ERB 等）
- 既存コードの修正時は、新たに書く・書き換える箇所に適用する（触らない既存の style 属性まで
  一括置換しない: 最小差分原則）

## 理由

- デザインシステムの一貫性
- メンテナンス性
- レスポンシブ対応の統一
- パフォーマンス最適化
