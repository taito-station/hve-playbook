# primary の checkout での作業ブランチへの切り替えを止める hook の仕様（Issue #117）

- 対象スコープ: hooks/main-commit-guard.py（または新しい hook）、rules/global/git/branching.md、resolve-issue・hve-implement・next-issue ほか、ブランチの切り替えを案内する skill・文書
- 対象ドキュメント:
  - `hooks/main-commit-guard.py`
  - `rules/global/git/branching.md`
  - `skills/global/resolve-issue/SKILL.md`
  - `skills/hve-implement/SKILL.md`
  - `skills/global/next-issue/SKILL.md`
  - `knowledge/adr/0020-gate-plan-headings-and-main-commit-with-hooks.md`
  - `knowledge/adr/0023-via-scope-for-commit-instruction-and-skill-enforcer.md`
  - `knowledge/adr/0033-block-writes-outside-launched-repository.md`
- 関連スコープ: hve-playbook#117
- 生成: aqod（primary の checkout での作業ブランチへの切り替えを hook で止め、着手を worktree に強制する仕様の未確定の点を確定させる）
- 状態: 回答済み
- 推論許可: 全問に推奨（既定値候補）を付ける。既定値のままの回答は承認とみなす
- 作成日: 2026-11-08
- 回答確定日: 2026-11-08
- 反映先: ADR 起票（knowledge/adr/0034）、`hooks/main-commit-guard.py`、`rules/global/git/branching.md`

## サマリー

primary の checkout（git-dir と git-common-dir が同じ作業ツリー）で作業ブランチへ切り替える Bash 操作を PreToolUse hook で止め、着手を worktree に強制する。Issue 本文の未確定の点 4 つに、調査で見つかった論点 3 つ（並走 clone も primary に当たる、main 上の未コミットの変更を switch -c で退避する既存の手順との衝突、hook の置き場所）を加えて確定させる。

---

[Q01]
- 対象ドキュメント: hooks/main-commit-guard.py
- 該当箇所: Issue #117「未確定の点」1、skills/global/parallel-setup/SKILL.md
- 問題種別: 不明瞭
- 重大度: critical
- 質問内容: hook を適用するリポジトリの範囲をどうするか（並走 clone の扱いを含む）
- 選択肢: A) remote を持つリポジトリすべて（並走 clone も含め、着手は常に worktree） B) remote を持ち、かつ他の worktree が既にあるリポジトリだけ C) 起動したリポジトリ（CLAUDE_PROJECT_DIR の checkout）だけ
- 未回答時の既定値候補: remote を持つリポジトリすべて（並走 clone も含め、着手は常に worktree）
- 既定値候補の理由: 共有の有無は hook から判定できず、条件付きにすると「今は自分だけ」と判断して外れる余地が残る（Issue の推奨と同じ）。規則が「着手は worktree」の 1 つになる。main-commit-guard と同じく remote の無い一時リポジトリは対象外
- 未回答のまま進めた場合の影響: 並走 clone を除外すると、clone を共有したときの事故（今回の #109、2026-10-18 の前例）が並走 clone で残る。含めると、並走 clone でも着手を worktree に変える必要がある

[Q02]
- 対象ドキュメント: hooks/main-commit-guard.py
- 該当箇所: Issue #117「未確定の点」3
- 問題種別: 不明瞭
- 重大度: major
- 質問内容: デフォルトブランチ以外の既存ブランチへの切り替え（他人の PR の確認など）も止めるか
- 選択肢: A) 止める（確認は worktree か git show / git diff で行う） B) 止めない（新しいブランチの作成だけを止める）
- 未回答時の既定値候補: 止める（確認は worktree か git show / git diff で行う）
- 既定値候補の理由: primary の HEAD を動かす点は新しいブランチの作成と同じで、他セッションへの影響も同じ（Issue の推奨と同じ）
- 未回答のまま進めた場合の影響: 止めないと、既存ブランチへの切り替えで primary の HEAD が動き、他セッションを巻き込む経路が残る

