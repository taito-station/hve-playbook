# 計画の必須見出しと main への commit を hook でゲートする

## ステータス

Accepted — 2026-10-12

## 背景と課題

開発ルール（Plan モード必須、implement-flow の Step 2〜4、ブランチ必須、ルール準拠表）は rules・skill の文面とメモリに頼っており、計画の段階で「ルール遵守の確認」による差し戻しが続いた（2026-09-27、10-03、10-04 に 2 件）。ADR 0016 も、hve-implement の順序を実行時に守らせる仕組みは同梱していないと書いている。

既存の hook は、破壊的なコマンドや誤った push などの安全ガード（destructive-guard・git-push-merged-pr-check・sail-env-inline-block・sql-schema-check）と、skill への誘導（skill-enforcer）に限られ、ルールの順守を止めるものは無かった。これまでの判断は「止めるより注意に留める」方向だった（ADR 0003 は create-pr の AKM チェックを STOP ゲートにせず、ADR 0010 は LSP を強制する hook を廃止した）。

## 意思決定の要因

- 差し戻しの実績がある箇所（計画にゲートの結果と準拠表が無い、main への commit）を機械的に止める
- ADR 0004 のとおり、サブエージェントと skill の自動フローを止めない
- 正規の手順（resolve-issue・create-issue・edit-issue が、ブランチを切る前の main 上でファイルを書く）を誤って止めない
- hook 自体が壊れたときに Claude Code を止めない（add-hook skill の fail-open）
- 除外リストのような保守の要る仕組みを増やさない

## 検討した選択肢

- A の発火点: PermissionRequest（matcher: ExitPlanMode）／PreToolUse（matcher: ExitPlanMode）
- A の適用範囲: 全計画／HVE のリポジトリだけ／専用のマーカーで検査を省ける
- A の判定: 見出しの語を含めば可＋準拠表に表の行／完全一致／見出しの有無だけ
- B の対象: `git commit` だけ／Edit・Write も（追跡済みファイルに限り除外パスを持つ）／Edit・Write も（resolve-issue のブランチ作成を早める）
- B で同じコマンド内のブランチの切り替え（`git switch -c x && git commit`）を追う／追わない
- 計画の承認前に Edit・Write を止める
- UserPromptSubmit で毎回チェックシートを注入する

## 決定内容

選択した選択肢: **A は PermissionRequest/ExitPlanMode で全計画の 2 見出しを検査し、B は main / master 上の `git commit` だけを止める**。範囲・適用・判定は質問票の回答（`qa/hook-rule-gate-scope-questionnaire.md`）による。

- **A: `hooks/plan-gate-check.py`**（PermissionRequest、matcher `ExitPlanMode`）
  - 計画本文（`tool_input.plan`、無ければ `tool_input.planFilePath` のファイル）に、見出し「ゲートの確認結果」と「ルール準拠表」があるかを検査する
  - 見出しは `#`〜`####`（行頭の空白は 3 つまで）。見出しの文字列が語を含めばよい。ルール準拠表の節（同じか上位のレベルの次の見出しまで）に `|` を含む行が 1 行以上必要。コードフェンスの中の行は数えない
  - 全計画に適用する。implement-flow の対象外の計画は「ゲートの確認結果」に「対象外: <理由>」と書く。専用の逃げ道は設けない
  - 欠けていれば `hookSpecificOutput.decision.behavior = "deny"` の JSON で止め、足りない見出しと書き方を message で返す。計画本文が無い（`tool_input` が `{}`）ときも止める。Claude Code は計画ファイルの中身を `tool_input.plan` に入れて渡すが、計画ファイルの Write と ExitPlanMode を同じ応答で並列に呼ぶと、書き込む前の内容（初回はファイルが無いので `{}`）で判定される（2026-10-12 の E2E で、transcript の message id と debug ログの入力から確認した）。deny の message でこの並列呼び出しも案内する。過去の差し戻し 3 件も `{}` だった
- **B: `hooks/main-commit-guard.py`**（PreToolUse、matcher `Bash`）
  - セグメントの先頭が `git` で subcommand が `commit` のとき、判定するリポジトリ（`git -C`、同じコマンド内の `cd` と `env -C`、payload の `cwd`）の実行前の `git symbolic-ref -q HEAD` が `refs/heads/main` / `refs/heads/master` なら exit 2 で止める（unborn のブランチも含む）。同じコマンド内のブランチの切り替えは追わないので、作業ブランチへの退避（`git switch -c`）と commit は別の Bash 呼び出しで実行する（deny の message と branching.md で案内する）
  - Edit・Write は止めない。main 上で作った変更は `git switch -c` で退避してから commit する（branching.md）
  - 逃げ道は `# via:main-commit-ok: <理由>`（理由必須、クォート内・heredoc の本文・単語の途中は無効）。via はコマンド中のどのコメントにあっても、そのコマンドのすべての commit を通す
