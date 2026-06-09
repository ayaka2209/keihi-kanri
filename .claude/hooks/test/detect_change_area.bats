#!/usr/bin/env bats
# lib/detect_change_area.sh の純粋関数を守るテスト。

setup() {
  source "${BATS_TEST_DIRNAME}/../lib/detect_change_area.sh"
}

@test "backend の変更は BE" {
  run detect_change_area "backend/app/crud.py"
  [ "$output" = "BE" ]
}

@test "static の変更は FE" {
  run detect_change_area "static/app.js"
  [ "$output" = "FE" ]
}

@test "両方の変更は BE FE" {
  run detect_change_area $'backend/app/main.py\nstatic/app.js'
  [ "$output" = "BE FE" ]
}

@test "対象外ファイルは NONE" {
  run detect_change_area "README.md"
  [ "$output" = "NONE" ]
}

@test "空入力は NONE" {
  run detect_change_area ""
  [ "$output" = "NONE" ]
}
