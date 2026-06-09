#!/usr/bin/env bats
# lib/is_test_command.sh の純粋関数を守るテスト。
# 実行: brew install bats-core してから  bats .claude/hooks/test/

setup() {
  source "${BATS_TEST_DIRNAME}/../lib/is_test_command.sh"
}

@test "pytest を検知する" {
  run is_test_command "cd backend && pytest"
  [ "$output" = "yes" ]
}

@test "python3 -m pytest を検知する" {
  run is_test_command "python3 -m pytest tests/"
  [ "$output" = "yes" ]
}

@test "テストでないコマンドは no" {
  run is_test_command "ruff check backend"
  [ "$output" = "no" ]
}

@test "pytest を部分文字列として含む別語は誤検知しない" {
  run is_test_command "echo mypytestfile"
  [ "$output" = "no" ]
}

@test "空文字は no" {
  run is_test_command ""
  [ "$output" = "no" ]
}
