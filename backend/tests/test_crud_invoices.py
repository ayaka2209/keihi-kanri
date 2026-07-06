"""請求書(Invoice)と事業者設定(Setting)の crud テスト。

見積書(Quote)と対になる存在。見積からの変換・請求書番号の採番(接頭辞 INV-)・
入金フラグ・明細のぶら下げ／入れ替え・マルチテナントのスコープを検証する。
func.extract は使わないので SQLite in-memory でそのまま動く（grasp-testing）。
"""

import datetime

from app import crud, schemas


def _seed_user(db) -> int:
    return crud.ensure_seed_data(db)


# ---- 事業者設定（振込先・発行元） -----------------------------------------
def test_get_settings_creates_default_row(db):
    uid = _seed_user(db)
    s = crud.get_settings(db, uid)
    # 未設定でも空の設定が1件用意される（毎回作らない＝upsert）
    assert s is not None
    assert s.business_name == ""
    # 2回呼んでも増えない（同じ行を返す）
    s2 = crud.get_settings(db, uid)
    assert s2.id == s.id


def test_update_settings_persists(db):
    uid = _seed_user(db)
    updated = crud.update_settings(
        db,
        uid,
        schemas.SettingUpdate(
            business_name="遠矢彩加",
            postal_code="899-4316",
            address="鹿児島県霧島市国分上小川781-4",
            tel="080-3370-2241",
            bank_info="○○銀行 △△支店 普通 1234567 トオヤ アヤカ",
            registration_no="T1234567890123",
        ),
    )
    assert updated.business_name == "遠矢彩加"
    assert updated.bank_info.startswith("○○銀行")
    # 取り直しても保持されている
    again = crud.get_settings(db, uid)
    assert again.registration_no == "T1234567890123"


def test_settings_scoped_to_user(db):
    uid = _seed_user(db)
    crud.update_settings(db, uid, schemas.SettingUpdate(business_name="本人"))
    # 別ユーザーは自分の空設定を得る（他人の設定が混ざらない）
    other = crud.get_settings(db, uid + 999)
    assert other.business_name == ""


# ---- 請求書 ---------------------------------------------------------------
def _invoice_payload(**over) -> schemas.InvoiceCreate:
    base = dict(
        client_name="株式会社中央グループ",
        honorific="御中",
        subject="画像使用料",
        issue_date=datetime.date(2026, 7, 6),
        due_date=datetime.date(2026, 7, 31),
        tax_mode="inclusive",
        tax_rate=10,
        notes="",
        items=[
            schemas.InvoiceItemIn(name="Lサイズ画像", quantity=6, unit="点", unit_price=3630),
            schemas.InvoiceItemIn(name="事務手数料", quantity=1, unit="式", unit_price=3000),
        ],
    )
    base.update(over)
    return schemas.InvoiceCreate(**base)


def test_create_invoice_assigns_prefixed_number_and_items(db):
    uid = _seed_user(db)
    inv = crud.create_invoice(db, uid, _invoice_payload())
    # 請求書番号は接頭辞 INV- ＋ 発行年 ＋ 連番で自動採番（見積と区別できる）
    assert inv.invoice_no == "INV-2026-001"
    assert len(inv.items) == 2
    assert inv.status == "unpaid"  # 既定は未入金


def test_invoice_number_increments_and_resets_per_year(db):
    uid = _seed_user(db)
    crud.create_invoice(db, uid, _invoice_payload())
    inv2 = crud.create_invoice(db, uid, _invoice_payload())
    assert inv2.invoice_no == "INV-2026-002"
    inv3 = crud.create_invoice(db, uid, _invoice_payload(issue_date=datetime.date(2027, 1, 5)))
    assert inv3.invoice_no == "INV-2027-001"


def test_invoice_and_quote_numbers_are_independent(db):
    uid = _seed_user(db)
    # 見積と請求は別系列で採番される（互いの連番に影響しない）
    crud.create_quote(
        db,
        uid,
        schemas.QuoteCreate(
            client_name="A社",
            issue_date=datetime.date(2026, 7, 1),
            items=[schemas.QuoteItemIn(name="x", quantity=1, unit_price=100)],
        ),
    )
    inv = crud.create_invoice(db, uid, _invoice_payload())
    assert inv.invoice_no == "INV-2026-001"


def test_invoice_out_serializes_totals_from_orm(db):
    uid = _seed_user(db)
    inv = crud.create_invoice(db, uid, _invoice_payload())
    out = schemas.InvoiceOut.model_validate(inv)
    # 税込: 3630×6 + 3000 = 24780。内税10% → 税抜=22527, 税=2253, 合計=24780
    assert out.total == 24780
    assert out.subtotal == 22527
    assert out.tax == 2253


