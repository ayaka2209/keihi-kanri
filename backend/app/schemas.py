"""
Pydanticスキーマ = APIの入口と出口の「型」。

FastAPIはこの型を使って、
  - リクエストの中身を自動でチェック（金額がマイナス、日付が変、など）
  - レスポンスを自動で整形
  - /docs にAPIドキュメントを自動生成
してくれる。これが生のHTTPサーバーとの大きな違い。
"""

import datetime

from pydantic import BaseModel, Field, ConfigDict


# ---- 経費 -----------------------------------------------------------------
class ExpenseBase(BaseModel):
    date: datetime.date
    category: str = Field(min_length=1, max_length=100)
    amount: int = Field(ge=0)  # 0以上（マイナスは弾く）
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


# ---- 勘定科目 -------------------------------------------------------------
class CategoryCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
