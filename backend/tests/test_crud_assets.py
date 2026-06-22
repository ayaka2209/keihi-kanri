"""
固定資産 crud と「その年の減価償却費」集計のテスト。

func.extract に依存しない操作だけを検証する（資産は user_id でのフィルタのみ、
償却額は Python 側の純粋計算なので SQLite でそのまま動く）。
"""

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


def _asset_data(**over) -> schemas.FixedAssetCreate:
    base = dict(
        name="業務用車両",
        acquisition_date=datetime.date(2024, 1, 1),
        acquisition_cost=2_400_000,
        useful_life_years=6,
        business_ratio=100,
        memo="",
    )
    base.update(over)
    return schemas.FixedAssetCreate(**base)


def test_create_and_list_asset(db):
    user = _make_user(db)
    created = crud.create_fixed_asset(db, user.id, _asset_data())
    assert created.id is not None
    assert created.user_id == user.id

    rows = crud.list_fixed_assets(db, user.id)
    assert len(rows) == 1
    assert rows[0].name == "業務用車両"


def test_update_and_delete_asset(db):
    user = _make_user(db)
    created = crud.create_fixed_asset(db, user.id, _asset_data())

    updated = crud.update_fixed_asset(
        db, user.id, created.id, _asset_data(name="軽トラ", business_ratio=80)
    )
    assert updated is not None
    assert updated.name == "軽トラ"
    assert updated.business_ratio == 80

    assert crud.delete_fixed_asset(db, user.id, created.id) is True
    assert crud.list_fixed_assets(db, user.id) == []
    # 既に無いものは False
    assert crud.delete_fixed_asset(db, user.id, created.id) is False


def test_get_depreciation_for_year(db):
    user = _make_user(db)
    crud.create_fixed_asset(db, user.id, _asset_data())  # 2,400,000 / 6年 / 100%

    result = crud.get_depreciation_for_year(db, user.id, 2024)
    assert result.year == 2024
    assert result.total_business_amount == 400_800
    assert len(result.details) == 1
    assert result.details[0].business_amount == 400_800

    # 取得前の年は0件
    before = crud.get_depreciation_for_year(db, user.id, 2023)
    assert before.total_business_amount == 0
    assert before.details == []


def test_disposal_before_acquisition_is_rejected():
    """除却日が取得日より前なら弾く（償却が静かに0になるのを防ぐ）。"""
    with pytest.raises(ValidationError):
        _asset_data(
            acquisition_date=datetime.date(2024, 8, 1),
            disposal_date=datetime.date(2024, 7, 1),
        )
    # 同日はOK（取得即日除却もあり得る）
    _asset_data(
        acquisition_date=datetime.date(2024, 8, 1),
        disposal_date=datetime.date(2024, 8, 1),
    )


def test_depreciation_is_per_user(db):
    """他人の資産が混ざらない（マルチテナント）。"""
    me = _make_user(db)
    other = _make_user(db)
    crud.create_fixed_asset(db, other.id, _asset_data())

    result = crud.get_depreciation_for_year(db, me.id, 2024)
    assert result.total_business_amount == 0
    assert result.details == []