def test_update_invoice_replaces_items_keeps_number(db):
    uid = _seed_user(db)
    inv = crud.create_invoice(db, uid, _invoice_payload())
    payload = _invoice_payload(
        subject="改訂",
        items=[schemas.InvoiceItemIn(name="Sサイズ画像", quantity=12, unit_price=550)],
    )
    updated = crud.update_invoice(db, uid, inv.id, payload)
    assert updated is not None
    assert updated.subject == "改訂"
    assert len(updated.items) == 1
    assert updated.invoice_no == "INV-2026-001"  # 番号は更新で変わらない


def test_mark_invoice_paid(db):
    uid = _seed_user(db)
    inv = crud.create_invoice(db, uid, _invoice_payload())
    updated = crud.update_invoice(
        db,
        uid,
        inv.id,
        _invoice_payload(status="paid", paid_date=datetime.date(2026, 7, 20)),
    )
    assert updated.status == "paid"
    assert updated.paid_date == datetime.date(2026, 7, 20)


def test_delete_invoice_cascades_items(db):
    uid = _seed_user(db)
    inv = crud.create_invoice(db, uid, _invoice_payload())
    iid = inv.id
    assert crud.delete_invoice(db, uid, iid) is True
    assert crud.get_invoice(db, uid, iid) is None


def test_invoice_is_scoped_to_user(db):
    uid = _seed_user(db)
    inv = crud.create_invoice(db, uid, _invoice_payload())
    assert crud.get_invoice(db, uid + 999, inv.id) is None
    assert crud.delete_invoice(db, uid + 999, inv.id) is False


# ---- 見積 → 請求書 への変換 -----------------------------------------------
def _quote_payload(**over) -> schemas.QuoteCreate:
    base = dict(
        client_name="株式会社中央グループ",
        honorific="御中",
        subject="画像使用料 御見積",
        issue_date=datetime.date(2026, 4, 15),
        tax_mode="inclusive",
        tax_rate=10,
        notes="ご査収ください",
        items=[
            schemas.QuoteItemIn(name="Lサイズ画像", quantity=6, unit="点", unit_price=3630),
            schemas.QuoteItemIn(name="Mサイズ画像", quantity=1, unit="点", unit_price=1980),
            schemas.QuoteItemIn(name="Sサイズ画像", quantity=12, unit="点", unit_price=550),
            schemas.QuoteItemIn(name="事務手数料", quantity=1, unit="式", unit_price=3000),
        ],
    )
    base.update(over)
    return schemas.QuoteCreate(**base)


def test_create_invoice_from_quote_copies_content(db):
    uid = _seed_user(db)
    client = crud.create_client(db, uid, schemas.ClientCreate(name="株式会社中央グループ"))
    quote = crud.create_quote(db, uid, _quote_payload(client_id=client.id))

    inv = crud.create_invoice_from_quote(db, uid, quote.id, issue_date=datetime.date(2026, 7, 6))
    assert inv is not None
    # 宛名・件名・税区分・明細が見積からそのまま転記される
    assert inv.client_name == "株式会社中央グループ"
    assert inv.client_id == client.id
    assert inv.tax_mode == "inclusive"
    assert [it.name for it in sorted(inv.items, key=lambda x: x.sort)] == [
        "Lサイズ画像",
        "Mサイズ画像",
        "Sサイズ画像",
        "事務手数料",
    ]
    # 変換元の見積を辿れる & 独自の請求書番号・発行日・未入金が付く
    assert inv.quote_id == quote.id
    assert inv.invoice_no == "INV-2026-001"
    assert inv.issue_date == datetime.date(2026, 7, 6)
    assert inv.status == "unpaid"
    # 合計は見積と一致（税込 3630×6+1980+550×12+3000 = 33360）
    out = schemas.InvoiceOut.model_validate(inv)
    assert out.total == 33360


def test_create_invoice_from_missing_quote_returns_none(db):
    uid = _seed_user(db)
    assert crud.create_invoice_from_quote(db, uid, 9999) is None


# ---- 参照整合性（取引先／見積を消しても請求書は残す） ---------------------
def test_delete_client_keeps_referencing_invoice(db):
    uid = _seed_user(db)
    client = crud.create_client(db, uid, schemas.ClientCreate(name="株式会社中央グループ"))
    inv = crud.create_invoice(db, uid, _invoice_payload(client_id=client.id))
    assert crud.delete_client(db, uid, client.id) is True
    kept = crud.get_invoice(db, uid, inv.id)
    assert kept is not None
    assert kept.client_id is None
    assert kept.client_name == "株式会社中央グループ"  # 宛名スナップショットは保持


def test_delete_quote_keeps_converted_invoice(db):
    uid = _seed_user(db)
    quote = crud.create_quote(db, uid, _quote_payload())
    inv = crud.create_invoice_from_quote(db, uid, quote.id, issue_date=datetime.date(2026, 7, 6))
    # 変換元の見積を消しても請求書は残り、quote_id だけ null になる
    assert crud.delete_quote(db, uid, quote.id) is True
    kept = crud.get_invoice(db, uid, inv.id)
    assert kept is not None
    assert kept.quote_id is None
