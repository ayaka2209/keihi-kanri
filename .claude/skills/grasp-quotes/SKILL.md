---
name: grasp-quotes
description: 見積書・取引先マスタ・消費税(税抜/税込)計算・見積番号採番・ブラウザ印刷(PDF)を扱う前に読む。Quote/Client/QuoteItem を触る/見積の金額計算や印刷を変えるとき必須。
---

# grasp-quotes — 見積書モジュールの正典

対象: `backend/app/quotes.py`, `models.py`(Client/Quote/QuoteItem),
`schemas.py`(Quote*/Client*), `crud.py`(見積・取引先), `static/`(見積書タブ)

## これは何か
青色申告の集計とは独立した**受注業務の機能**。取引先に渡す見積書を作り、
ブラウザの印刷（「PDFとして保存」）で送付用PDFにする。将来の請求書・入金管理の土台。

## データ構造（3テーブル・すべて user_id 持ち＝マルチテナント）
- `clients` … 取引先マスタ（name / honorific(様·御中) / address / contact / memo）。
  見積作成時に選ぶと宛名を流し込める。**任意**（直接入力も可）。
- `quotes` … 見積ヘッダ。**宛名は発行時点のスナップショット**（`client_name`/`honorific`）。
  `client_id` は参照（nullable）。マスタを後から直しても発行済み見積の宛名は変えない。
- `quote_items` … 明細。`quotes` に `cascade="all, delete-orphan"` でぶら下がる。
  金額は保存せず `単価×数量` を都度計算する。

## 金額計算（`quotes.compute_totals` 純粋関数に集約）
- **シンプルな税込/税抜のみ**（インボイスの税率別集計はしない）。
  - `exclusive`(税抜・外税): 小計に消費税を上乗せ。`税=小計×税率//100`、`合計=小計+税`。
  - `inclusive`(税込・内税): 合計=小計。`税抜=合計×100//(100+税率)`、`税=合計-税抜`。
- **円未満は切り捨て**（`//`）。金額は整数（円）。経費側と同じ「小数を持たない」鉄則。
- FE(`static/app.js` の `quoteTotals`)はこの関数と**必ず同じ式**にする（プレビュー用の二重実装）。
  片方だけ変えない。
- `QuoteOut` は `subtotal`/`tax`/`total`/明細`amount` を **`@computed_field`** で返す
  （DBに保存しない）。ORM から `model_validate` で変換される。

## 見積番号の採番（`crud._next_quote_no`）
- 形式 `YYYY-連番3桁`（例 `2026-001`）。発行年ごとに連番、年が変わるとリセット。
- `func.extract` を使わず **`quote_no LIKE 'YYYY-%'`** で当年分を絞る（SQLite でも動く）。
- 採番は作成時のみ。**更新(PUT)では quote_no を変えない**。

## API（main.py、static マウントより上に置く）
- `/api/clients`(GET/POST), `/api/clients/{id}`(PUT/DELETE)
- `/api/quotes`(GET/POST), `/api/quotes/{id}`(GET/PUT/DELETE)
- 全ルートで `uid: int = Depends(current_user_id)` を通す。crud は無ければ None/False を返し、
  HTTP 404 変換は main.py 側で行う（層の責務分離）。

## 印刷（PDFはブラウザ任せ＝サーバ依存ゼロ）
- 「印刷」で `#print-area` に見積書HTMLを組み立て、`body.printing` を付けて `window.print()`。
- `@media print` で `header`/`main` を隠し `#print-area` だけ出す（`static/style.css`）。
- `afterprint` で元に戻す。**PDF生成ライブラリは入れない**（最小依存の方針）。

## テスト
- 純粋計算: `tests/test_quotes_calc.py`（DB非依存）。
- CRUD/採番/明細入れ替え/スコープ: `tests/test_crud_quotes.py`（SQLite in-memory）。
- いずれも `func.extract` を踏まないので SQLite でそのまま緑（[grasp-testing](../grasp-testing/SKILL.md)）。
