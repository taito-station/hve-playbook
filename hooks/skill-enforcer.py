#!/usr/bin/env python3
"""
Pre-Tool-Use hook for Bash that blocks commands which should be invoked
through a dedicated route (a Skill or a wrapper script) instead.

Reads tool input from stdin (JSON) and:
- Returns exit 0 (allow) when the command does not match any known pattern.
- Returns exit 2 (block) with a stderr message naming the correct route
  when the command matches a registered pattern.

Triggered by Claude Code's PreToolUse hook with matcher="Bash".

Patterns are intentionally narrow: only block the literal commands that
correspond to a known route, so general bash usage is not affected.
"""

import json
import re
import sys


# Each rule: (compiled regex, route name (skill or wrapper script), reason)
RULES = [
    (
        re.compile(r"\bdrawio\b(?=[^|;&]*--export\b)"),
        "run-drawio-export",
        "drawio --export を直接呼ばないこと。~/.claude/hooks/run-drawio-export.sh 経由で実行する（Xvfb 起動と後始末をまとめてやる）。",
    ),
    (
        # The repo-override flag -R / --repo (persistent on `pr`) may sit before
        # and/or after `pr` (Issue #76). Only these typical forms are caught; the
        # hook does not parse shell syntax strictly (ADR 0020 / 0023).
        re.compile(
            r"\bgh\s+(?:(?:-R|--repo)=?\s*\S+\s+)?"
            r"pr\s+(?:(?:-R|--repo)=?\s*\S+\s+)?"
            r"(?:create|new)\b"
        ),
        "create-pr",
        "gh pr create / gh pr new を直接呼ばないこと。/create-pr スキル経由で実行する。",
    ),
    # NOTE: md-to-pdf rule removed.
    # /pdf skill's instructions internally call `npx md-to-pdf`, so this rule
    # would block the skill's own execution. Detecting "md-to-pdf without
    # prior SVG embedding" is too fragile, so we rely on memory/skill discipline
    # for /pdf invocation. drawio and gh pr create / gh pr new are still enforced because
    # those commands have meaningful pre/post setup that the skill orchestrates.
]


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except Exception as e:
        # If we can't parse, do not block.
        print(f"[skill-enforcer] failed to parse payload: {e}", file=sys.stderr)
        return 0

    tool_name = payload.get("tool_name") or payload.get("toolName")
    tool_input = payload.get("tool_input") or payload.get("toolInput") or {}

    if tool_name != "Bash":
        return 0

    command = tool_input.get("command", "") or ""
    if not isinstance(command, str):
        return 0

    # Bypass: explicit acknowledgment that the call is part of the route's flow.
    # Add a comment like `# via:run-drawio-export` at the end of the bash command
    # to confirm you went through that route (skill or wrapper script) first.
    # This forces a conscious confirmation rather than silent rule-evasion.
    # The via must name the matched rule's route exactly, so another hook's via
    # (e.g. `# via:main-commit-ok: ...`) or another route's via does not bypass it.
    # Escaped characters and quoted strings (within one line) are replaced with a
    # non-space placeholder first, and `#` counts only at line start or after
    # whitespace, so a via embedded in data (`--title "x # via:create-pr"`,
    # `'x'# via:...`, `x\ # via:...`) does not bypass. Quotes do not span lines, so an
    # unpaired `'` (e.g. "It's" in a heredoc body) does not swallow a real via.
    # A reason may follow as `# via:<route>: <reason>`, like the other hooks' via.
    stripped = re.sub(r"\\.|'[^'\n]*'|\"(?:[^\"\\\n]|\\.)*\"", "_", command)
    for pattern, skill, reason in RULES:
        if pattern.search(command) and not re.search(
            rf"(?:^|\s)#\s*via:{re.escape(skill)}(?=\s|$|:\s)", stripped
        ):
            print(
                "BLOCKED by skill-enforcer hook.\n"
                f"reason: {reason}\n"
                f"route: {skill}\n"
                "Stop and re-run via the route given in reason (a skill or a wrapper script).\n"
                f"Bypass (only after going through that route): append `# via:{skill}` to the command.",
                file=sys.stderr,
            )
            return 2

    return 0


if __name__ == "__main__":
    sys.exit(main())
