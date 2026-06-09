#!/usr/bin/env bash
# 純粋関数: 変更ファイルのパス（改行 or 空白区切り）から変更領域を判定する。
#   入力 : ファイルパスの並び（$1）
#   出力 : "BE" / "FE" / "BE FE" / "NONE"
# 副作用なし。bats(test/detect_change_area.bats)で守る。
detect_change_area() {
  local paths="$1"
  local out=""
  if printf '%s' "$paths" | grep -Eq '(^|/)backend/'; then
    out="BE"
  fi
  if printf '%s' "$paths" | grep -Eq '(^|/)static/'; then
    if [[ -n "$out" ]]; then out="$out FE"; else out="FE"; fi
  fi
  if [[ -z "$out" ]]; then out="NONE"; fi
  echo "$out"
}

if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
  detect_change_area "$1"
fi
