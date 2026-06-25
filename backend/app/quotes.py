"""見積書の金額計算（純粋関数）。

DBにもPydanticにも依存しない「計算だけ」を閉じ込める場所。
depreciation.py と同じ思想で、テストしやすい純粋関数にしておく。

消費税は「シンプルな税込/税抜計算のみ」（インボイスの税率別集計はしない）。
- exclusive（税抜・外税）: 単価は税抜。小計に消費税を上乗せして合計を出す。
- inclusive（税込・内税）: 単価は税込。合計＝小計で、そこから内税を逆算する。
円未満は切り捨て（個人事業の慣行に合わせた既定。必要なら将来オプション化）。
"""

from typing import Literal

TaxMode = Literal["exclusive", "inclusive"]


def compute_totals(
    line_amounts: list[int],
    tax_mode: TaxMode,
    tax_rate: int,
) -> tuple[int, int, int]:
    """明細の金額リストから (税抜小計, 消費税, 合計) を返す。すべて整数（円）。

    line_amounts は各明細の「単価×数量」（税抜 or 税込は tax_mode に従う）。
    """
    gross = sum(line_amounts)
    if tax_mode == "inclusive":
        # 単価が税込 → 合計はそのまま。税抜＝合計×100/(100+税率)、内税＝差分。
        subtotal = gross * 100 // (100 + tax_rate)
        tax = gross - subtotal
        total = gross
    else:
        # 単価が税抜 → 小計に税を上乗せ。
        subtotal = gross
        tax = subtotal * tax_rate // 100
        total = subtotal + tax
    return subtotal, tax, total
