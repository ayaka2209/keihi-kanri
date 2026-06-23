"""収入 crud のテスト（func.extract に依存しない操作のみ検証）。"""

import datetime

from app import crud, models, schemas


def _make_user(db) -> models.User:
    user = models.User(name="test")
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def test_create_and_list_income(db):
    user = _make_user(db)
    data = schemas.IncomeCreate(
        date=datetime.date(2026, 5, 20),
        category="売上",
        amount=300000,
        payer="株式会社テスト",
        memo="5月分",
    )
    created = crud.create_income(db, user.id, data)
    assert created.id is not None
    assert created.user_id == user.id

    rows = crud.list_incomes(db, user.id)
    assert len(rows) == 1
    assert rows[0].category == "売上"
    assert rows[0].amount == 300000


def test_update_and_delete_income(db):
    user = _make_user(db)
    created = crud.create_income(
        db,
        user.id,
        schemas.IncomeCreate(date=datetime.date(2026, 5, 1), category="売上", amount=100000),
    )
    updated = crud.update_income(
        db,
        user.id,
        created.id,
        schemas.IncomeUpdate(date=datetime.date(2026, 5, 1), category="雑収入", amount=5000),
    )
    assert updated is not None
    assert updated.category == "雑収入"
    assert updated.amount == 5000

    assert crud.delete_income(db, user.id, created.id) is True
    assert crud.list_incomes(db, user.id) == []
    assert crud.delete_income(db, user.id, created.id) is False


def test_income_is_per_user(db):
    me = _make_user(db)
    other = _make_user(db)
    crud.create_income(
        db,
        other.id,
        schemas.IncomeCreate(date=datetime.date(2026, 5, 1), category="売上", amount=100000),
    )
    assert crud.list_incomes(db, me.id) == []
