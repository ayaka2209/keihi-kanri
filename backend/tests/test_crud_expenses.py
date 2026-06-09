"""
crud 層のサンプルテスト（雛形）。

PostgreSQL 専用の func.extract に依存しない操作だけを検証している
（作成→一覧、科目の追加→一覧）。年月集計のテストは grasp-testing の方針に従うこと。
"""

import datetime

from app import crud, models, schemas


def _make_user(db) -> models.User:
    user = models.User(name="test")
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def test_create_and_list_expense(db):
    user = _make_user(db)
    data = schemas.ExpenseCreate(
        date=datetime.date(2026, 6, 9),
        category="消耗品費",
        amount=1200,
        payee="テスト商店",
        payment="現金",
        memo="動作確認",
        receipt=True,
    )

    created = crud.create_expense(db, user.id, data)
    assert created.id is not None

    rows = crud.list_expenses(db, user.id)
    assert len(rows) == 1
    assert rows[0].category == "消耗品費"
    assert rows[0].amount == 1200
    assert rows[0].user_id == user.id


def test_add_and_list_categories(db):
    user = _make_user(db)

    crud.add_category(db, user.id, "新聞図書費")
    names = crud.list_categories(db, user.id)
    assert "新聞図書費" in names

    # 重複追加しても増えない
    before = len(names)
    crud.add_category(db, user.id, "新聞図書費")
    assert len(crud.list_categories(db, user.id)) == before
