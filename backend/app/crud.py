"""
リポジトリ層 = DB操作だけを担当する場所。

API層(main.py)は「何をしたいか」だけを呼び出し、
「どうDBを触るか」はここに閉じ込める。
こうして層を分けると、テストや改修がラクになり、大規模化に耐える。

すべての関数が user_id を受け取り、その人のデータだけを対象にする
（マルチテナント）。今は user_id=1 固定だが、将来そのまま複数ユーザーに使える。
"""

import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from . import depreciation, models, schemas

DEFAULT_CATEGORIES = [
    "租税公課",
    "荷造運賃",
    "水道光熱費",
    "旅費交通費",
    "通信費",
    "広告宣伝費",
    "接待交際費",
    "損害保険料",
    "修繕費",
    "消耗品費",
    "減価償却費",
    "福利厚生費",
    "外注工賃",
    "利子割引料",
    "地代家賃",
    "新聞図書費",
    "会議費",
    "支払手数料",
    "雑費",
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
        stmt = stmt.where(models.Expense.payee.ilike(like) | models.Expense.memo.ilike(like))
    stmt = stmt.order_by(models.Expense.date.desc(), models.Expense.id.desc())
    return list(db.scalars(stmt).all())


def create_expense(db: Session, user_id: int, data: schemas.ExpenseCreate) -> models.Expense:
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
    # 事業按分を1件ずつ正しく丸めるため、その年の経費を取得して Python 側で集計する。
    # （金額そのものではなく「事業分 = 金額 × 事業按分率」を集計対象にする）
    expenses = db.scalars(
        select(models.Expense)
        .where(models.Expense.user_id == user_id)
        .where(func.extract("year", models.Expense.date) == y)
    ).all()

    by_month = [schemas.MonthTotal(month=m, total=0) for m in range(1, 13)]
    cat_acc: dict[str, list[int]] = {}  # category -> [事業分合計, 件数]
    total = 0
    count = 0
    for e in expenses:
        share = depreciation.business_share(e.amount, e.business_ratio)
        total += share
        count += 1
        by_month[e.date.month - 1].total += share
        acc = cat_acc.setdefault(e.category, [0, 0])
        acc[0] += share
        acc[1] += 1

    by_category = [
        schemas.CategoryTotal(category=c, total=v[0], count=v[1]) for c, v in cat_acc.items()
    ]
    by_category.sort(key=lambda c: c.total, reverse=True)

    # 固定資産の減価償却費（事業分）を「減価償却費」科目と合計に合算する。
    # 確定申告書の経費欄にそのまま転記できることが価値の中心なので、ここに正しく出す。
    # 月別推移(by_month)には載せない（償却は月次の現金支出ではないため）。
    dep = get_depreciation_for_year(db, user_id, y)
    dep_total = dep.total_business_amount
    if dep_total:
        total += dep_total
        for ct in by_category:
            if ct.category == "減価償却費":
                ct.total += dep_total
                ct.count += len(dep.details)
                break
        else:
            by_category.append(
                schemas.CategoryTotal(
                    category="減価償却費", total=dep_total, count=len(dep.details)
                )
            )
        by_category.sort(key=lambda c: c.total, reverse=True)

    return schemas.Summary(
        year=y,
        total=total,
        count=int(count),
        by_month=by_month,
        by_category=by_category,
        depreciation_total=dep_total,
    )


def asset_depreciation_years(assets: list[models.FixedAsset], current_year: int) -> set[int]:
    """固定資産が償却される年（取得〜償却完了、ただし当年まで）の集合。

    経費が無い過去年でも減価償却の明細を画面で遡れるようにするため、
    年プルダウンの候補に含める。DBに触らない純粋関数（テストしやすい）。
    """
    years: set[int] = set()
    for a in assets:
        for entry in depreciation.build_schedule(
            acquisition_cost=a.acquisition_cost,
            useful_life_years=a.useful_life_years,
            acquisition_date=a.acquisition_date,
            business_ratio=a.business_ratio,
            disposal_date=a.disposal_date,
            method=a.depreciation_method,
        ):
            if entry.year <= current_year:
                years.add(entry.year)
    return years


def get_years(db: Session, user_id: int) -> list[str]:
    rows = db.execute(
        select(func.distinct(func.extract("year", models.Expense.date))).where(
            models.Expense.user_id == user_id
        )
    ).all()
    years = {int(r[0]) for r in rows}
    current = datetime.date.today().year
    years.add(current)
    # 固定資産の償却年も候補に含める（経費が無い年でも償却を見られるように）
    years |= asset_depreciation_years(list_fixed_assets(db, user_id), current)
    return [str(y) for y in sorted(years, reverse=True)]


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


# ---- 固定資産 -------------------------------------------------------------
def list_fixed_assets(db: Session, user_id: int) -> list[models.FixedAsset]:
    stmt = (
        select(models.FixedAsset)
        .where(models.FixedAsset.user_id == user_id)
        .order_by(models.FixedAsset.acquisition_date.desc(), models.FixedAsset.id.desc())
    )
    return list(db.scalars(stmt).all())


def create_fixed_asset(
    db: Session, user_id: int, data: schemas.FixedAssetCreate
) -> models.FixedAsset:
    obj = models.FixedAsset(user_id=user_id, **data.model_dump())
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


def update_fixed_asset(
    db: Session, user_id: int, asset_id: int, data: schemas.FixedAssetUpdate
) -> models.FixedAsset | None:
    obj = db.scalar(
        select(models.FixedAsset).where(
            models.FixedAsset.id == asset_id, models.FixedAsset.user_id == user_id
        )
    )
    if obj is None:
        return None
    for key, value in data.model_dump().items():
        setattr(obj, key, value)
    db.commit()
    db.refresh(obj)
    return obj


def delete_fixed_asset(db: Session, user_id: int, asset_id: int) -> bool:
    obj = db.scalar(
        select(models.FixedAsset).where(
            models.FixedAsset.id == asset_id, models.FixedAsset.user_id == user_id
        )
    )
    if obj is None:
        return False
    db.delete(obj)
    db.commit()
    return True


# ---- 減価償却（その年の明細・合計） ---------------------------------------
def _display_rate(method: str, useful_life_years: int) -> float:
    """明細表示用の償却率。区分により意味が異なる。"""
    if method == "lump_sum_3y":
        return round(1 / 3, 3)  # 一括償却：3年均等 ≒ 0.333
    if method == "small_special":
        return 1.0  # 少額特例：全額
    return depreciation.annual_rate(useful_life_years)  # 定額法


def get_depreciation_for_year(db: Session, user_id: int, year: int) -> schemas.DepreciationSummary:
    """登録済みの固定資産から、その年の減価償却費（事業分）を計算して返す。

    償却費は保存せず取得情報からその都度計算する（depreciation.py）。
    func.extract は使わないので SQLite でもそのまま動く。
    """
    details: list[schemas.DepreciationDetail] = []
    total = 0
    for asset in list_fixed_assets(db, user_id):
        entry = depreciation.for_year(
            year,
            acquisition_cost=asset.acquisition_cost,
            useful_life_years=asset.useful_life_years,
            acquisition_date=asset.acquisition_date,
            business_ratio=asset.business_ratio,
            disposal_date=asset.disposal_date,
            method=asset.depreciation_method,
        )
        if entry is None:
            continue
        total += entry.business_amount
        details.append(
            schemas.DepreciationDetail(
                asset_id=asset.id,
                name=asset.name,
                method=asset.depreciation_method,
                acquisition_date=asset.acquisition_date,
                acquisition_cost=asset.acquisition_cost,
                useful_life_years=asset.useful_life_years,
                rate=_display_rate(asset.depreciation_method, asset.useful_life_years),
                business_ratio=asset.business_ratio,
                months=entry.months,
                opening_book_value=entry.opening_book_value,
                depreciation_amount=entry.depreciation_amount,
                business_amount=entry.business_amount,
                closing_book_value=entry.closing_book_value,
            )
        )
    return schemas.DepreciationSummary(year=year, total_business_amount=total, details=details)
