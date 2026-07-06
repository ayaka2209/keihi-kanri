"""
API層 = FastAPIアプリ本体。

役割は「リクエストを受けて、crud(リポジトリ層)を呼んで、結果を返す」だけ。
DBの細かい操作はここには書かない（層を分けるのが大規模化の作法）。

起動:
    cd backend
    uvicorn app.main:app --reload --port 8765

自動生成APIドキュメント:  http://localhost:8765/docs
画面（既存フロント）:      http://localhost:8765/
"""

import csv
import datetime
import io
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Response
from fastapi.staticfiles import StaticFiles
from sqlalchemy import select
from sqlalchemy.orm import Session

from . import crud, depreciation, models, schemas
from .database import get_db
from .migrations import run_migrations

# フロントエンド（静的ファイル）の場所： backend/app/ から見た ../../static
STATIC_DIR = Path(__file__).resolve().parent.parent.parent / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 起動時：未適用のマイグレーションを適用し（スキーマを最新化）、初期データを投入する。
    run_migrations()
    db = next(get_db())
    try:
        crud.ensure_seed_data(db)
    finally:
        db.close()
    yield


app = FastAPI(title="経費管理API", version="2.0", lifespan=lifespan)


def current_user_id(db: Session = Depends(get_db)) -> int:
    """今ログイン中のユーザーID。今は1人なので先頭ユーザーを返す。
    Phase 3 でここを「トークンから本人を特定する」処理に差し替える。"""
    uid = db.scalar(select(models.User.id).limit(1))
    if uid is None:
        raise HTTPException(500, "ユーザーが初期化されていません")
    return uid


# ---- メタ情報 -------------------------------------------------------------
@app.get("/api/meta")
def meta():
    return {
        "payments": crud.PAYMENT_METHODS,
        "income_categories": crud.INCOME_CATEGORIES,
        "today": datetime.date.today().isoformat(),
    }


# ---- 経費 -----------------------------------------------------------------
@app.get("/api/expenses", response_model=list[schemas.ExpenseOut])
def get_expenses(
    year: str | None = None,
    month: int | None = None,
    category: str | None = None,
    keyword: str | None = None,
    db: Session = Depends(get_db),
    uid: int = Depends(current_user_id),
):
    return crud.list_expenses(db, uid, year, month, category, keyword)


@app.post("/api/expenses", response_model=schemas.ExpenseOut)
def post_expense(
    data: schemas.ExpenseCreate,
    db: Session = Depends(get_db),
    uid: int = Depends(current_user_id),
):
    return crud.create_expense(db, uid, data)


@app.put("/api/expenses/{expense_id}", response_model=schemas.ExpenseOut)
def put_expense(
    expense_id: int,
    data: schemas.ExpenseUpdate,
    db: Session = Depends(get_db),
    uid: int = Depends(current_user_id),
):
    obj = crud.update_expense(db, uid, expense_id, data)
    if obj is None:
        raise HTTPException(404, "対象の経費が見つかりません")
    return obj


@app.delete("/api/expenses/{expense_id}")
def remove_expense(
    expense_id: int,
    db: Session = Depends(get_db),
    uid: int = Depends(current_user_id),
):
    if not crud.delete_expense(db, uid, expense_id):
        raise HTTPException(404, "対象の経費が見つかりません")
    return {"deleted": expense_id}


# ---- 集計 -----------------------------------------------------------------
@app.get("/api/summary", response_model=schemas.Summary)
def summary(
    year: str | None = None,
    db: Session = Depends(get_db),
    uid: int = Depends(current_user_id),
):
    year = year or str(datetime.date.today().year)
    return crud.get_summary(db, uid, year)


@app.get("/api/years")
def years(db: Session = Depends(get_db), uid: int = Depends(current_user_id)):
    return crud.get_years(db, uid)


# ---- 勘定科目 -------------------------------------------------------------
@app.get("/api/categories")
def categories(db: Session = Depends(get_db), uid: int = Depends(current_user_id)):
    return crud.list_categories(db, uid)


@app.post("/api/categories")
def post_category(
    data: schemas.CategoryCreate,
    db: Session = Depends(get_db),
    uid: int = Depends(current_user_id),
):
    crud.add_category(db, uid, data.name)
    return {"name": data.name}


