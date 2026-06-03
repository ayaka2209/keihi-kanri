"""
ORMモデル = Pythonのクラスがそのままテーブルになる。

設計上のポイント:
- 今は自分1人だが、最初から User テーブルと user_id を持たせている。
  こうしておけば、後で複数ユーザー化（Phase 3）してもテーブルを作り直さずに済む。
- Expense / Category は user_id で「誰のデータか」を区別する（マルチテナント設計）。
"""

import datetime

from sqlalchemy import (
    Integer,
    String,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
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


class Expense(Base):
    __tablename__ = "expenses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    date: Mapped[datetime.date] = mapped_column(Date, nullable=False, index=True)
    category: Mapped[str] = mapped_column(String(100), nullable=False)  # 勘定科目
    amount: Mapped[int] = mapped_column(Integer, nullable=False)        # 金額（円・税込）
    payee: Mapped[str] = mapped_column(String(200), default="")         # 支払先
    payment: Mapped[str] = mapped_column(String(50), default="")        # 支払方法
    memo: Mapped[str] = mapped_column(String(500), default="")          # 摘要
    receipt: Mapped[bool] = mapped_column(Boolean, default=False)       # 領収書有無
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    user: Mapped["User"] = relationship(back_populates="expenses")
