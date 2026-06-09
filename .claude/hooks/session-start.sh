#!/usr/bin/env bash
# SessionStart hook。
# 前回セッションのサマリ（.claude/.last-session.md）があれば、それを
# additionalContext として復元し、作業の続きに入りやすくする。
#
# サマリは「人が」または「セッション終了時に」.claude/.last-session.md へ
# 書いておく運用（このファイルは .gitignore 済み・個人ローカル）。
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SUMMARY_FILE="$HERE/../.last-session.md"

if [[ -f "$SUMMARY_FILE" ]]; then
  context="$(cat "$SUMMARY_FILE")"
else
  context="（前回サマリはありません。.claude/.last-session.md に書いておくと次回ここに復元されます。）"
fi

python3 -c '
import json, sys
print(json.dumps({
    "hookSpecificOutput": {
        "hookEventName": "SessionStart",
        "additionalContext": "## 前回セッションのサマリ\n\n" + sys.argv[1],
    }
}))
' "$context"
