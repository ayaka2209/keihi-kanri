"""
ORMモデル = Pythonのクラスがそのままテーブルになる。

設計上のポイント:
- 今は自分1人だが、最初から User テーブルと user_id を持たせている。
  こうしておけば、後で複数ユーザー化（Phase 3）してもテーブルを作り直さずに済む。
- Expense / Category は user_id で「誰のデータか」を区別する（マルチテナント設計）。
"""

import datetime

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    expenses: Mapped[list["Expense"]] = relationship(back_populates="user")
    categories: Mapped[list["Category"]] = relationship(back_populates="user")


class Category(Base):
    __tablename__ = "categories"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    sort: Mapped[int] = mapped_column(Integer, default=0)

    user: Mapped["User"] = relationship(back_populates="categories")


class FixedAsset(Base):
    """固定資産（車・PC・建物など）。毎年の減価償却費は保存せず、
    取得情報からその都度計算する（→ app/depreciation.py）。"""

    __tablename__ = "fixed_assets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)  # 資産名
    acquisition_date: Mapped[datetime.date] = mapped_column(Date, nullable=False)  # 事業供用開始日
    acquisition_cost: Mapped[int] = mapped_column(Integer, nullable=False)  # 取得価額（円）
    useful_life_years: Mapped[int] = mapped_column(Integer, nullable=False)  # 耐用年数
    business_ratio: Mapped[int] = mapped_column(Integer, default=100)  # 事業按分率(0〜100)
    depreciation_method: Mapped[str] = mapped_column(
        String(30),
        default="straight_line",  # 現状は定額法のみ。将来 declining_balance 用
    )
    disposal_date: Mapped[datetime.date | None] = mapped_column(Date, nullable=True)  # 売却・除却日
    memo: Mapped[str] = mapped_column(String(500), default="")
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    user: Mapped["User"] = relationship()


class Client(Base):
    """取引先（見積・請求の宛先）マスタ。見積作成時に選んで宛名を流し込み、
    将来の請求書でも使い回す。"""

    __tablename__ = "clients"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)  # 取引先名
    honorific: Mapped[str] = mapped_column(String(20), default="御中")  # 様 / 御中
    address: Mapped[str] = mapped_column(String(300), default="")  # 住所
    contact: Mapped[str] = mapped_column(String(200), default="")  # 担当者・連絡先
    memo: Mapped[str] = mapped_column(String(500), default="")
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    user: Mapped["User"] = relationship()


class Quote(Base):
    """見積書（ヘッダ）。宛名は発行時点の値をスナップショットで持つ
    （後から取引先マスタを直しても、発行済み見積の宛名は変わらない）。"""

    __tablename__ = "quotes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    quote_no: Mapped[str] = mapped_column(String(30), nullable=False)  # 例 2026-001
    # 取引先マスタへの参照（任意）。マスタを消しても見積は残せるよう nullable。
    client_id: Mapped[int | None] = mapped_column(
        ForeignKey("clients.id"), nullable=True, index=True
    )
    client_name: Mapped[str] = mapped_column(String(200), nullable=False)  # 宛名(スナップショット)
    honorific: Mapped[str] = mapped_column(String(20), default="御中")
    subject: Mapped[str] = mapped_column(String(300), default="")  # 件名
    issue_date: Mapped[datetime.date] = mapped_column(Date, nullable=False, index=True)  # 発行日
    valid_until: Mapped[datetime.date | None] = mapped_column(Date, nullable=True)  # 有効期限
    # exclusive(税抜・外税) / inclusive(税込・内税)
    tax_mode: Mapped[str] = mapped_column(String(20), default="exclusive")
    tax_rate: Mapped[int] = mapped_column(Integer, default=10)  # 消費税率(%)
    notes: Mapped[str] = mapped_column(String(1000), default="")  # 備考
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    user: Mapped["User"] = relationship()
    # 見積を消したら明細も消える（delete-orphan）。並びは sort 順。
    items: Mapped[list["QuoteItem"]] = relationship(
        back_populates="quote",
        cascade="all, delete-orphan",
        order_by="QuoteItem.sort",
    )


class QuoteItem(Base):
    """見積明細。quotes にぶら下がる1行。金額(=単価×数量)は保存せず都度計算する。"""

    __tablename__ = "quote_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    quote_id: Mapped[int] = mapped_column(ForeignKey("quotes.id"), index=True)
    sort: Mapped[int] = mapped_column(Integer, default=0)  # 表示順
    name: Mapped[str] = mapped_column(String(200), nullable=False)  # 品名・項目
    quantity: Mapped[int] = mapped_column(Integer, default=1)  # 数量
    unit: Mapped[str] = mapped_column(String(50), default="")  # 単位(式・個・月 等)
    unit_price: Mapped[int] = mapped_column(Integer, default=0)  # 単価(円)

    quote: Mapped["Quote"] = relationship(back_populates="items")


class Expense(Base):
    __tablename__ = "expenses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    date: Mapped[datetime.date] = mapped_column(Date, nullable=False, index=True)
    category: Mapped[str] = mapped_column(String(100), nullable=False)  # 勘定科目
    amount: Mapped[int] = mapped_column(Integer, nullable=False)  # 金額（円・税込）
    # 事業按分率(0〜100%)。既存行のため server_default="100"。事業分=amount×割合
    business_ratio: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="100", default=100
    )
    payee: Mapped[str] = mapped_column(String(200), default="")  # 支払先
    payment: Mapped[str] = mapped_column(String(50), default="")  # 支払方法
    memo: Mapped[str] = mapped_column(String(500), default="")  # 摘要
    receipt: Mapped[bool] = mapped_column(Boolean, default=False)  # 領収書有無
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    user: Mapped["User"] = relationship(back_populates="expenses")


class Income(Base):
    """収入（売上・雑収入など）。経費(Expense)と対になる存在。
    損益 = 収入合計 − 経費合計 を出すために使う。"""

    __tablename__ = "incomes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    date: Mapped[datetime.date] = mapped_column(Date, nullable=False, index=True)
    category: Mapped[str] = mapped_column(String(100), nullable=False)  # 収入科目
    amount: Mapped[int] = mapped_column(Integer, nullable=False)  # 金額（円）
    payer: Mapped[str] = mapped_column(String(200), default="")  # 取引先（支払元）
    memo: Mapped[str] = mapped_column(String(500), default="")  # 摘要
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    user: Mapped["User"] = relationship()