# ---- 固定資産 -------------------------------------------------------------
@app.get("/api/assets", response_model=list[schemas.FixedAssetOut])
def get_assets(
    db: Session = Depends(get_db),
    uid: int = Depends(current_user_id),
):
    return crud.list_fixed_assets(db, uid)


@app.post("/api/assets", response_model=schemas.FixedAssetOut)
def post_asset(
    data: schemas.FixedAssetCreate,
    db: Session = Depends(get_db),
    uid: int = Depends(current_user_id),
):
    return crud.create_fixed_asset(db, uid, data)


@app.put("/api/assets/{asset_id}", response_model=schemas.FixedAssetOut)
def put_asset(
    asset_id: int,
    data: schemas.FixedAssetUpdate,
    db: Session = Depends(get_db),
    uid: int = Depends(current_user_id),
):
    obj = crud.update_fixed_asset(db, uid, asset_id, data)
    if obj is None:
        raise HTTPException(404, "対象の固定資産が見つかりません")
    return obj


@app.delete("/api/assets/{asset_id}")
def remove_asset(
    asset_id: int,
    db: Session = Depends(get_db),
    uid: int = Depends(current_user_id),
):
    if not crud.delete_fixed_asset(db, uid, asset_id):
        raise HTTPException(404, "対象の固定資産が見つかりません")
    return {"deleted": asset_id}


# ---- 減価償却（その年の明細） ---------------------------------------------
@app.get("/api/depreciation", response_model=schemas.DepreciationSummary)
def get_depreciation(
    year: str | None = None,
    db: Session = Depends(get_db),
    uid: int = Depends(current_user_id),
):
    y = int(year) if year else datetime.date.today().year
    return crud.get_depreciation_for_year(db, uid, y)


# ---- 固定資産の減価償却CSV（確定申告「減価償却費の計算」欄用） -----------
@app.get("/api/assets_export.csv")
def export_assets_csv(
    year: str | None = None,
    db: Session = Depends(get_db),
    uid: int = Depends(current_user_id),
):
    y = int(year) if year else datetime.date.today().year
    result = crud.get_depreciation_for_year(db, uid, y)
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(
        [
            "資産名",
            "取得年月日",
            "取得価額",
            "耐用年数",
            "償却率",
            "事業専用割合",
            "本年中の償却期間(月)",
            "期首帳簿価額",
            "本年分の償却費",
            "本年分の必要経費算入額",
            "期末帳簿価額",
        ]
    )
    for d in result.details:
        writer.writerow(
            [
                d.name,
                d.acquisition_date.isoformat(),
                d.acquisition_cost,
                d.useful_life_years,
                d.rate,
                f"{d.business_ratio}%",
                d.months,
                d.opening_book_value,
                d.depreciation_amount,
                d.business_amount,
                d.closing_book_value,
            ]
        )
    # Excelで文字化けしないようBOM付きUTF-8
    body = ("﻿" + buf.getvalue()).encode("utf-8")
    return Response(
        content=body,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="genka_shokyaku_{y}.csv"'},
    )


# ---- 収入 -----------------------------------------------------------------
@app.get("/api/incomes", response_model=list[schemas.IncomeOut])
def get_incomes(
    year: str | None = None,
    month: int | None = None,
    category: str | None = None,
    keyword: str | None = None,
    db: Session = Depends(get_db),
    uid: int = Depends(current_user_id),
):
    return crud.list_incomes(db, uid, year, month, category, keyword)


@app.post("/api/incomes", response_model=schemas.IncomeOut)
def post_income(
    data: schemas.IncomeCreate,
    db: Session = Depends(get_db),
    uid: int = Depends(current_user_id),
):
    return crud.create_income(db, uid, data)


@app.put("/api/incomes/{income_id}", response_model=schemas.IncomeOut)
def put_income(
    income_id: int,
    data: schemas.IncomeUpdate,
    db: Session = Depends(get_db),
    uid: int = Depends(current_user_id),
):
    obj = crud.update_income(db, uid, income_id, data)
    if obj is None:
        raise HTTPException(404, "対象の収入が見つかりません")
    return obj


