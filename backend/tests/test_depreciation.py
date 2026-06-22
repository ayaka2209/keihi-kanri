"""
減価償却（定額法）の純粋計算テスト。

DB を使わない純粋関数なので SQLite/PostgreSQL の差（func.extract）と無関係に
高速・確実に検証できる。申告書の値とズレないことを守るのが目的。
"""

import datetime

from app import depreciation as dep


# ---- 償却率（定額法 = 1/耐用年数 を小数第3位に切り上げ）------------------
def test_annual_rate_matches_official_table():
    # 法定の定額法償却率表と一致すること
    assert dep.annual_rate_thousandths(6) == 167  # 普通車（新車）
    assert dep.annual_rate_thousandths(4) == 250  # 軽自動車（新車）
    assert dep.annual_rate_thousandths(3) == 334
    assert dep.annual_rate_thousandths(5) == 200
    assert dep.annual_rate_thousandths(7) == 143


# ---- 満年（12か月）の償却費 ---------------------------------------------
def test_full_year_straight_line():
    sched = dep.build_schedule(
        acquisition_cost=2_400_000,
        useful_life_years=6,
        acquisition_date=datetime.date(2024, 1, 1),  # 1月取得＝初年度も12か月
        business_ratio=100,
    )
    first = sched[0]
    assert first.year == 2024
    assert first.months == 12
    assert first.depreciation_amount == 400_800  # 2,400,000 × 0.167
    assert first.business_amount == 400_800
    assert first.closing_book_value == 2_400_000 - 400_800


# ---- 初年度の月割り（7月取得 → 6/12）-----------------------------------
def test_first_year_month_proration():
    sched = dep.build_schedule(
        acquisition_cost=2_400_000,
        useful_life_years=6,
        acquisition_date=datetime.date(2024, 7, 1),
        business_ratio=100,
    )
    assert sched[0].year == 2024
    assert sched[0].months == 6
    assert sched[0].depreciation_amount == 200_400  # 400,800 × 6/12


# ---- 事業按分（按分率70%）----------------------------------------------
def test_business_ratio_applied():
    sched = dep.build_schedule(
        acquisition_cost=2_400_000,
        useful_life_years=6,
        acquisition_date=datetime.date(2024, 1, 1),
        business_ratio=70,
    )
    assert sched[0].depreciation_amount == 400_800  # 償却費そのもの（按分前）
    assert sched[0].business_amount == 280_560  # 400,800 × 70%


# ---- 最終年度は備忘価額1円を残して止まる -------------------------------
def test_final_year_keeps_one_yen():
    sched = dep.build_schedule(
        acquisition_cost=1_000_000,
        useful_life_years=5,
        acquisition_date=datetime.date(2020, 1, 1),
        business_ratio=100,
    )
    last = sched[-1]
    assert last.year == 2024  # 5年で償却完了
    assert last.closing_book_value == 1  # 1円残す
    assert last.depreciation_amount == 199_999  # 200,000 ではなく1円残す分だけ
    # 合計償却額 = 取得価額 − 1円
    assert sum(s.depreciation_amount for s in sched) == 1_000_000 - 1


# ---- 売却・除却した年は供用月数まで償却し、翌年以降は計上しない ---------
def test_disposal_stops_depreciation():
    sched = dep.build_schedule(
        acquisition_cost=1_200_000,
        useful_life_years=6,
        acquisition_date=datetime.date(2024, 1, 1),
        business_ratio=100,
        disposal_date=datetime.date(2026, 8, 15),
    )
    years = [s.year for s in sched]
    assert years == [2024, 2025, 2026]  # 2027 以降は無い
    disposal_year = sched[-1]
    assert disposal_year.year == 2026
    assert disposal_year.months == 8  # 1〜8月
    assert disposal_year.depreciation_amount == 133_600  # 200,400 × 8/12


# ---- 特定年だけ取り出すヘルパ ------------------------------------------
def test_for_year_returns_none_before_service():
    kwargs = dict(
        acquisition_cost=2_400_000,
        useful_life_years=6,
        acquisition_date=datetime.date(2024, 1, 1),
        business_ratio=100,
    )
    assert dep.for_year(2023, **kwargs) is None  # 取得前の年は無し
    assert dep.for_year(2024, **kwargs).business_amount == 400_800
