# 「コミットして」は main への commit の指示に当たらず、skill-enforcer の via はルート名の完全一致に限る

## ステータス

Accepted — 2026-10-13

## 背景と課題

ADR 0020 で、main / master 上の `git commit` を止める hook（main-commit-guard）を入れ、逃げ道を `# via:main-commit-ok: <理由>` にした。branching.md は「ユーザーが main への commit を明示的に指示したときだけ via を付ける」と書く。その PR（#61）のセルフレビューで、via の効く範囲について 2 点が残った（Issue #62）。

- commit-workflow は「『コミットして』と言われたら即座にコミット（追加確認不要）」と書く。main 上で「コミットして」とだけ言われたとき、via を付けて main に commit するのか、作業ブランチへ退避するのかが、規則の文面から決まらない
- skill-enforcer は、コマンドに `#\s*via:[a-z0-9_-]+` が 1 つでもあれば全ルールを素通しにしていた。そのため `# via:main-commit-ok: <理由>` を付けたコマンドにつないだ `gh pr create` が、`/create-pr` への誘導を受けない

## 意思決定の要因

- main を PR で守る branching の目的と、ADR 0020 の main-commit-guard の挙動（変えない）
- 「コミットして」の指示を、追加の確認なしで果たせること
- via は自己申告の逃げ道で、別の hook のための via が他の hook を通してしまわないこと
- 判定を最小限に保つ（ADR 0020 の「善意の誤操作の防止で、意図的な迂回への防御ではない」）

## 検討した選択肢

- 「コミットして」: 作業ブランチへ退避してから commit する／退避の前にブランチ名を確認する／via を付けて main に commit する
- 規則の置き場所: branching.md と commit-workflow の両方／branching.md だけ／commit-workflow だけ
- skill-enforcer の bypass: 当たったルールのルート名と完全に一致する via だけ／それに加えてクォート文字列を除いてから探す（destructive-guard と同じ方式）／via をシェルのコメントとして厳密に解釈する（main-commit-guard と同じ方式）／今のまま

## 決定内容

選択した選択肢: **「コミットして」は main への commit の指示に当たらない。remote を持つリポジトリでは作業ブランチへ退避してから commit し、ブランチ名を報告する。skill-enforcer は、当たったルールのルート名と完全に一致する `# via:<ルート名>`（後ろに `: <理由>` を続けてよい）が、クォートの外のコメントにあるときだけ通す**。質問票の回答（`qa/hook-gate-followups-questionnaire.md`）と、PR のセルフレビューでのユーザーの判断（クォートの除去）による。

- 規則の正本は branching.md（作業開始時の手順）。commit-workflow の「即座にコミット実行」に、main / master 上なら退避してから commit する旨を添えて branching.md を参照する。ユーザーが main への commit を明示したときは branching.md の via に従う
- remote の無いリポジトリは対象外とする。main-commit-guard の対象外（ADR 0020）と揃え、`git init` 直後の初回 commit（unborn の main で `git switch -c` すると main が作られない）を妨げない
- skill-enforcer は、エスケープした文字と 1 行の中のクォート文字列を空白を含まない文字に置き換えたコマンドで、行頭か空白の後の `#\s*via:<ルート名>` の直後が空白・行末・「`:` と空白」のいずれかであることを、ルールごとに確かめる。別の hook の via（`main-commit-ok`・`destructive-ok`）、ルート名に文字が続くもの（`create-prx`・`create-prX`・`create-pr:x`）、別ルートの via、クォート内やクォート直後の via（`--title "x # via:create-pr"`・`'x'# via:create-pr`）では通さない。理由付きの `# via:create-pr: <理由>` は、他の hook の via の書式と揃えて通す。2 つのルールに当たるコマンドは両方の via が要り、message は当たったルールを 1 つずつ示す
- 契約は `tests/test_skill_enforcer.sh` で固定する

### 結果（Consequences）

