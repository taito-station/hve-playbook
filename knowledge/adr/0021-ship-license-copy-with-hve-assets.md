# setup.sh は導入先に LICENSE の写しを .claude/LICENSE-hve-playbook として配る

## ステータス

Accepted — 2026-10-13

## 背景と課題

`setup.sh` は導入先の `.claude/` に、rules/hve・skills/hve-*・agents/hve-*.md・workflows/hve-*.js・scripts/hve（hve-scripts の写し）・CLAUDE.hve.md をコピーする。これらの多くは dahatake/HypervelocityEngineering（MIT）の派生物だが、LICENSE（著作権表示と許諾表示）は一緒にコピーしていなかった。MIT の条件は "The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software." で、導入先のリポジトリを公開・再配布すると、表示のない複製が出回りうる。CLAUDE.hve.md の出典の 1 行（「出典: dahatake/HypervelocityEngineering (MIT License)」）は、著作権表示と許諾表示そのものではない。

ADR-0015 は本リポの LICENSE を 3 者（taito-station・Daiyu Hatakeyama・youhei-ushio）の著作権行と MIT 本文だけにしたが、導入先に配る資産の扱いは範囲外とした（[hve-playbook#46](https://github.com/taito-station/hve-playbook/issues/46)）。

この判断は法的助言ではない。配る資産が「substantial portions」に当たるかの解釈はオーナーが判断した（`qa/hve-asset-license-notice-questionnaire.md` の Q04）。

## 意思決定の要因

- 導入先に配る資産に、上流と本リポの著作権表示・許諾表示が含まれること
- setup.sh を再適用しても表示が消えないこと（setup.sh は写しを削除してから置き直す）
- `.claude/` を ignore している導入先でも、表示が git 管理に入ること
- 導入先の毎セッションのコンテキストを増やさないこと

## 検討した選択肢

- 本リポの LICENSE をそのまま `.claude/LICENSE-hve-playbook` に 1 ファイルでコピーする
- rules/hve・skills/hve-*・scripts/hve の各ディレクトリに LICENSE を置く
- CLAUDE.hve.md の出典行を著作権表示と許諾文の全文にする
- 含めない（「substantial portions」に当たらないとして、根拠を記録する）

## 決定内容

選択した選択肢: **本リポの LICENSE をそのまま `.claude/LICENSE-hve-playbook` に 1 ファイルでコピーする**。

- `setup.sh` は実行のたびに `LICENSE` を導入先の `.claude/LICENSE-hve-playbook` にコピーする（上書きする）。中身は加工しない
- 1 本で全資産を覆う。hve-scripts は taito-station/paddock からの移植で、著作権者はオーナー本人だけなので、LICENSE の taito-station の行で覆われる（質問票の Q03）
- 「substantial portions」に当たるかを問わず、表示を含める（質問票の Q04）
- 適用プロンプト（`docs/prompts/apply-hve-playbook.md`）の、setup.sh が変更するものの一覧・退避対象・ignore の例外・確認の対象に `LICENSE-hve-playbook` を加える

本 ADR は ADR-0015 が範囲外とした点を決めるもので、ADR-0015 を置き換えない。

### 結果（Consequences）

- 良い結果: 導入先に配る資産に、3 者の著作権表示と MIT の許諾文が付く。本リポの LICENSE を変えたときも、setup.sh の再適用で写しが揃う
- 良い結果: 導入先の `.claude/` が ignore されていても、適用プロンプトの例外で表示が git 管理に入る
- 悪い結果: 写しは `.claude/` に 1 本だけなので、資産の一部（skill 1 つなど）だけを別の場所へ切り出すと、表示は付いて行かない。切り出す側で表示を持ち出す必要がある
- 悪い結果: 導入先が `.claude/LICENSE-hve-playbook` を手で書き換えても、再適用で上書きされる（hve-playbook の名を冠したファイルで、導入先が独自に書き換える理由は無いので許容する）

## 選択肢の評価（Pros and Cons）

### 本リポの LICENSE をそのまま `.claude/LICENSE-hve-playbook` に 1 ファイルでコピーする（採用）

#### メリット

- 変更が setup.sh の 1 か所で済み、ディレクトリ構成に依存しない
- 中身を加工しないので、本リポの LICENSE と食い違わない
- 導入先が `.claude/LICENSE` などを置いていても衝突しない

#### デメリット

- 資産を個別に切り出すと表示が付いて行かない

### rules/hve・skills/hve-*・scripts/hve の各ディレクトリに LICENSE を置く

#### メリット

- ディレクトリ単位で切り出しても表示が付いて回る

#### デメリット

- agents/hve-*.md と workflows/hve-*.js は導入先の既存ファイルと同じディレクトリにファイル単位で置くので、置けない（置くと導入先の agents/ 全体に掛かるように見える）

### CLAUDE.hve.md の出典行を著作権表示と許諾文の全文にする

#### メリット

- ファイルが増えない

#### デメリット

- 導入先で CLAUDE.md として毎セッション読み込まれうるので、コンテキストを消費する

### 含めない

#### メリット

- 変更が要らない

#### デメリット

- 含めなくてよい根拠を立てて維持する必要がある。含めるコストは 1 ファイルのコピーで、こちらのほうが安全

## 関連リンク

- Related: [0015-license-plain-mit-with-provenance-in-readme](0015-license-plain-mit-with-provenance-in-readme.md)（導入先に配る資産の扱いを範囲外とした）
- Related: [hve-playbook#46](https://github.com/taito-station/hve-playbook/issues/46)
- 質問票: `qa/hve-asset-license-notice-questionnaire.md`