@app.delete("/api/incomes/{income_id}")
def remove_income(
    income_id: int,
    db: Session = Depends(get_db),
    uid: int = Depends(current_user_id),
):
    if not crud.delete_income(db, uid, income_id):
        raise HTTPException(404, "対象の収入が見つかりません")
    return {"deleted": income_id}


@app.get("/api/incomes_export.csv")
def export_incomes_csv(
    year: str | None = None,
    db: Session = Depends(get_db),
    uid: int = Depends(current_user_id),
):
    year = year or str(datetime.date.today().year)
    rows = crud.list_incomes(db, uid, year=year)
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["日付", "収入科目", "金額", "源泉徴収税額", "差引入金額", "取引先", "摘要"])
    for r in sorted(rows, key=lambda x: x.date):
        writer.writerow(
            [
                r.date.isoformat(),
                r.category,
                r.amount,
                r.withholding,
                r.amount - r.withholding,  # 実際に振り込まれた額
                r.payer,
                r.memo,
            ]
        )
    # Excelで文字化けしないようBOM付きUTF-8
    body = ("﻿" + buf.getvalue()).encode("utf-8")
    return Response(
        content=body,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="shunyu_{year}.csv"'},
    )


# ---- CSV出力（確定申告用） ------------------------------------------------
@app.get("/api/export.csv")
def export_csv(
    year: str | None = None,
    db: Session = Depends(get_db),
    uid: int = Depends(current_user_id),
):
    year = year or str(datetime.date.today().year)
    rows = crud.list_expenses(db, uid, year=year)
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(
        ["日付", "勘定科目", "金額", "事業割合", "事業分", "支払先", "支払方法", "摘要", "領収書"]
    )
    for r in sorted(rows, key=lambda x: x.date):
        writer.writerow(
            [
                r.date.isoformat(),
                r.category,
                r.amount,
                f"{r.business_ratio}%",
                depreciation.business_share(r.amount, r.business_ratio),
                r.payee,
                r.payment,
                r.memo,
                "有" if r.receipt else "",
            ]
        )
    # Excelで文字化けしないようBOM付きUTF-8
    body = ("﻿" + buf.getvalue()).encode("utf-8")
    return Response(
        content=body,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="keihi_{year}.csv"'},
    )


# ---- 取引先（見積・請求の宛先マスタ） -------------------------------------
@app.get("/api/clients", response_model=list[schemas.ClientOut])
def get_clients(
    db: Session = Depends(get_db),
    uid: int = Depends(current_user_id),
):
    return crud.list_clients(db, uid)


@app.post("/api/clients", response_model=schemas.ClientOut)
def post_client(
    data: schemas.ClientCreate,
    db: Session = Depends(get_db),
    uid: int = Depends(current_user_id),
):
    return crud.create_client(db, uid, data)


@app.put("/api/clients/{client_id}", response_model=schemas.ClientOut)
def put_client(
    client_id: int,
    data: schemas.ClientUpdate,
    db: Session = Depends(get_db),
    uid: int = Depends(current_user_id),
):
    obj = crud.update_client(db, uid, client_id, data)
    if obj is None:
        raise HTTPException(404, "対象の取引先が見つかりません")
    return obj


@app.delete("/api/clients/{client_id}")
def remove_client(
    client_id: int,
    db: Session = Depends(get_db),
    uid: int = Depends(current_user_id),
):
    if not crud.delete_client(db, uid, client_id):
        raise HTTPException(404, "対象の取引先が見つかりません")
    return {"deleted": client_id}


# ---- 見積書 ---------------------------------------------------------------
@app.get("/api/quotes", response_model=list[schemas.QuoteOut])
def get_quotes(
    db: Session = Depends(get_db),
    uid: int = Depends(current_user_id),
):
    return crud.list_quotes(db, uid)


@app.get("/api/quotes/{quote_id}", response_model=schemas.QuoteOut)
def fetch_quote(
    quote_id: int,
    db: Session = Depends(get_db),
    uid: int = Depends(current_user_id),
):
    obj = crud.get_quote(db, uid, quote_id)
    if obj is None:
        raise HTTPException(404, "対象の見積書が見つかりません")
    return obj