- 規則の正本: 見出しの規則は CLAUDE.md・hve-implement（単独モードの承認）・resolve-issue（Plan のフォーマット）に、main への commit の停止は branching.md に書く。hve-implement は導入先に配るが hook は配らないので、hve-implement には hook のことを書かない
- 契約は `tests/test_plan_gate_check.sh` と `tests/test_main_commit_guard.sh` で固定する

### 結果（Consequences）

- 良い結果: ゲートの結果と準拠表の無い計画は、承認画面に出る前に足りない見出しを示して差し戻される。main 上でうっかり commit することを、正規の手順を止めずに防げる。どちらも ADR 0004 の範囲（ExitPlanMode を呼ぶのは Plan モードの計画だけ、commit は作業ブランチ上で行う）に収まり、サブエージェントや自動フローの正規の動きを止めない
- 悪い結果・既知の限界:
  - A は見出しがあるかを検査するだけで、中身が検討されたかは検査できない。Plan モードを経ない承認（resolve-issue の AskUserQuestion）は A の対象外で、テンプレートの見出しで補う
  - Plan モードに入らずに実装を始めた場合、A は発動しない（Plan モードの開始は CLAUDE.md の規則に頼る）
  - A は ExitPlanMode の承認画面（PermissionRequest）で動くので、ExitPlanMode を事前に許可する（settings の allow に入れる）など承認画面を出さない設定・モードでは発動しない。ExitPlanMode は allow に入れない。auto モードで発動するかは未確認（マージ後に確かめる）
  - Claude Code の将来の版で ExitPlanMode が常に `{}` で呼ばれるようになると、A がすべての計画を止める（deny の message で気づける。Plan モードは手動で抜けられる）
  - deny のあと、同じ event の他の hook（応答待ちの表示（この環境では Orca の agent hook）や通知音）も発火するので、人の入力が要らない自動の差し戻しでも応答待ちのように見える
  - B はシェルの構文を完全には解釈しない best-effort の静的判定で、Claude Code がふだん出す形（`git commit` / `git -C <リテラルのパス>` / `&&`・`;`・改行での連結 / `<<'EOF'` の heredoc）を対象にする。変数・コマンド置換・前置コマンド・予約語の中の `cd` など、それ以外の形は見逃すことがあり、分割に失敗したコマンドは通す（fail-open）。限界を個別に列挙すると「列挙に無いものは対応済み」と読めて境界ケースの追加を誘うので、一般的に書く（PR #61 のレビューで、個別の列挙が巡ごとに新しい指摘を呼んだ）。直すのは、Claude Code がふだん出す形での見逃し、正規の手順を止める誤検知、判定を単純にする修正に限る。逆に、同じコマンド内で作業ブランチへ退避してからの commit（`git switch -c x && git commit`）と、`git commit --dry-run` / `-h` は main 上では止める（message の案内どおり別の Bash 呼び出しにすれば回復できる）
  - add-hook skill の規約は「block は exit 2」「PermissionRequest の matcher は `""` など」だったので、PermissionRequest で拒否するときは JSON の decision で exit 0、matcher は tool 名、という流儀を同じ PR で add-hook に追記した（PermissionRequest で拒否する公式の方式が JSON の decision で、matcher が tool_name に当たるため）
  - リポ版の hook は `settings.machine.json` で外せない（ADR 0006）。user-level 基盤は作者の個人設定という位置付け（ADR 0007）なので、この 2 つのゲートも外す手段を設けない。main だけで運用するリポジトリでは、ユーザーの明示指示のもとで via を付ける
  - hook の実体は clone の作業ツリーへの symlink なので、マージして sync したあと、symlink 先の clone で hook のファイルを持たないブランチ（マージ前に切ったもの）を checkout すると、実体が消えて `python3 <無いファイル>` が exit 2 を返し、Bash と ExitPlanMode が全面的に止まる。symlink 先の clone は main のまま使い（作業は worktree で行う）、マージ前のブランチは先に main へ rebase してから checkout する。欠落時に通すラッパーは、add-hook の「欠落は sync で検出して fail-loud にする」方針と衝突するので採らない
  - PreToolUse の Bash の python hook が 5 本目になり、Bash の呼び出しごとに python の起動が 1 回増える（main-commit-guard は `commit` を含まないコマンドではすぐ終わる）。これ以上増やすときは 1 プロセスへの統合を検討する
  - A・B の目的は善意の誤操作（規則の見落とし）の防止で、意図的な迂回への防御ではない。via は自己申告の逃げ道で、上の限界のとおり迂回の手段もある。main の保護は branch protection に任せる（knowledge-maturity の検査スクリプトと同じ位置付け。ADR 0014）
  - ADR 0003・0010 の「止めるより注意に留める」方向を、この 2 点に限って覆す

