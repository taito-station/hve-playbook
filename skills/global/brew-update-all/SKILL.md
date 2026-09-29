---
name: brew-update-all
description: Homebrew 本体の更新・インストール済みパッケージの更新・キャッシュ削除をまとめて行う。「brew を一括更新して」「Homebrew を最新にして」のような自然言語で起動。
---

# brew-update-all

Homebrewのパッケージ更新・Homebrew自体の更新・キャッシュ削除をまとめて行うスキル。

## Instructions

以下のコマンドを順番に実行してください：

1. `brew update` — Homebrew自体とパッケージ定義を最新に更新
2. `brew upgrade` — インストール済みのすべてのformulaeとcasksを更新
3. `brew cleanup --prune=all` — キャッシュをすべて削除

各コマンドの実行結果をユーザーに報告してください。
