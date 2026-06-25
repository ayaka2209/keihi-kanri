"""見積金額計算（quotes.compute_totals）の純粋関数テスト。

DB に触らないので SQLite/PostgreSQL の差を気にせず動く（grasp-testing）。
税抜(外税)・税込(内税)の2方式と、円未満の丸めを検証する。
"""

from app import quotes


def test_exclusive_tax_adds_on_top():
    # 税抜: 単価×数量の小計に消費税を上乗せする
    # 1000×2 + 3000×1 = 5000、消費税10% = 500、合計 5500
    subtotal, tax, total = quotes.compute_totals([2000, 3000], tax_mode="exclusive", tax_rate=10)
    assert subtotal == 5000
    assert tax == 500
    assert total == 5500


def test_exclusive_tax_floors_yen():
    # 端数は円未満切り捨て: 9999×10% = 999.9 → 999
    subtotal, tax, total = quotes.compute_totals([9999], tax_mode="exclusive", tax_rate=10)
    assert subtotal == 9999
    assert tax == 999
    assert total == 10998


def test_inclusive_tax_extracts_from_gross():
    # 税込: 単価が税込。合計=小計、内税を逆算する
    # 合計 11000、税抜 = 11000×100/110 = 10000、内税 = 1000
    subtotal, tax, total = quotes.compute_totals([11000], tax_mode="inclusive", tax_rate=10)
    assert total == 11000
    assert subtotal == 10000
    assert tax == 1000


def test_empty_items_are_zero():
    assert quotes.compute_totals([], tax_mode="exclusive", tax_rate=10) == (0, 0, 0)