- 良い結果: main 上の「コミットして」の扱いが規則の文面から一意に決まる。main-commit-guard の via を付けたコマンドでも、`gh pr create` は `/create-pr` へ誘導される
- 悪い結果・既知の限界:
  - これまで別の名前の via で skill-enforcer を通していた呼び出しは止まる。リポ内に via を付けた呼び出しは無いが、他のリポや日頃の作業での利用は確かめられない。止まっても message が正しい via を示すので回復できる
  - 2 つのルールに当たるコマンドは、止められるたびに示された via を足す必要がある（最大 2 回）
  - クォートの対応は 1 行の正規表現による近似で、シェルの構文を厳密には解釈しない（ADR 0020 と同じ位置付け。skill-enforcer は誘導が目的）。heredoc の本文や、改行を含むクォート文字列の中の行頭の via は数える。`$'...'` の中のエスケープした引用符（`\'`）も解釈しない。クォートを行の中に限るのは、heredoc の本文の対にならない `'`（It's など）が別の行の `'` と組になり、正しい via ごと消えて止まる（message の案内に従っても回復できない）のを避けるため
  - via は自己申告で、ルートを経由したかは検証しない。message に従って via を足せば通る

## 選択肢の評価（Pros and Cons）

### 「コミットして」で作業ブランチへ退避する（採用）

#### メリット

- 追加の確認なしで指示を果たせ、main に commit を残さない（branching.md の「main に残さない」と一致）

#### デメリット

- ブランチ名をモデルが決める（規約どおりの名前にし、報告する）

### 退避の前にブランチ名を確認する

#### メリット

- ブランチ名をユーザーが決められる

#### デメリット

- commit-workflow の「追加確認不要」と食い違い、「コミットして」のたびに 1 往復増える

### via を付けて main に commit する

#### メリット

- 指示の字面どおりに即座に commit できる

#### デメリット

- 「main への明示的な指示」の条件が空洞になり、ADR 0020 の main-commit-guard を規則の側から外すことになる

### 規則を branching.md と commit-workflow の両方に書く（採用）

#### メリット

- 正本（branching.md）を保ちつつ、「コミットして」のときに読み込まれる commit-workflow だけを読んでも退避が決まる

#### デメリット

- 2 か所に書くので、変えるときは両方を直す

### 規則を branching.md だけ、または commit-workflow だけに書く

#### メリット

- 記述が 1 か所で済む

#### デメリット

- branching.md だけでは、commit-workflow の「即座に」だけを読んで main に commit しうる。commit-workflow だけでは、via の正本（branching.md）と規則が離れる

### 当たったルールのルート名と完全に一致する via だけ（クォートを除かない）

#### メリット

- 判定が単純で、別の hook の via・別ルートの via で通らない

#### デメリット

- データとして混ざった via（`--title "x # via:create-pr"`）で通る。PR のセルフレビューで指摘され、ユーザーの判断でクォートの除去を加えた

### 今のまま（どの名前の via でも全ルールを通す）

#### メリット

- 変更が無い

#### デメリット

- `# via:main-commit-ok: <理由>` を付けたコマンドにつないだ PR 作成が `/create-pr` へ誘導されない（Issue #62 の課題そのもの）

### クォート文字列を除いてから探す（採用）

#### メリット

- データとして混ざった via（`--title "x # via:create-pr"`）で通らない。destructive-guard と同じ 1 行の除去で済み、判定の仕組みを増やさない

#### デメリット

- heredoc の本文の via は数える（厳密な解釈はしない）

### via をシェルのコメントとして厳密に解釈する

#### メリット

- クォート内や heredoc の本文の via で通らない

#### デメリット

- 誘導が目的の hook に、main-commit-guard と同じ静的解析（shlex での分割と heredoc の判定）を持ち込むのは過剰（ADR 0020 の「B で同じコマンド内のブランチの切り替えを追う」の却下理由と同じ）

## 関連リンク

- Related: [0020-gate-plan-headings-and-main-commit-with-hooks](0020-gate-plan-headings-and-main-commit-with-hooks.md)
- Related: [hve-playbook#62](https://github.com/taito-station/hve-playbook/issues/62)
