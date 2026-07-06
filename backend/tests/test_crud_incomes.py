"""収入 crud のテスト（func.extract に依存しない操作のみ検証）。"""

import datetime

import pytest
from pydantic import ValidationError

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


def test_income_withholding_is_stored(db):
    """源泉徴収税額(withholding)を保存・更新できる。既定は0。"""
    user = _make_user(db)

    # 未指定なら0で保存される（後方互換）。
    plain = crud.create_income(
        db,
        user.id,
        schemas.IncomeCreate(date=datetime.date(2026, 1, 30), category="売上", amount=22000),
    )
    assert plain.withholding == 0

    # 源泉徴収ありで保存できる（22,000円のうち2,042円が源泉徴収）。
    gensen = crud.create_income(
        db,
        user.id,
        schemas.IncomeCreate(
            date=datetime.date(2026, 1, 30),
            category="売上",
            amount=22000,
            withholding=2042,
            payer="中央グループ",
            memo="中央グループHP制作代",
        ),
    )
    assert gensen.withholding == 2042

    # 更新でも書き換わる。
    updated = crud.update_income(
        db,
        user.id,
        gensen.id,
        schemas.IncomeUpdate(
            date=datetime.date(2026, 1, 30), category="売上", amount=22000, withholding=1000
        ),
    )
    assert updated is not None
    assert updated.withholding == 1000


def test_withholding_total_sums_business_year(db):
    """get_withholding_total はその年の源泉徴収税額の合計を返す。"""
    user = _make_user(db)
    crud.create_income(
        db,
        user.id,
        schemas.IncomeCreate(
            date=datetime.date(2026, 1, 30), category="売上", amount=22000, withholding=2042
        ),
    )
    crud.create_income(
        db,
        user.id,
        schemas.IncomeCreate(
            date=datetime.date(2026, 6, 10), category="売上", amount=110000, withholding=10210
        ),
    )
    # 源泉なしの1件は合計に影響しない。
    crud.create_income(
        db,
        user.id,
        schemas.IncomeCreate(date=datetime.date(2026, 7, 1), category="雑収入", amount=5000),
    )

    assert crud.get_withholding_total(db, user.id, 2026) == 2042 + 10210


def test_withholding_cannot_exceed_amount():
    """源泉徴収税額は金額(満額)を超えられない（入力ミス検知）。"""
    # 金額と等しいのは許容（全額源泉という理論上の端）。
    schemas.IncomeCreate(
        date=datetime.date(2026, 1, 30), category="売上", amount=22000, withholding=22000
    )
    # 金額を超える源泉はバリデーションで弾く。
    with pytest.raises(ValidationError):
        schemas.IncomeCreate(
            date=datetime.date(2026, 1, 30), category="売上", amount=22000, withholding=30000
        )