@app.post("/api/quotes", response_model=schemas.QuoteOut)
def post_quote(
    data: schemas.QuoteCreate,
    db: Session = Depends(get_db),
    uid: int = Depends(current_user_id),
):
    return crud.create_quote(db, uid, data)


@app.put("/api/quotes/{quote_id}", response_model=schemas.QuoteOut)
def put_quote(
    quote_id: int,
    data: schemas.QuoteUpdate,
    db: Session = Depends(get_db),
    uid: int = Depends(current_user_id),
):
    obj = crud.update_quote(db, uid, quote_id, data)
    if obj is None:
        raise HTTPException(404, "対象の見積書が見つかりません")
    return obj


@app.delete("/api/quotes/{quote_id}")
def remove_quote(
    quote_id: int,
    db: Session = Depends(get_db),
    uid: int = Depends(current_user_id),
):
    if not crud.delete_quote(db, uid, quote_id):
        raise HTTPException(404, "対象の見積書が見つかりません")
    return {"deleted": quote_id}


# ---- 事業者設定（発行元情報・振込先） -------------------------------------
@app.get("/api/settings", response_model=schemas.SettingOut)
def get_settings(
    db: Session = Depends(get_db),
    uid: int = Depends(current_user_id),
):
    return crud.get_settings(db, uid)


@app.put("/api/settings", response_model=schemas.SettingOut)
def put_settings(
    data: schemas.SettingUpdate,
    db: Session = Depends(get_db),
    uid: int = Depends(current_user_id),
):
    return crud.update_settings(db, uid, data)


# ---- 請求書 ---------------------------------------------------------------
@app.get("/api/invoices", response_model=list[schemas.InvoiceOut])
def get_invoices(
    db: Session = Depends(get_db),
    uid: int = Depends(current_user_id),
):
    return crud.list_invoices(db, uid)


@app.get("/api/invoices/{invoice_id}", response_model=schemas.InvoiceOut)
def fetch_invoice(
    invoice_id: int,
    db: Session = Depends(get_db),
    uid: int = Depends(current_user_id),
):
    obj = crud.get_invoice(db, uid, invoice_id)
    if obj is None:
        raise HTTPException(404, "対象の請求書が見つかりません")
    return obj


@app.post("/api/invoices", response_model=schemas.InvoiceOut)
def post_invoice(
    data: schemas.InvoiceCreate,
    db: Session = Depends(get_db),
    uid: int = Depends(current_user_id),
):
    return crud.create_invoice(db, uid, data)


@app.post("/api/quotes/{quote_id}/invoice", response_model=schemas.InvoiceOut)
def convert_quote_to_invoice(
    quote_id: int,
    db: Session = Depends(get_db),
    uid: int = Depends(current_user_id),
):
    """見積を請求書に変換する（見積の内容を転記した請求書を新規作成）。"""
    obj = crud.create_invoice_from_quote(db, uid, quote_id)
    if obj is None:
        raise HTTPException(404, "変換元の見積書が見つかりません")
    return obj


@app.put("/api/invoices/{invoice_id}", response_model=schemas.InvoiceOut)
def put_invoice(
    invoice_id: int,
    data: schemas.InvoiceUpdate,
    db: Session = Depends(get_db),
    uid: int = Depends(current_user_id),
):
    obj = crud.update_invoice(db, uid, invoice_id, data)
    if obj is None:
        raise HTTPException(404, "対象の請求書が見つかりません")
    return obj


@app.delete("/api/invoices/{invoice_id}")
def remove_invoice(
    invoice_id: int,
    db: Session = Depends(get_db),
    uid: int = Depends(current_user_id),
):
    if not crud.delete_invoice(db, uid, invoice_id):
        raise HTTPException(404, "対象の請求書が見つかりません")
    return {"deleted": invoice_id}


# ---- フロントエンド（静的ファイル） ---------------------------------------
# 注意: API のルートをすべて定義した「後」にマウントすること。
# こうしないと "/" がすべてのリクエストを横取りしてしまう。
app.mount("/", StaticFiles(directory=str(STATIC_DIR), html=True), name="static")
