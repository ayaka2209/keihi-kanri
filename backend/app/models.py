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
