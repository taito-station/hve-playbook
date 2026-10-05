# LICENSE は著作権行と MIT 本文だけにし、由来の説明は README に置く

## ステータス

Accepted — 2026-10-05

## 背景と課題

リポジトリを公開した（[hve-playbook#33](https://github.com/taito-station/hve-playbook/issues/33)）が、GitHub のライセンス判定が `other`（`spdx_id: NOASSERTION`）になり、MIT と表示されなかった（[hve-playbook#39](https://github.com/taito-station/hve-playbook/issues/39)）。

LICENSE は、自分の著作権行と MIT の許諾文の間に、上流 2 リポの由来の段落（`Based on …` / `Includes …`、URL、`Original work Copyright …`）を挟んでいた。GitHub はライセンスの判定に licensee を使う（GitHub 側の版は未確認。検証には v10.1.0 を使った）。licensee は照合の前にタイトル行や先頭の著作権行などを除くが、`Based on …` のような由来の段落は除かない（`lib/licensee/content_helper/normalization_methods.rb` の `strip_copyright`、`lib/licensee/matchers/copyright.rb`）。そのため MIT との類似度は 65.96% で、しきい値 98% に届かなかった（licensee 10.1.0 の `licensee detect` で確認）。

ADR-0002 は「LICENSE に dotclaude-public の著作権表示を追記し、LLM が出典を辿れるようにする」と決め、結果の節に「出典は LICENSE とコミット履歴で追跡可能」と書いている。LICENSE の書き方を変えると LICENSE から由来のリポを辿れなくなるので、出典の置き場所を決め直す必要がある。

## 意思決定の要因

- GitHub が MIT と判定し、再利用する第三者がライセンスを判断できること
- 上流 2 者（HypervelocityEngineering: Daiyu Hatakeyama、dotclaude-public: youhei-ushio。どちらも MIT）の著作権表示を残すこと（MIT の「著作権表示と許諾表示を含める」条件）
- 由来（どのリポから何を取り込んだか）を辿れること（ADR-0002 の意図）
- GitHub Docs の案内:「ライセンスを検出させるには LICENSE を単純にし、複雑な点は README など別の場所に書く」（[Licensing a repository](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/licensing-a-repository)）

## 検討した選択肢

- LICENSE を著作権行と MIT 本文だけにし、由来の説明は README に置く
- LICENSE を同じく単純にし、由来の説明は NOTICE ファイルを新設して置く
- 現状維持（LICENSE に由来の段落を残す）

## 決定内容

選択した選択肢: **LICENSE を著作権行と MIT 本文だけにし、由来の説明は README に置く**。

LICENSE は `MIT License`、3 者の著作権行（`Copyright (c) 2026 taito-station` / `Copyright (c) 2026 Daiyu Hatakeyama` / `Copyright (c) 2026 youhei-ushio`）、MIT 本文だけにする。由来の説明（リポ名・URL・ライセンス）は README.md の冒頭（`Based on …` / `Includes …`）に置く。リポ名・URL・ライセンスは README にすでにあり、著作者の実名は LICENSE の著作権行に残るので、移す作業は LICENSE から段落を消すだけで済む。

本 ADR は ADR-0002 を部分的に置き換える。ADR-0002 の決定のうち「LICENSE に dotclaude-public の著作権表示を追記する」は、著作権行として残るので有効のまま。「LLM が出典を辿れるようにする」と結果の「出典は LICENSE とコミット履歴で追跡可能」は失効し、「著作権表示は LICENSE、由来（リポ名・URL）は README.md、経緯はコミット履歴」に置き換える。ADR-0002 のステータス節と一覧に、有効な部分と失効した部分を書いた。

### 結果（Consequences）

- 良い結果: licensee 10.1.0 で `License: MIT`（`Licensee::Matchers::Exact`、Confidence 100%）と判定され、3 者すべてが Attribution に出る
- 良い結果: 上流 2 者の著作権表示は LICENSE に残り、MIT の再配布条件を満たす
- 悪い結果: LICENSE だけを見ても、どのリポから何を取り込んだかはわからない（README を見る必要がある）
- 悪い結果: GitHub 側の判定が更新されるタイミングは TBD（推論: 既定ブランチへの反映後に GitHub 側で再判定される）。マージ後に確認する

## 選択肢の評価（Pros and Cons）

### LICENSE を著作権行と MIT 本文だけにし、由来の説明は README に置く

LICENSE から由来の段落を消し、由来は既存の README.md 冒頭の記述に任せる。

#### メリット

- README にすでに由来の記述があり、新しいファイルが要らない
- GitHub Docs の案内どおり

#### デメリット

- LICENSE 単体では由来がわからない

### LICENSE を同じく単純にし、由来の説明は NOTICE ファイルを新設して置く

LICENSE は同じく単純にし、由来の説明を新しい NOTICE ファイルにまとめる。

#### メリット

- 由来の説明を README の構成から切り離せる

#### デメリット

- README と内容が重複する。今の由来の説明は 2 行で、別ファイルにするほどの量がない

### 現状維持（LICENSE に由来の段落を残す）

LICENSE を変えない。

#### メリット

- LICENSE だけで由来がわかる

#### デメリット

- GitHub が MIT と判定しない（#39 の課題が残る）

## 関連リンク

- Supersedes: [0002-integrate-dotclaude-public-into-hve-playbook](0002-integrate-dotclaude-public-into-hve-playbook.md)（出典の置き場所のみ）
- Related: [hve-playbook#39](https://github.com/taito-station/hve-playbook/issues/39)
