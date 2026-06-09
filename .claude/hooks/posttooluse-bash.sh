#!/usr/bin/env bash
# PostToolUse(Bash) hook。
#
# 設計意図は「テストが緑になった瞬間に自動コードレビューを促す」こと。
# “緑かどうか” は実行後にしか分からないため、PreToolUse ではなく
# PostToolUse(Bash) に接続している（実行結果の exit code を見て判定する）。
#
# 流れ:
#   1. stdin の JSON から、実行された Bash コマンドと exit code を取り出す
#   2. lib/is_test_command で「テスト実行コマンドだったか」を判定
#   3. テスト かつ 成功(0) のときだけ、レビューを促すコンテキストを返す
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/is_test_command.sh
source "$HERE/lib/is_test_command.sh"

input="$(cat)"

# JSON 解析は jq 非依存にするため python3 を使う（このリポジトリの前提言語）。
cmd="$(printf '%s' "$input" | python3 -c '
import sys, json
d = json.load(sys.stdin)
print((d.get("tool_input") or {}).get("command", "").replace("\n", " "))
' 2>/dev/null || true)"

code="$(printf '%s' "$input" | python3 -c '
import sys, json
d = json.load(sys.stdin)
resp = d.get("tool_response") or {}
if not isinstance(resp, dict):
    print(0); sys.exit()
code = resp.get("exit_code", resp.get("returncode"))
if code is None:
    # exit code が取れない実装向けのフォールバック（失敗痕跡があれば 1 扱い）
    out = (resp.get("stdout", "") + resp.get("stderr", "")).lower()
    code = 1 if ("failed" in out or " error" in out) else 0
print(code)
' 2>/dev/null || echo 0)"

# テスト実行コマンドでなければ何もしない
[[ "$(is_test_command "$cmd")" == "yes" ]] || exit 0
# 緑(0)でなければ何もしない（赤のときはレビューを促さない）
[[ "$code" == "0" ]] || exit 0

msg="✅ テストが緑になりました。CLAUDE.md §5 の作業フローに従い、次は自動コードレビューの番です。今回の変更に対して /code-review を実行し、続けて ruff check backend / ruff format --check backend を通してください。"

python3 -c '
import json, sys
print(json.dumps({
    "hookSpecificOutput": {
        "hookEventName": "PostToolUse",
        "additionalContext": sys.argv[1],
    }
}))
' "$msg"