[Q03]
- 対象ドキュメント: hooks/main-commit-guard.py
- 該当箇所: Issue #117「未確定の点」4
- 問題種別: 不明瞭
- 重大度: minor
- 質問内容: 既にブランチを切り替えてしまった後の状態（hook の導入前や逃げ道で切り替えた後）を hook で扱うか
- 選択肢: A) hook では扱わない（切り替えの時点で止めるだけ） B) primary が作業ブランチにいたら警告を出す
- 未回答時の既定値候補: hook では扱わない（切り替えの時点で止めるだけ）
- 既定値候補の理由: 既存の状態の是正は範囲外。memory の「切り替えられたら戻さず worktree で続ける」の手順のままでよい（Issue の推奨と同じ）
- 未回答のまま進めた場合の影響: 扱う場合、primary が作業ブランチにある間の commit なども止めることになり、範囲が広がる

[Q04]
- 対象ドキュメント: skills/global/commit-workflow/SKILL.md ほか
- 該当箇所: branching.md:72-80、commit-workflow:14、hve-akm:43、git-push-merged-pr-check.py:144、apply-hve-playbook.md:61-63
- 問題種別: 一貫性欠落
- 重大度: major
- 質問内容: ブランチの切り替えを案内している他の箇所を、この PR でどこまで worktree の手順に合わせるか
- 選択肢: A) すべてこの PR で合わせる（Issue の 4 ファイルに加え、上の箇所も） B) Issue に挙げた 4 ファイルだけ合わせ、残りは別 Issue にする
- 未回答時の既定値候補: すべてこの PR で合わせる（Issue の 4 ファイルに加え、上の箇所も）
- 既定値候補の理由: 案内と hook が食い違う状態を残さない。どれも数行の差し替えで、1 トピック（着手を worktree に）の範囲に収まる
- 未回答のまま進めた場合の影響: 合わせないと、規則・skill が hook の止める操作を案内し続け、モデルがそれに従って止められる

[Q05]
- 対象ドキュメント: hooks/main-commit-guard.py
- 該当箇所: Issue #117「未確定の点」2
- 問題種別: 不明瞭
- 重大度: major
- 質問内容: 逃げ道 `# via:<名前>: <理由>` を設けるか
- 選択肢: A) 設ける: `# via:primary-branch-ok: <理由>`（理由必須） B) 設けない
- 未回答時の既定値候補: 設ける: `# via:primary-branch-ok: <理由>`（理由必須）
- 既定値候補の理由: ユーザーが primary での作業を明示的に指示する場合がある。main-commit-guard の `# via:main-commit-ok:` と同じ形にそろえる（Issue の推奨と同じ）
- 未回答のまま進めた場合の影響: 設けないと、ユーザーが primary での作業を明示的に指示したときに手段が無い

[Q06]
- 対象ドキュメント: hooks/main-commit-guard.py
- 該当箇所: ADR 0020 結果、ADR 0033 選択肢の評価
- 問題種別: 不明瞭
- 重大度: major
- 質問内容: hook をどこに置くか
- 選択肢: A) main-commit-guard に追加する（_parse・_git_call・cd の追跡を再利用） B) 新しい hook（例: primary-branch-guard.py）を足す
- 未回答時の既定値候補: main-commit-guard に追加する（_parse・_git_call・cd の追跡を再利用）
- 既定値候補の理由: ADR 0020・0033 の方針に沿う（hook を増やさず、パースと cd の追跡を共有する）。ADR 0033 で他リポジトリへの書き込みも同じ hook に入れた前例がある
- 未回答のまま進めた場合の影響: 新しい hook にすると ADR 0033 の却下理由と衝突し、ADR で覆す理由を書く必要がある

[Q07]
- 対象ドキュメント: rules/global/git/branching.md
- 該当箇所: branching.md:23,25、ADR 0023、hooks/main-commit-guard.py:688
- 問題種別: 一貫性欠落
- 重大度: critical
- 質問内容: main 上で作ってしまった未コミットの変更を作業ブランチへ退避する手順（今は primary で `git switch -c`）をどう変えるか
- 選択肢: A) stash で worktree へ移す: `git stash push -u -m <固有のタグ>` → `git worktree add .claude/worktrees/<名前> -b <branch> origin/<default>` → worktree で `git stash apply <その stash の SHA>` → 自分の stash を drop（素の pop は使わない。ADR 0023 は部分的に supersede） B) default ブランチ上に未コミットの変更があるときだけ、primary での `git switch -c` を通す C) 退避は逃げ道（via:primary-branch-ok）を付けた `git switch -c` で行う
- 未回答時の既定値候補: stash で worktree へ移す（A）
- 既定値候補の理由: primary の HEAD を動かさずに変更を移せる（stash は worktree 間で共有される）。stash は並走セッションとも共有されるので、タグと SHA で自分のものだけを扱う。規則が「primary は default のまま、作業は worktree」の 1 つで済む
- 未回答のまま進めた場合の影響: 決めないと、main-commit-guard の案内どおりに退避しようとして新しい hook に止められ、退避の手段が無くなる

