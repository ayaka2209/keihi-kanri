"""
Pydanticスキーマ = APIの入口と出口の「型」。

FastAPIはこの型を使って、
  - リクエストの中身を自動でチェック（金額がマイナス、日付が変、など）
  - レスポンスを自動で整形
  - /docs にAPIドキュメントを自動生成
してくれる。これが生のHTTPサーバーとの大きな違い。
"""

import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, computed_field, model_validator

from . import quotes

# 固定資産の償却区分
DepreciationMethod = Literal["straight_line", "lump_sum_3y", "small_special"]

# 消費税の扱い: exclusive(税抜・外税) / inclusive(税込・内税)
TaxMode = Literal["exclusive", "inclusive"]

# 請求書の入金ステータス: unpaid(未入金) / paid(入金済み)
InvoiceStatus = Literal["unpaid", "paid"]


# ---- 経費 -----------------------------------------------------------------
class ExpenseBase(BaseModel):
    date: datetime.date
    category: str = Field(min_length=1, max_length=100)
    amount: int = Field(ge=0)  # 0以上（マイナスは弾く）
    business_ratio: int = Field(default=100, ge=0, le=100)  # 事業按分率（%）
    payee: str = ""
    payment: str = ""
    memo: str = ""
    receipt: bool = False


class ExpenseCreate(ExpenseBase):
    """登録時に受け取る形（POST）。"""


class ExpenseUpdate(ExpenseBase):
    """更新時に受け取る形（PUT）。"""


class ExpenseOut(ExpenseBase):
    """APIが返す形（DBのidなどを含む）。"""

    id: int
    created_at: datetime.datetime

    # ORMオブジェクトからそのまま変換できるようにする
    model_config = ConfigDict(from_attributes=True)


# ---- 集計 -----------------------------------------------------------------
class MonthTotal(BaseModel):
    month: int
    total: int


class CategoryTotal(BaseModel):
    category: str
    total: int
    count: int


class Summary(BaseModel):
    year: int
    total: int
    count: int
    by_month: list[MonthTotal]
    by_category: list[CategoryTotal]
    # 減価償却費（事業分）の合計。total と by_category には含むが、by_month には
    # 含めない（償却は月次の現金支出ではないため）。UI の注記用。
    depreciation_total: int = 0
    # 損益: 収入合計と、収入−経費(total)の差引
    income_total: int = 0
    profit: int = 0
    # 源泉徴収税額の年間合計（前払いした所得税）。確定申告で差し引く額の目安。
    withholding_total: int = 0


# ---- 勘定科目 -------------------------------------------------------------
class CategoryCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)


# ---- 収入 -----------------------------------------------------------------
class IncomeBase(BaseModel):
    date: datetime.date
    category: str = Field(min_length=1, max_length=100)
    amount: int = Field(ge=0)  # 源泉徴収前の満額
    withholding: int = Field(default=0, ge=0)  # 源泉徴収税額（円）。無ければ0
    payer: str = ""  # 取引先（支払元）
    memo: str = ""

    @model_validator(mode="after")
    def _withholding_within_amount(self) -> "IncomeBase":
        # 源泉徴収税額が満額を超えるのは入力ミス。差引入金額が負になるのを防ぐ。
        if self.withholding > self.amount:
            raise ValueError("源泉徴収税額は金額（満額）を超えられません")
        return self


class IncomeCreate(IncomeBase):
    """登録時に受け取る形（POST）。"""


class IncomeUpdate(IncomeBase):
    """更新時に受け取る形（PUT）。"""


class IncomeOut(IncomeBase):
    id: int
    created_at: datetime.datetime

    model_config = ConfigDict(from_attributes=True)


