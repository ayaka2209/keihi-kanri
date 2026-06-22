"""
減価償却の計算（定額法）。

ここは DB に一切触らない純粋関数だけを置く（crud は DB 専用、という層の責務を守る）。
個人事業主の原則どおり定額法のみを扱う。値は確定申告書「減価償却費の計算」欄に
そのまま転記できることを目標にする。

計算ルール（定額法・2007/4/1 以降取得）:
  償却率   = 1 / 耐用年数 を小数第3位に切り上げ（法定の定額法償却率表と一致）
  本年分   = 取得価額 × 償却率 × 本年中の供用月数 / 12   （円未満は切り上げ）
  事業分   = 本年分 × 事業専用割合(%)                    （円未満は四捨五入）
  最終年度 = 帳簿価額に 1円（備忘価額）を残して償却を止める
  売却・除却した年は供用月数まで償却し、翌年以降は計上しない
"""

import datetime
from dataclasses import dataclass


@dataclass
class YearlyDepreciation:
    """ある1年分の償却明細（申告書「減価償却費の計算」欄に対応）。"""

    year: int
    months: int  # その年の供用月数（1〜12）
    opening_book_value: int  # 期首帳簿価額
    full_year_amount: int  # 満額（12か月・按分前）の年間償却費（表示用）
    depreciation_amount: int  # 本年分の償却費（月割り後・按分前）
    business_amount: int  # 事業分（按分後）＝ 必要経費算入額
    closing_book_value: int  # 期末帳簿価額


def annual_rate_thousandths(useful_life_years: int) -> int:
    """定額法償却率を「千分率の整数」で返す。1/n を小数第3位に切り上げた値。

    例: 6年 → 167（=0.167） / 4年 → 250 / 3年 → 334
    整数演算で計算し浮動小数の誤差を避ける。
    """
    if useful_life_years <= 0:
        raise ValueError("useful_life_years は1以上")
    return _ceil_div(1000, useful_life_years)


def annual_rate(useful_life_years: int) -> float:
    """定額法償却率（小数）。表示用。"""
    return annual_rate_thousandths(useful_life_years) / 1000


def build_schedule(
    *,
    acquisition_cost: int,
    useful_life_years: int,
    acquisition_date: datetime.date,
    business_ratio: int,
    disposal_date: datetime.date | None = None,
    method: str = "straight_line",
) -> list[YearlyDepreciation]:
    """取得から償却完了（または売却・除却）までの年次明細を順に返す。

    method:
      straight_line … 通常の減価償却（定額法）
      lump_sum_3y   … 一括償却資産（3年均等・月割りなし。耐用年数/除却は無視）
      small_special … 少額減価償却資産の特例（取得年に全額即時償却）
    """
    if method == "lump_sum_3y":
        return _lump_sum_schedule(acquisition_cost, acquisition_date, business_ratio)
    if method == "small_special":
        return _small_special_schedule(acquisition_cost, acquisition_date, business_ratio)
    return _straight_line_schedule(
        acquisition_cost, useful_life_years, acquisition_date, business_ratio, disposal_date
    )


def _straight_line_schedule(
    acquisition_cost: int,
    useful_life_years: int,
    acquisition_date: datetime.date,
    business_ratio: int,
    disposal_date: datetime.date | None,
) -> list[YearlyDepreciation]:
    """定額法のスケジュール。"""
    rate = annual_rate_thousandths(useful_life_years)
    full_year_amount = _ceil_div(acquisition_cost * rate, 1000)

    schedule: list[YearlyDepreciation] = []
    accumulated = 0
    year = acquisition_date.year
    # 月割りの関係で耐用年数より延びることがあるため、安全弁付きで回す。
    hard_stop = acquisition_date.year + useful_life_years + 2

    while True:
        months = _months_in_service(year, acquisition_date, disposal_date)
        if months == 0:
            break

        opening = acquisition_cost - accumulated
        amount = _ceil_div(acquisition_cost * rate * months, 12_000)

        # 備忘価額1円を必ず残す
        if accumulated + amount > acquisition_cost - 1:
            amount = acquisition_cost - 1 - accumulated
        if amount < 0:
            amount = 0

        accumulated += amount
        closing = acquisition_cost - accumulated

        schedule.append(
            YearlyDepreciation(
                year=year,
                months=months,
                opening_book_value=opening,
                full_year_amount=full_year_amount,
                depreciation_amount=amount,
                business_amount=business_share(amount, business_ratio),
                closing_book_value=closing,
            )
        )

        if closing <= 1:
            break
        if disposal_date is not None and year >= disposal_date.year:
            break
        if year >= hard_stop:
            break
        year += 1

    return schedule


