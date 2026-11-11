# review-pr のセルフレビューを、スコープ内の誤りを直すことに絞って軽くする

## ステータス

Accepted — 2026-11-11

- 0025 の一部（結果の「test_review_pr_contracts.sh はメインの checkout の手順書を検査する」）を supersede する

## 背景と課題

review-pr のセルフレビュー（create-pr の Step 5 から呼ばれる）が重かった。full は Correctness・Security・Impact・Analyst の 4 エージェントで最大 3 巡、フラグなし（legacy）は Reviewer A/B + Fact-checker で最大 5 巡だった。直近のマージ済み PR 12 本のうち 5 本が 3 巡以上回り、#106 は 8 巡回った。

当初は「AI が書くコードなので、コード品質（命名・可読性）の観点は要らないのでは」という問題意識だった。しかし #121 の対応履歴では、auto-fix は 15 → 14 → 1 件で、そのうち命名・可読性に当たるものは 29 件中 2〜3 件だった。重さの原因は次のとおりだった。

1. スコープ外の指摘（「この場合も考慮すべき」）をそのまま auto-fix するので、レビュー中に PR のスコープが広がる。#121 の 2 巡目では、Docker Compose の stack を立てる節を新しく足した
2. 修正量が多いほど次の巡が回る（auto-fix した分を次の巡がまたレビューする）
3. 巡ごとのエージェント数

## 意思決定の要因

- Security の観点は削らない
- レビューを、PR のスコープ内の誤りを直す工程にする（設計をやり直す場にしない）
- 短縮禁止の趣旨（実行時に独断で構成・巡数を減らさない）は保つ
- skill・規則の文面は AI の挙動を決めるので、その曖昧さ・矛盾は品質の好みとして扱わない
- 人が書いた PR（review-only モード）では、「AI が書くから品質は要らない」という前提が成り立たない

## 検討した選択肢

- 指摘の扱い: スコープ外の指摘と [judgment] を直さず記録する（follow-up）／品質の観点だけを外す
- Impact の扱い: Correctness に統合する／共有部品の契約を変える diff のときだけ起動する
- legacy（フラグなし）の扱い: 廃止して full に寄せる／2 巡に揃えて残す
- full の巡数: 最大 2 巡（後半巡制約を 2 巡目から）／最大 3 巡のまま

## 決定内容

選択した選択肢: **スコープ外の指摘と [judgment] を `follow-up` として直さずに記録し、Impact を Correctness に統合し、legacy を廃止してフラグなしを full にし、full を最大 2 巡にする**。会話と Issue #122 のコメント（Plan の敵対的レビューの反映と PO の承認）による。

- **構成**: lightweight・full とも Correctness + Security + Analyst。depth で変わるのは巡数だけ（lightweight 1、full 2）。フラグなしは full
- **Correctness**: Impact の観点のうち「共有部品の契約変更による diff 外の caller の破壊」「データ整合性」と、性能（N+1・不要ループ・メモリ過剰）を引き継ぐ。命名・可読性・不要 import・typo は、review-only モード（既定では collaborator の PR）のときだけ [judgment] で報告する。`--fix` を明示して collaborator の PR を fix モードで回すときは報告しない。実行結果を変える綴り誤りは、モードによらず [defect]
- **種別**: skill・規則・手順書など AI が読んで従う文面の曖昧さ・矛盾は [defect] とする（共通ヘッダ）
- **Analyst**: 指摘ごとに PR のスコープの内外（`in|out`）を返す。in はこの diff が入れた誤り・壊したもの・Issue の成功条件の未達・PR 本文との食い違い、out は PR の目的の外の考慮漏れ・機能の追加・既存の問題
- **分類（fix モード）**: silent-reject → follow-up → escalate → auto-fix の順に判定する。follow-up は `scope == out` と [judgment]。ただし `[Security]`、Analyst の追加指摘のうち [defect]（目的適合性・criticalDecisions の宣言漏れ）、Issue の成功条件の未達は follow-up にしない。文面の曖昧さ・矛盾の [defect] も、この diff が入れたもの（scope in）だけを直す。follow-up を escalate より先に判定するのは、スコープ外の指摘が escalate の条件（仕様判断・データ整合性）に当たりやすく、escalate に落ちると early-break でその巡の auto-fix が止まるため
- **follow-up の扱い**: 直さず、対応履歴と Step 7 の報告に載せる（スコープ外は Issue の候補として内容と該当箇所つき、judgment は件数と要約）。収束判定と ITER_MAX 到達の判定に含めない
- **後半巡制約**: マージを止める級だけを報告させる制約を、3 巡目からではなく 2 巡目から付ける
- **ITER_MAX 到達の判定**: 「後半巡が Nice-to-have のみなら収束」の基準をやめ、最後の巡で auto-fix があれば、その修正を「未再レビュー」として報告に列挙する
- **短縮禁止**: 新しい構成・巡数を正規の値とし、「スコープ内の指摘を follow-up に倒して直さずに済ませる」を禁止する行動に加える
- **契約テスト**: `tests/test_review_pr_contracts.sh` の ROOT を、他の契約テストと同じくスクリプトのあるリポジトリ（worktree ならその作業ツリー）にする。メインの checkout を検査していたため、worktree で手順書を変えても検査できなかった（ADR 0025 の結果に書いた注意は、この変更で要らなくなる）

