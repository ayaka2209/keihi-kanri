#!/usr/bin/env bash
# 純粋関数: 引数の文字列が「テスト実行コマンド」かを判定する。
#   入力 : コマンド文字列（$1）
#   出力 : "yes" または "no"
# 副作用なし。bats(test/is_test_command.bats)で守る。
is_test_command() {
  local cmd="$1"
  # 単語境界つきで pytest / python -m pytest を検知（mypytestfile 等は誤検知しない）
  if printf '%s' "$cmd" | grep -Eq '(^|[^a-zA-Z])pytest($|[^a-zA-Z])|python[0-9.]*[[:space:]]+-m[[:space:]]+pytest'; then
    echo "yes"
  else
    echo "no"
  fi
}

# スクリプトとして直接実行されたときだけ、引数を判定して出力する。
# （source されたときは何もしない＝純粋関数として再利用できる）
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
  is_test_command "$1"
fi
