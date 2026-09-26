#!/bin/bash
# scripts/session-cost.py の料金キー解決を固定する検査
#
# 実行: bash tests/test_session_cost.sh
#
# 前方一致の解決がキーの並び順に依存すると、新モデルの追加で旧料金に落ちる
# (例: claude-opus-5-5 が claude-opus-5 や claude-opus-4 に解決される)。
# 代表的なモデル ID と、期待するキー・入出力単価の対応を固定する。
# 期待値は公表価格 (https://platform.claude.com/docs/en/about-claude/pricing) から転記する。

set -u
SCRIPT="${SESSION_COST_SCRIPT:-$(cd "$(dirname "$0")/.." && pwd)/scripts/session-cost.py}"

python3 - "$SCRIPT" <<'EOF'
import importlib.util
import sys

spec = importlib.util.spec_from_file_location("session_cost", sys.argv[1])
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

# (モデル ID, 期待キー, 既知扱いか, input, output, cache_write, cache_read)
CASES = [
    ("claude-opus-5-5", "claude-opus-5-5", True, 4.0, 20.0, 5.0, 0.20),
    ("claude-opus-5", "claude-opus-5", True, 5.0, 25.0, 6.25, 0.50),
    ("claude-opus-4-8", "claude-opus-4-8", True, 5.0, 25.0, 6.25, 0.50),
    ("claude-opus-4-7", "claude-opus-4-7", True, 5.0, 25.0, 6.25, 0.50),
    ("claude-opus-4-6", "claude-opus-4-6", True, 5.0, 25.0, 6.25, 0.50),
    ("claude-opus-4-5-20251101", "claude-opus-4-5", True, 5.0, 25.0, 6.25, 0.50),
    ("claude-opus-4-1-20250805", "claude-opus-4", True, 15.0, 75.0, 18.75, 1.50),
    ("claude-sonnet-5", "claude-sonnet-5", True, 2.0, 10.0, 2.50, 0.20),
    ("claude-sonnet-4-6", "claude-sonnet-4", True, 3.0, 15.0, 3.75, 0.30),
    ("claude-haiku-4-5-20251001", "claude-haiku-4", True, 1.0, 5.0, 1.25, 0.10),
    ("claude-fable-5-1", "claude-fable-5-1", True, 10.0, 50.0, 12.50, 0.25),
    ("claude-fable-5", "claude-fable-5", True, 10.0, 50.0, 12.50, 1.0),
    ("claude-mythos-5-1", "claude-mythos-5-1", True, 10.0, 50.0, 12.50, 0.25),
    ("claude-mythos-5", "claude-mythos-5", True, 10.0, 50.0, 12.50, 1.0),
    ("<synthetic>", "claude-opus-5", False, 5.0, 25.0, 6.25, 0.50),
]

fail = 0
for model, key, known, inp, out, cw, cr in CASES:
    got_key, got_known = m.resolve_pricing_key(model)
    price = m.PRICING[got_key]
    ok = (got_key, got_known) == (key, known) and (price["input"], price["output"], price["cache_write"], price["cache_read"]) == (inp, out, cw, cr)
    print(f"[{'PASS' if ok else 'FAIL'}] {model} -> {got_key} known={got_known} {price['input']}/{price['output']}/{price['cache_write']}/{price['cache_read']}")
    fail |= not ok

# 並び順に依存しないこと: キー順を逆にしても同じ解決になる
m.PRICING = dict(reversed(list(m.PRICING.items())))
for model, key, known, *_ in CASES:
    if m.resolve_pricing_key(model) != (key, known):
        print(f"[FAIL] キー順を逆にすると {model} の解決が変わる")
        fail = 1
if not fail:
    print("[PASS] キー順に依存しない")

print("===================================")
print("ALL TESTS PASSED" if not fail else "SOME TESTS FAILED")
sys.exit(1 if fail else 0)
EOF