# ---- 固定資産 -------------------------------------------------------------
class FixedAssetBase(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    acquisition_date: datetime.date  # 事業供用開始日
    acquisition_cost: int = Field(ge=1)  # 取得価額（円）
    useful_life_years: int = Field(ge=1, le=100)  # 耐用年数
    business_ratio: int = Field(default=100, ge=0, le=100)  # 事業按分率（%）
    # 償却区分: straight_line(定額法) / lump_sum_3y(一括償却) / small_special(少額特例)
    depreciation_method: DepreciationMethod = "straight_line"
    disposal_date: datetime.date | None = None  # 売却・除却日（任意）
    memo: str = ""

    @model_validator(mode="after")
    def _disposal_not_before_acquisition(self) -> "FixedAssetBase":
        # 除却日が取得日より前だと供用月数が0になり、償却が静かに0円になってしまう。
        if self.disposal_date is not None and self.disposal_date < self.acquisition_date:
            raise ValueError("disposal_date は acquisition_date 以降にしてください")
        return self


class FixedAssetCreate(FixedAssetBase):
    """登録時に受け取る形（POST）。"""


class FixedAssetUpdate(FixedAssetBase):
    """更新時に受け取る形（PUT）。"""


class FixedAssetOut(FixedAssetBase):
    """APIが返す形。"""

    id: int
    created_at: datetime.datetime

    model_config = ConfigDict(from_attributes=True)


# ---- 減価償却（その年の明細） ---------------------------------------------
class DepreciationDetail(BaseModel):
    """資産1件・その年の償却明細（申告書「減価償却費の計算」欄に対応）。"""

    asset_id: int
    name: str
    method: DepreciationMethod  # 償却区分
    acquisition_date: datetime.date
    acquisition_cost: int
    useful_life_years: int
    rate: float  # 償却率（定額法のみ意味を持つ。例 0.167）
    business_ratio: int
    months: int  # その年の供用月数
    opening_book_value: int  # 期首帳簿価額
    depreciation_amount: int  # 本年分の償却費（按分前）
    business_amount: int  # 事業分（必要経費算入額）
    closing_book_value: int  # 期末帳簿価額


class DepreciationSummary(BaseModel):
    year: int
    total_business_amount: int  # その年の減価償却費（事業分）合計
    details: list[DepreciationDetail]


# ---- 取引先（見積・請求の宛先マスタ） -------------------------------------
class ClientBase(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    honorific: str = Field(default="御中", max_length=20)  # 様 / 御中
    address: str = ""
    contact: str = ""
    memo: str = ""


class ClientCreate(ClientBase):
    """登録時に受け取る形（POST）。"""


class ClientUpdate(ClientBase):
    """更新時に受け取る形（PUT）。"""


class ClientOut(ClientBase):
    id: int
    created_at: datetime.datetime

    model_config = ConfigDict(from_attributes=True)


# ---- 見積書 ---------------------------------------------------------------
class QuoteItemIn(BaseModel):
    """見積明細の入力。"""

    name: str = Field(min_length=1, max_length=200)
    quantity: int = Field(default=1, ge=0)
    unit: str = Field(default="", max_length=50)
    unit_price: int = Field(default=0, ge=0)


class QuoteItemOut(BaseModel):
    id: int
    name: str
    quantity: int
    unit: str
    unit_price: int

    model_config = ConfigDict(from_attributes=True)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def amount(self) -> int:
        """金額 = 単価 × 数量（保存せず都度計算）。"""
        return self.unit_price * self.quantity


class QuoteBase(BaseModel):
    client_id: int | None = None
    client_name: str = Field(min_length=1, max_length=200)  # 宛名
    honorific: str = Field(default="御中", max_length=20)
    subject: str = Field(default="", max_length=300)  # 件名
    issue_date: datetime.date  # 発行日
    valid_until: datetime.date | None = None  # 有効期限
    tax_mode: TaxMode = "exclusive"
    tax_rate: int = Field(default=10, ge=0, le=100)
    notes: str = Field(default="", max_length=1000)


class QuoteCreate(QuoteBase):
    items: list[QuoteItemIn] = []


class QuoteUpdate(QuoteCreate):
    """更新時に受け取る形（PUT）。明細はまるごと入れ替える。"""


class QuoteOut(QuoteBase):
    id: int
    quote_no: str
    created_at: datetime.datetime
    items: list[QuoteItemOut]

    model_config = ConfigDict(from_attributes=True)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def subtotal(self) -> int:
        """税抜小計。"""
        return self._totals()[0]

    @computed_field  # type: ignore[prop-decorator]
    @property
    def tax(self) -> int:
        """消費税額。"""
        return self._totals()[1]

    @computed_field  # type: ignore[prop-decorator]
    @property
    def total(self) -> int:
        """合計（税込）。"""
        return self._totals()[2]

    def _totals(self) -> tuple[int, int, int]:
        line_amounts = [it.unit_price * it.quantity for it in self.items]
        return quotes.compute_totals(line_amounts, self.tax_mode, self.tax_rate)


# ---- 事業者設定（発行元情報・振込先） -------------------------------------
class SettingBase(BaseModel):
    business_name: str = Field(default="", max_length=200)  # 発行者名・屋号
    postal_code: str = Field(default="", max_length=20)
    address: str = Field(default="", max_length=300)
    tel: str = Field(default="", max_length=50)
    email: str = Field(default="", max_length=200)
    registration_no: str = Field(default="", max_length=20)  # インボイス登録番号(T+13桁)
    bank_info: str = Field(default="", max_length=500)  # 振込先（複数行可）


class SettingUpdate(SettingBase):
    """更新時に受け取る形（PUT）。"""


class SettingOut(SettingBase):
    id: int
    created_at: datetime.datetime

    model_config = ConfigDict(from_attributes=True)


# ---- 請求書 ---------------------------------------------------------------
class InvoiceItemIn(BaseModel):
    """請求明細の入力。"""

    name: str = Field(min_length=1, max_length=200)
    quantity: int = Field(default=1, ge=0)
    unit: str = Field(default="", max_length=50)
    unit_price: int = Field(default=0, ge=0)


class InvoiceItemOut(BaseModel):
    id: int
    name: str
    quantity: int
    unit: str
    unit_price: int

    model_config = ConfigDict(from_attributes=True)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def amount(self) -> int:
        """金額 = 単価 × 数量（保存せず都度計算）。"""
        return self.unit_price * self.quantity


class InvoiceBase(BaseModel):
    client_id: int | None = None
    client_name: str = Field(min_length=1, max_length=200)  # 宛名
    honorific: str = Field(default="御中", max_length=20)
    subject: str = Field(default="", max_length=300)  # 件名
    issue_date: datetime.date  # 発行日
    due_date: datetime.date | None = None  # 支払期限
    tax_mode: TaxMode = "exclusive"
    tax_rate: int = Field(default=10, ge=0, le=100)
    notes: str = Field(default="", max_length=1000)
    status: InvoiceStatus = "unpaid"  # 入金ステータス
    paid_date: datetime.date | None = None  # 入金日

    @model_validator(mode="after")
    def _paid_date_requires_paid(self) -> "InvoiceBase":
        # 入金日を入れたのに未入金のままは矛盾。入金日があれば入金済み扱いにする。
        if self.paid_date is not None:
            self.status = "paid"
        return self


class InvoiceCreate(InvoiceBase):
    quote_id: int | None = None  # 変換元の見積（任意）
    items: list[InvoiceItemIn] = []


class InvoiceUpdate(InvoiceCreate):
    """更新時に受け取る形（PUT）。明細はまるごと入れ替える。"""


class InvoiceOut(InvoiceBase):
    id: int
    invoice_no: str
    quote_id: int | None
    created_at: datetime.datetime
    items: list[InvoiceItemOut]

    model_config = ConfigDict(from_attributes=True)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def subtotal(self) -> int:
        """税抜小計。"""
        return self._totals()[0]

    @computed_field  # type: ignore[prop-decorator]
    @property
    def tax(self) -> int:
        """消費税額。"""
        return self._totals()[1]

    @computed_field  # type: ignore[prop-decorator]
    @property
    def total(self) -> int:
        """合計（税込）。"""
        return self._totals()[2]

    def _totals(self) -> tuple[int, int, int]:
        line_amounts = [it.unit_price * it.quantity for it in self.items]
        return quotes.compute_totals(line_amounts, self.tax_mode, self.tax_rate)
