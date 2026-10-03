---
name: add-hook
description: Claude Code の hook (PreToolUse/PostToolUse/UserPromptSubmit/SessionStart/PermissionRequest) を新規追加する。雛形作成・settings.json 配線・検証・テストまでを型化し、「settings 参照 hook がファイル欠落で全 tool を block する」致命的事故を防ぐ。「hook を追加して」「新しい hook を作る」「PreToolUse hook を書く」のような自然言語で起動。
allowed-tools: Read, Edit, Write, Grep, Glob, Bash
---

# Claude Code hook の新規追加

新しい hook を本リポに追加し、`settings.json` に配線して安全に有効化する。

## 最重要原則 (なぜこの skill があるか)

**settings.json が参照する hook ファイルが存在しないと、その event の tool 呼び出しが
すべて exit 2 で block される**(例: `PreToolUse` Bash hook のファイル欠落 → 全 Bash が
死ぬ)。本 skill は配線・配備・検証を型化してこれを防ぐ。

**配備**: `~/.claude/hooks/` には、`sync-dotclaude.sh` が repo `hooks/` の `*.py` / `*.sh` を
**ファイル単位で symlink** する。repo の `hooks/` に置いただけでは `~/.claude/hooks/` に現れず、
sync を実行して初めてリンクが張られる。したがって hook 追加の手順は
「① repo に置く ② settings.json に配線 ③ sync を実行して検証」に集約される。

## 手順

### 1. hook ファイルを作成

`hooks/<name>.py` をリポジトリルートに作成する。雛形 (fail-open + bypass 規約):

```python
#!/usr/bin/env python3
"""<name>.py — Claude Code <Event> hook。<目的を 1-2 行で>"""
from __future__ import annotations
import json, sys
# import re, os 等は必要に応じて

def main() -> int:
    try:
        try:
            payload = json.load(sys.stdin)
        except (json.JSONDecodeError, ValueError, OSError):
            return 0
        if not isinstance(payload, dict):
            return 0
        # event / tool_name で対象を絞る (防御 filter: 誤配置でも安全に振る舞う)
        # event = payload.get("hook_event_name", "")
        if payload.get("tool_name") != "Bash":   # 例: Bash 限定 hook
            return 0
        ti = payload.get("tool_input") or {}
        cmd = ti.get("command", "") if isinstance(ti, dict) else ""
        # ... 判定 ...
        # block する場合: 理由を stderr に出して return 2
        #   bypass 規約を設けるなら `# via:<name>-ok: <理由>` を見て return 0
        return 0
    except BaseException:
        # hook 失敗で Claude Code を止めない原則 (fail-open)
        return 0

if __name__ == "__main__":
    sys.exit(main())
```

規約:
- **例外は握って exit 0 (fail-open)**。hook のバグで tool を止めない。
- **block は exit 2** + 理由を stderr に。block hook には **bypass マーカー**
  (`# via:<name>-ok: <非空の理由>`) を設けると、誤検知時の escape hatch になる
  (destructive-guard と同じ流儀)。
- 個人パス・プロジェクト名をハードコードしない (public 共有のため。`~` を使う)。

`chmod +x hooks/<name>.py` は任意 (settings は `python3 ~/.claude/hooks/<name>.py` で
起動するので shebang 非依存。慣習として付けてよい)。

### 2. settings.json に配線

repo の `settings.json` の `hooks.<Event>` に追加する（マシン固有の hook は
`~/.claude/settings.machine.json` に書く）。`~/.claude/settings.json` は `sync-dotclaude.sh` が
repo 版と `settings.machine.json` から生成するファイルなので、直接編集しない（次の同期で退避・上書きされる。
ADR-0006）。Event と matcher を正しく選ぶ:

- `PreToolUse` / `PostToolUse`: matcher は tool 名 (`"Bash"` / `"Write"` 等)、全 tool は `""`
- `UserPromptSubmit` / `SessionStart` / `PermissionRequest`: matcher は `""` または
  source 等 (例: SessionStart の `"startup|clear"`)

既存ブロックに `{"type":"command","command":"python3 ~/.claude/hooks/<name>.py"}` を追加。
**hook の実行順が意味を持つ場合は順序に注意**(例: PreToolUse(Bash) で skill-enforcer.py を
他のガード hook より先に置く等)。

### 3. 検証 (必須)

以下を**すべて**通す:

```bash
# (a) JSON 妥当性
python3 -c "import json; json.load(open('settings.json')); print('settings.json OK')"
# (b) Python 構文
python3 -m py_compile hooks/<name>.py && echo "compile OK"
# (c) スモークテスト (benign payload → exit 0、対象形 → 期待の exit)。
#     コマンド文字列にトリガー語を「データとして」埋め込むと destructive-guard 等に
#     誤反応されるので、payload は python で組み立てて渡す
# (d) settings 参照 hook が全解決するか (★最重要: 欠落 = 全 tool block の致命傷を検出)
#     先に sync で ~/.claude/settings.json を再生成する。sync 自身も参照 hook を検査し、
#     欠落があれば FATAL (exit 1) で配置を止める。exit 1 なら以下に進まず原因を直す
bash sync-dotclaude.sh
python3 - <<'PY'
import json, os, re
from pathlib import Path
s = json.load(open(os.path.expanduser("~/.claude/settings.json")))
miss=[]; seen=set()
for ev, blocks in s.get("hooks", {}).items():
    for b in blocks:
        for h in b.get("hooks", []):
            m = re.search(r"(~/\.claude/hooks/[\w.-]+\.(?:py|sh))", h.get("command",""))
            if m and m.group(1) not in seen:
                seen.add(m.group(1))
                if not Path(os.path.expanduser(m.group(1))).exists():
                    miss.append(m.group(1))
print(f"参照 hook {len(seen)} / 欠落 {len(miss)}:", miss or "なし → OK")
assert not miss, f"欠落 hook あり (放置すると当該 event の tool が全 block): {miss}"
PY
```

### 4. テスト (block する hook なら必須)

`tests/test_<name>.sh` を追加し、**block / allow / bypass / 対象外 event** を網羅する
(`tests/test_destructive_guard.sh` を雛形に。各ケースは `&&` 連結、`run "名前" 関数`
形式)。block-regex 系の hook は **バイパス変種を敵対的にテスト**する
(オプション束ね・クォート・別演算子・前置オプション等)。

### 5. 設計判断の記録 (仕様変更を伴う場合)

hook が挙動ポリシーを変える場合は、その判断理由を記録する (リポに ADR を置く運用なら
`knowledge/adr/` または `docs/adr/` に追加。最低限 PR 本文に背景を残す)。

### 6. PR 化

`/create-pr` で PR を作成 (セルフレビューまで自走)。

## 注意事項

- **settings.json は起動時 snapshot** として読まれる。配線の
  ライブ反映は次回起動分。ただし block hook のファイル欠落は稼働中セッションでも
  顕在化しうるため、手順 3(d) の解決検証は必ず行う。
- `~/.claude/hooks/` への symlink は `sync-dotclaude.sh` が張る（手作業で張らない）。hook を
  追加・改名・削除したら sync を実行する。消えた hook を指すリンクは sync が dangling として
  知らせ、`--prune` で除去できる。改名・削除するときは、同じ変更の中で settings.json（または
  settings.machine.json）の配線も直してから sync する（直さないと参照 hook の欠落として FATAL に
  なり、settings.json が配置されない）。
- block hook を追加すると、稼働中セッションは再起動するまで反映されない一方、再起動した
  セッション/parallel は即座に新挙動になる。並走環境では全 parallel の再起動タイミングに留意。
