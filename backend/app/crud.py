"""
リポジトリ層 = DB操作だけを担当する場所。

API層(main.py)は「何をしたいか」だけを呼び出し、
「どうDBを触るか」はここに閉じ込める。
こうして層を分けると、テストや改修がラクになり、大規模化に耐える。

すべての関数が user_id を受け取り、その人のデータだけを対象にする
（マルチテナント）。今は user_id=1 固定だが、将来そのまま複数ユーザーに使える。
"""

import datetime
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from . import models, schemas

DEFAULT_CATEGORIES = [
    "租税公課", "荷造運賃", "水道光熱費", "旅費交通費", "通信費",
    "広告宣伝費", "接待交際費", "損害保険料", "修繕費", "消耗品費",
    "減価償却費", "福利厚生費", "外注工賃", "利子割引料", "地代家賃",
    "新聞図書費", "会議費", "支払手数料", "雑費",
]

PAYMENT_METHODS = ["現金", "クレジットカード", "口座振替", "銀行振込", "電子マネー", "その他"]


# ---- 初期データ -----------------------------------------------------------
def ensure_seed_data(db: Session) -> int:
    """デフォルトユーザーと初期勘定科目を用意し、ユーザーidを返す。"""
    user = db.scalar(select(models.User).limit(1))
    if user is None:
        user = models.User(name="default")
        db.add(user)
        db.flush()  # idを確定させる
        for i, name in enumerate(DEFAULT_CATEGORIES):
            db.add(models.Category(user_id=user.id, name=name, sort=i))
        db.commit()
    return user.id


# ---- 経費 -----------------------------------------------------------------
def list_expenses(
    db: Session,
    user_id: int,
    year: str | None = None,
    month: int | None = None,
    category: str | None = None,
    keyword: str | None = None,
) -> list[models.Expense]:
    stmt = select(models.Expense).where(models.Expense.user_id == user_id)
    if year:
        stmt = stmt.where(func.extract("year", models.Expense.date) == int(year))
    if month:
        stmt = stmt.where(func.extract("month", models.Expense.date) == int(month))
    if category:
        stmt = stmt.where(models.Expense.category == category)
    if keyword:
        like = f"%{keyword}%"
        stmt = stmt.where(
            models.Expense.payee.ilike(like) | models.Expense.memo.ilike(like)
        )
    stmt = stmt.order_by(models.Expense.date.desc(), models.Expense.id.desc())
    return list(db.scalars(stmt).all())


def create_expense(
    db: Session, user_id: int, data: schemas.ExpenseCreate
) -> models.Expense:
    obj = models.Expense(user_id=user_id, **data.model_dump())
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


def update_expense(
    db: Session, user_id: int, expense_id: int, data: schemas.ExpenseUpdate
) -> models.Expense | None:
    obj = db.scalar(
        select(models.Expense).where(
            models.Expense.id == expense_id, models.Expense.user_id == user_id
        )
    )
    if obj is None:
        return None
    for key, value in data.model_dump().items():
        setattr(obj, key, value)
    db.commit()
    db.refresh(obj)
    return obj


def delete_expense(db: Session, user_id: int, expense_id: int) -> bool:
    obj = db.scalar(
        select(models.Expense).where(
            models.Expense.id == expense_id, models.Expense.user_id == user_id
        )
    )
    if obj is None:
        return False
    db.delete(obj)
    db.commit()
    return True


# ---- 集計 -----------------------------------------------------------------
def get_summary(db: Session, user_id: int, year: str) -> schemas.Summary:
    y = int(year)
    base = (
        select(models.Expense)
        .where(models.Expense.user_id == user_id)
        .where(func.extract("year", models.Expense.date) == y)
    ).subquery()

    # 月別
    by_month = [schemas.MonthTotal(month=m, total=0) for m in range(1, 13)]
    rows = db.execute(
        select(
            func.extract("month", base.c.date).label("m"),
            func.sum(base.c.amount).label("total"),
        ).group_by("m")
    ).all()
    for r in rows:
        idx = int(r.m) - 1
        if 0 <= idx < 12:
            by_month[idx].total = int(r.total)

    # 科目別
    cat_rows = db.execute(
        select(
            base.c.category,
            func.sum(base.c.amount).label("total"),
            func.count().label("count"),
        )
        .group_by(base.c.category)
        .order_by(func.sum(base.c.amount).desc())
    ).all()
    by_category = [
        schemas.CategoryTotal(category=r.category, total=int(r.total), count=int(r.count))
        for r in cat_rows
    ]

    total = db.scalar(select(func.coalesce(func.sum(base.c.amount), 0))) or 0
    count = db.scalar(select(func.count()).select_from(base)) or 0

    return schemas.Summary(
        year=y, total=int(total), count=int(count),
        by_month=by_month, by_category=by_category,
    )


def get_years(db: Session, user_id: int) -> list[str]:
    rows = db.execute(
        select(func.distinct(func.extract("year", models.Expense.date)))
        .where(models.Expense.user_id == user_id)
        .order_by(func.extract("year", models.Expense.date).desc())
    ).all()
    years = [str(int(r[0])) for r in rows]
    this_year = str(datetime.date.today().year)
    if this_year not in years:
        years.insert(0, this_year)
    return years


# ---- 勘定科目 -------------------------------------------------------------
def list_categories(db: Session, user_id: int) -> list[str]:
    rows = db.scalars(
        select(models.Category)
        .where(models.Category.user_id == user_id)
        .order_by(models.Category.sort, models.Category.id)
    ).all()
    return [c.name for c in rows]


def add_category(db: Session, user_id: int, name: str) -> None:
    exists = db.scalar(
        select(models.Category).where(
            models.Category.user_id == user_id, models.Category.name == name
        )
    )
    if exists:
        return
    max_sort = db.scalar(
        select(func.coalesce(func.max(models.Category.sort), 0)).where(
            models.Category.user_id == user_id
        )
    )
    db.add(models.Category(user_id=user_id, name=name, sort=(max_sort or 0) + 1))
    db.commit()
