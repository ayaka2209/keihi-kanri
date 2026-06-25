"""取引先(Client)と見積書(Quote)の crud テスト。

func.extract は使わないので SQLite in-memory でそのまま動く（grasp-testing）。
見積番号の採番・明細のぶら下げ・更新で明細を入れ替える挙動を検証する。
"""

import datetime

from app import crud, schemas


def _seed_user(db) -> int:
    return crud.ensure_seed_data(db)


# ---- 取引先マスタ ---------------------------------------------------------
def test_create_and_list_client(db):
    uid = _seed_user(db)
    obj = crud.create_client(
        db, uid, schemas.ClientCreate(name="株式会社サンプル", honorific="御中")
    )
    assert obj.id is not None
    clients = crud.list_clients(db, uid)
    assert [c.name for c in clients] == ["株式会社サンプル"]


def test_update_and_delete_client(db):
    uid = _seed_user(db)
    obj = crud.create_client(db, uid, schemas.ClientCreate(name="旧名"))
    updated = crud.update_client(db, uid, obj.id, schemas.ClientUpdate(name="新名"))
    assert updated is not None and updated.name == "新名"
    assert crud.delete_client(db, uid, obj.id) is True
    assert crud.list_clients(db, uid) == []


# ---- 見積書 ---------------------------------------------------------------
def _quote_payload(**over) -> schemas.QuoteCreate:
    base = dict(
        client_name="株式会社サンプル",
        honorific="御中",
        subject="Webサイト制作",
        issue_date=datetime.date(2026, 4, 1),
        valid_until=datetime.date(2026, 4, 30),
        tax_mode="exclusive",
        tax_rate=10,
        notes="",
        items=[
            schemas.QuoteItemIn(name="トップページ制作", quantity=1, unit="式", unit_price=200000),
            schemas.QuoteItemIn(name="下層ページ", quantity=5, unit="ページ", unit_price=30000),
        ],
    )
    base.update(over)
    return schemas.QuoteCreate(**base)


def test_create_quote_assigns_number_and_items(db):
    uid = _seed_user(db)
    q = crud.create_quote(db, uid, _quote_payload())
    # 見積番号は発行年＋連番で自動採番
    assert q.quote_no == "2026-001"
    assert len(q.items) == 2
    # 明細の並び順(sort)が保たれている
    assert [it.name for it in sorted(q.items, key=lambda x: x.sort)][0] == "トップページ制作"


def test_quote_number_increments_per_year(db):
    uid = _seed_user(db)
    crud.create_quote(db, uid, _quote_payload())
    q2 = crud.create_quote(db, uid, _quote_payload())
    assert q2.quote_no == "2026-002"
    # 別の年は連番がリセットされる
    q3 = crud.create_quote(db, uid, _quote_payload(issue_date=datetime.date(2027, 1, 5)))
    assert q3.quote_no == "2027-001"


def test_update_quote_replaces_items(db):
    uid = _seed_user(db)
    q = crud.create_quote(db, uid, _quote_payload())
    payload = _quote_payload(
        subject="改訂",
        items=[schemas.QuoteItemIn(name="保守", quantity=1, unit="月", unit_price=50000)],
    )
    updated = crud.update_quote(db, uid, q.id, payload)
    assert updated is not None
    assert updated.subject == "改訂"
    assert len(updated.items) == 1
    assert updated.items[0].name == "保守"
    # 番号は更新で変わらない
    assert updated.quote_no == "2026-001"


def test_delete_quote_cascades_items(db):
    uid = _seed_user(db)
    q = crud.create_quote(db, uid, _quote_payload())
    qid = q.id
    assert crud.delete_quote(db, uid, qid) is True
    assert crud.get_quote(db, uid, qid) is None


def test_quote_out_serializes_totals_from_orm(db):
    # ORM オブジェクトから QuoteOut へ変換し、明細金額と税計算が出ることを確認
    uid = _seed_user(db)
    q = crud.create_quote(db, uid, _quote_payload())
    out = schemas.QuoteOut.model_validate(q)
    # 200000×1 + 30000×5 = 350000、税10% = 35000、合計 385000
    assert out.subtotal == 350000
    assert out.tax == 35000
    assert out.total == 385000
    # 明細1行ごとの金額(単価×数量)も計算される
    amounts = {it.name: it.amount for it in out.items}
    assert amounts["下層ページ"] == 150000


def test_quote_is_scoped_to_user(db):
    uid = _seed_user(db)
    q = crud.create_quote(db, uid, _quote_payload())
    # 別ユーザーIDでは取得できない（マルチテナント）
    assert crud.get_quote(db, uid + 999, q.id) is None
    assert crud.delete_quote(db, uid + 999, q.id) is False