## 選択肢の評価（Pros and Cons）

### A を PermissionRequest に置く（採用）

ExitPlanMode が PermissionRequest を発火し、計画本文が `tool_input.plan` に入ることを、実際の payload（許可要求ログ hook の debug ログ、258 件）で確かめた。

#### メリット

- 発火と入力の形を実データで確認できている

#### デメリット

- 同じ event の他の hook（ログ・tmux・通知音）も発火する

### A を PreToolUse に置く

#### メリット

- add-hook skill の「block は exit 2」の規約にそのまま乗る

#### デメリット

- ExitPlanMode で発火するかを確認できなかった（公式の例は PermissionRequest だけで、headless の `claude -p` は ExitPlanMode を提供しない）

### A を HVE のリポジトリだけに適用する、または専用のマーカーで検査を省ける

#### メリット

- HVE 以外の計画、対象外の計画で誤って止めない

#### デメリット

- HVE かどうかの判定という分岐が増える。HVE 以外では今の問題が残る。マーカー 1 つで抜けられる

### A を完全一致、または見出しの有無だけで判定する

#### メリット

- 判定が単純

#### デメリット

- 完全一致は表記揺れで止まりやすい。有無だけだと見出しを置いて中身を空にできる

### B で Edit・Write も止める（追跡済みファイルに限り除外パスを持つ、またはブランチ作成を早める）

#### メリット

- main 上の編集に、commit より前に気づける

#### デメリット

- resolve-issue・create-issue・edit-issue の正規の書き込み、`~/.claude` 配下の symlink 先（hve-playbook の main）、main 上で作業するリポジトリを止める。除外リストの保守か、skill 3 本の改修が要る

### B で同じコマンド内のブランチの切り替えを追う

#### メリット

- deny の message が案内する `git switch -c <branch>` と commit を 1 つのコマンドにつないでも止まらない

#### デメリット

- 区切りの演算子（`;` / `||` では switch が失敗しても commit が走る）、`git switch -`、`--track origin/main`、`--create=<name>`、サブディレクトリでの commit など、追う形が次々に増え、PR #61 のレビューでは追跡そのものが main への commit を見逃す経路になった。誤操作の防止という目的に対して、静的解析への投資が過剰になる

### 計画の承認前に Edit・Write を止める

#### メリット

- Plan モードを飛ばすこと自体を止められる

#### デメリット

- 「3 ステップ以上か」を hook では判定できず、小さな修正やサブエージェントの編集まで止まる（ADR 0004 と衝突する）

### UserPromptSubmit でチェックシートを注入する

#### メリット

- 止めずに毎回思い出させる

#### デメリット

- 文面を増やすだけで今の効き目と変わらず、毎回トークンを使う

## 関連リンク

- Related: [0005-default-model-opus-alias](0005-default-model-opus-alias.md)（「意思決定の要因」の hook の分類で、PreToolUse の安全ガードを 4 本と列挙している。main-commit-guard が加わったので、その記述は現状を表さない。0005 の決定内容（既定モデル・権限モード）は変わらない）
- Related: [0003-add-session-cost-and-akm-to-create-pr](0003-add-session-cost-and-akm-to-create-pr.md)
- Related: [0004-audit-prompts-for-opus-5-5](0004-audit-prompts-for-opus-5-5.md)
- Related: [0010-drop-serena-for-builtin-lsp](0010-drop-serena-for-builtin-lsp.md)
- Related: [0016-hve-implement-skill-and-two-phase-call-from-resolve-issue](0016-hve-implement-skill-and-two-phase-call-from-resolve-issue.md)
- Related: [hve-playbook#55](https://github.com/taito-station/hve-playbook/issues/55)