### 結果（Consequences）

- 1 巡のエージェント数は full で 4 から 3 に、巡数の上限は 3 から 2 に、フラグなしは 5 から 2 に減る
- スコープ外の考慮漏れはレビュー中に直らない。follow-up の報告から、必要なものを別の Issue にする
- 最後の巡（full の 2 巡目、lightweight の 1 巡目）で直した修正は、[Security] の修正を含めて再レビューされない。2 巡目のレビュアーロールの指摘はマージを止める級だけ（Analyst の追加指摘は級を問わない）で、未再レビューとして報告に残し人のレビューに委ねるので許容する（Security の修正だけ再レビューする案は、手順が増えるので採らなかった。PO の判断、Issue #122 の PR のセルフレビュー）
- 業務フローへの影響を専任で見るロールは無くなる。Issue の成功条件との照合（spec 観点）と Analyst の目的適合性に任せる
- 性能・diff 外の caller・データ整合性は Correctness が見るので、lightweight（バグ修正）でもこれらを見るようになる。データ整合性の指摘は escalate の条件に当たるので、lightweight で修正せずに止まる頻度が増えうる
- 自分の PR では、命名・可読性の指摘は直さない（judgment として件数だけ残る）
- create-pr Step 4 のブラウザテストの網羅性レビュー（最大 5 巡）と review-pr の Step 1.5（docs-drift / test-gap の事前検出）は変えていない

## 選択肢の評価（Pros and Cons）

### スコープ外の指摘と [judgment] を follow-up にする（採用）

#### メリット

- 巡数と修正量が減る原因（スコープの拡大）に直接効く
- スコープ外の指摘を捨てずに、Issue の候補として残せる

#### デメリット

- スコープの内外の判定が Analyst に依存し、ぶれると直すべき誤りが残る（常にスコープ内とする指摘を明記して抑える）

### 品質の観点だけを外す

#### メリット

- 変更が小さい

#### デメリット

- #121 の実績で auto-fix の 1 割未満にしか当たらず、効果が小さい

### Impact を Correctness に統合する（採用）

#### メリット

- 起動の判定が要らず、構成が depth によらず同じになる

#### デメリット

- Correctness の担当が増える。業務フローの専任の観点が無くなる

### 共有部品の契約を変える diff のときだけ Impact を起動する

#### メリット

- 必要なときだけ波及影響を深く見られる

#### デメリット

- 起動するかを親が diff から判定することになり、基準がぶれる

### legacy を廃止して full に寄せる（採用）

#### メリット

- モードが 1 つ減り、手順書と契約テストが単純になる

#### デメリット

- フラグなしの単独起動の挙動が変わる（Reviewer A/B の 2 名による多数決が無くなる）

### legacy を 2 巡に揃えて残す

#### メリット

- 変更範囲が小さい

#### デメリット

- 保守するモードが残る

### full を最大 2 巡にする（採用）

#### メリット

- 巡数の上限が下がる。後半巡制約を 2 巡目から付けるので、2 巡目はマージを止める級の確認になる

#### デメリット

- 2 巡目の修正が再レビューされない

### full を最大 3 巡のままにする

#### メリット

- 2 巡目の修正も再レビューできる

#### デメリット

- 上限が下がらず、重さの解消が follow-up の効果だけに頼る

## 関連リンク

- Related: [0016-hve-implement-skill-and-two-phase-call-from-resolve-issue](0016-hve-implement-skill-and-two-phase-call-from-resolve-issue.md)（`--depth` の決定者。変えない）
- Partially supersedes: [0025-run-tests-locally-by-discipline](0025-run-tests-locally-by-discipline.md)（契約テストの実行。test_review_pr_contracts.sh の注意を要らなくする）
- Related: [hve-playbook#122](https://github.com/taito-station/hve-playbook/issues/122)