---

## 回答（確定 2026-11-08）

| No. | 回答 | 判断 | 根拠 |
|---|---|---|---|
| Q01 | **remote を持つリポジトリすべて（並走 clone も含め、着手は常に worktree）** | 既定値承認 | 共有の有無は hook から判定できず、条件付きにすると「今は自分だけ」と判断して外れる余地が残る。remote の無い一時リポジトリは対象外。PR のセルフレビュー（2026-11-08）の追加の確認で、Docker Compose（Laravel Sail を含む）で動かすリポジトリも対象に含め、worktree に stack を立てる手順を branching.md に書くと確定（選択肢: compose のあるリポジトリを対象外にする／via で運用する／worktree で stack を立てる） |
| Q02 | **止めない（新しいブランチの作成だけを止める）** | 人間判断 | 既存ブランチへの切り替え（他人の PR の確認など）は止めず、`git switch -c` などの新しいブランチの作成だけを止める |
| Q03 | **primary が作業ブランチにいたら警告を出す** | 人間判断 | 切り替えた後の状態は止めずに警告で気づかせる。追加の確認（AskUserQuestion、2026-11-08）で、警告はセッションの開始時（SessionStart）に 1 回、起動したリポジトリの primary の checkout（remote を持つもの）がデフォルトブランチ以外にあるときに、標準出力でモデルへ渡すと確定（main-commit-guard が SessionStart の event も処理し、hook のファイルは増やさない）。PreToolUse の additionalContext は公式ドキュメントで確認できず、`permissionDecision: "allow"` は許可の確認を飛ばすので採らない |
| Q04 | **すべてこの PR で合わせる（Issue の 4 ファイルに加え、上の箇所も）** | 既定値承認 | 案内と hook が食い違う状態を残さない。どれも数行の差し替えで、1 トピック（着手を worktree に）の範囲に収まる。PR のセルフレビュー（2026-11-08）の追加の確認で、導入先に配る implement-flow・hve-implement・hve-akm の文面は「ブランチ運用規約に作業開始の手順（worktree に切るなど）があればそれに従う。無ければ、並走するセッションと共有しうるときは worktree に切る」と確定（rules/global と rules/hve の implement-flow を同じ行に保つため） |
| Q05 | **設ける: `# via:primary-branch-ok: <理由>`（理由必須）** | 既定値承認 | ユーザーが primary での作業を明示的に指示する場合がある。main-commit-guard の `# via:main-commit-ok:` と同じ形にそろえる |
| Q06 | **main-commit-guard に追加する（_parse・_git_call・cd の追跡を再利用）** | 既定値承認 | ADR 0020・0033 の方針に沿う（hook を増やさず、パースと cd の追跡を共有する）。ADR 0033 で他リポジトリへの書き込みも同じ hook に入れた前例がある |
| Q07 | （回答の欄の「ADR 0023 は部分的に supersede」は選択肢の文言のまま。実装時に訂正した。根拠の欄を参照）**stash で worktree へ移す（タグ付きの stash → worktree で SHA を指定して apply → 自分の stash を drop。ADR 0023 は部分的に supersede）** | 既定値承認 | primary の HEAD を動かさずに変更を移せる。stash は並走セッションとも共有されるので、タグと SHA で自分のものだけを扱う。実装時の確認: ADR 0023 の決定は「退避してから commit する」で退避の手段を定めていないため supersede せず、手段（`git switch -c`）を定めていた ADR 0020 の決定内容を ADR 0034 で部分的に supersede した。PR のセルフレビューで、primary は並走するセッションと共有されうるので、stash は `git status --porcelain` で確かめた自分の変更のパスだけに限り、言い切れない変更はユーザーに確認する形にした |