def _lump_sum_schedule(
    acquisition_cost: int,
    acquisition_date: datetime.date,
    business_ratio: int,
) -> list[YearlyDepreciation]:
    """一括償却資産：取得価額を3年で均等償却（月割りなし・備忘1円なし）。

    端数は最終年に寄せて合計＝取得価額にする。除却しても3年継続が原則。
    """
    schedule: list[YearlyDepreciation] = []
    base = acquisition_cost // 3
    accumulated = 0
    for i in range(3):
        amount = base if i < 2 else acquisition_cost - base * 2
        opening = acquisition_cost - accumulated
        accumulated += amount
        schedule.append(
            YearlyDepreciation(
                year=acquisition_date.year + i,
                months=12,
                opening_book_value=opening,
                full_year_amount=base,
                depreciation_amount=amount,
                business_amount=business_share(amount, business_ratio),
                closing_book_value=acquisition_cost - accumulated,
            )
        )
    return schedule


def _small_special_schedule(
    acquisition_cost: int,
    acquisition_date: datetime.date,
    business_ratio: int,
) -> list[YearlyDepreciation]:
    """少額減価償却資産の特例：取得年に全額を即時償却する。"""
    return [
        YearlyDepreciation(
            year=acquisition_date.year,
            months=12,
            opening_book_value=acquisition_cost,
            full_year_amount=acquisition_cost,
            depreciation_amount=acquisition_cost,
            business_amount=business_share(acquisition_cost, business_ratio),
            closing_book_value=0,
        )
    ]


def for_year(
    year: int,
    *,
    acquisition_cost: int,
    useful_life_years: int,
    acquisition_date: datetime.date,
    business_ratio: int,
    disposal_date: datetime.date | None = None,
    method: str = "straight_line",
) -> YearlyDepreciation | None:
    """指定年の明細だけ返す。その年が償却対象でなければ None。"""
    for entry in build_schedule(
        acquisition_cost=acquisition_cost,
        useful_life_years=useful_life_years,
        acquisition_date=acquisition_date,
        business_ratio=business_ratio,
        disposal_date=disposal_date,
        method=method,
    ):
        if entry.year == year:
            return entry
    return None


# ---- 内部ヘルパ -----------------------------------------------------------
def _ceil_div(numerator: int, denominator: int) -> int:
    """非負の整数同士の切り上げ除算。"""
    return -(-numerator // denominator)


def business_share(amount: int, ratio: int) -> int:
    """事業専用割合(%)を掛けた「事業分」を返す。円未満は四捨五入。

    減価償却費・経費の事業按分の両方で使う共通ルール。
    """
    return (amount * ratio + 50) // 100


def _months_in_service(
    year: int,
    acquisition_date: datetime.date,
    disposal_date: datetime.date | None,
) -> int:
    """その年に事業供用していた月数（1〜12、対象外は0）。"""
    if year < acquisition_date.year:
        return 0
    if disposal_date is not None and year > disposal_date.year:
        return 0

    start_month = acquisition_date.month if year == acquisition_date.year else 1
    if disposal_date is not None and year == disposal_date.year:
        end_month = disposal_date.month  # 除却月も含めて償却する
    else:
        end_month = 12
    return end_month - start_month + 1
