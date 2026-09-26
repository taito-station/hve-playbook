---
name: livewire-v3-syntax
description: |
  Livewire コンポーネントを書く・編集するときに必ず確認する。
  特に <livewire:...> タグ、@livewire ディレクティブ、wire:key / :key 属性のいずれかを書こうとしているとき。
  Livewire v2 と v3 で構文が大きく異なるため。
---

# Livewire v3 構文ルール

Livewire 3.x を使うプロジェクトで、v2 系の書き方が混入するのを防ぐ。
本 skill を有効にした状態では v2 構文は禁止。

## タグ記法

正解 (v3):
```blade
<livewire:component-name :key="$key" />
<livewire:component-name :prop="$value" />
<livewire:component-name :prop="$value" :key="$id" />
```

NG:
```blade
<livewire:component-name wire:key="key" />
```

`@livewire` ディレクティブは v3 でも有効（ループ内ではキーを第 3 引数 `key($id)` で渡す）。
プロジェクトの既存コードがタグ記法で統一されていればタグ記法に合わせる。

## キー属性

`<livewire:...>` コンポーネントタグを繰り返し描画するときのキーは `:key` を使う（コンポーネントタグに
`wire:key` を付けない）。ループ内の通常の HTML 要素には、v3 でも `wire:key` を付ける。

## 不確実な場合

claude.ai Context7 MCP で最新仕様を確認する:
1. `mcp__claude_ai_Context7__resolve-library-id` で Livewire の ID を取得
2. `mcp__claude_ai_Context7__query-docs` で最新仕様を確認
3. それに従って実装

Context7 が使えない環境では公式ドキュメント（https://livewire.laravel.com/docs/3.x/components）を参照する。
