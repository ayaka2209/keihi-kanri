#!/usr/bin/env python3
"""
経費管理アプリ（青色申告向け）

Python標準ライブラリのみで動作します。追加インストール不要。

起動方法:
    python3 app.py

その後、ブラウザで http://localhost:8765 を開いてください。
データは同じフォルダの keihi.db (SQLite) に保存されます。
"""

import json
import sqlite3
import csv
import io
import os
import datetime
import webbrowser
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "keihi.db")
STATIC_DIR = os.path.join(BASE_DIR, "static")
PORT = 8765

# 青色申告決算書の標準的な経費の勘定科目
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


# ---------------------------------------------------------------------------
# データベース
# ---------------------------------------------------------------------------
def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS expenses (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            date        TEXT    NOT NULL,            -- YYYY-MM-DD
            category    TEXT    NOT NULL,            -- 勘定科目
            amount      INTEGER NOT NULL,            -- 金額（円・税込）
            payee       TEXT    DEFAULT '',          -- 支払先
            payment     TEXT    DEFAULT '',          -- 支払方法
            memo        TEXT    DEFAULT '',          -- 摘要
            receipt     INTEGER DEFAULT 0,           -- 領収書有無 0/1
            created_at  TEXT    NOT NULL
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS categories (
            id    INTEGER PRIMARY KEY AUTOINCREMENT,
            name  TEXT UNIQUE NOT NULL,
            sort  INTEGER DEFAULT 0
        )
        """
    )
    # 勘定科目を初期投入（既に何かあればスキップ）
    cur.execute("SELECT COUNT(*) AS c FROM categories")
    if cur.fetchone()["c"] == 0:
        for i, name in enumerate(DEFAULT_CATEGORIES):
            cur.execute(
                "INSERT INTO categories (name, sort) VALUES (?, ?)", (name, i)
            )
    conn.commit()
    conn.close()


# ---------------------------------------------------------------------------
# APIロジック
# ---------------------------------------------------------------------------
def list_expenses(params):
    conn = get_conn()
    cur = conn.cursor()
    where = []
    args = []
    year = params.get("year", [None])[0]
    month = params.get("month", [None])[0]
    category = params.get("category", [None])[0]
    keyword = params.get("keyword", [None])[0]

    if year:
        where.append("substr(date,1,4) = ?")
        args.append(str(year))
    if month:
        where.append("substr(date,6,2) = ?")
        args.append(f"{int(month):02d}")
    if category:
        where.append("category = ?")
        args.append(category)
    if keyword:
        where.append("(payee LIKE ? OR memo LIKE ?)")
        args.extend([f"%{keyword}%", f"%{keyword}%"])

    sql = "SELECT * FROM expenses"
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY date DESC, id DESC"
    rows = [dict(r) for r in cur.execute(sql, args).fetchall()]
    conn.close()
    return rows


def create_expense(data):
    conn = get_conn()
    cur = conn.cursor()
    now = datetime.datetime.now().isoformat(timespec="seconds")
    cur.execute(
        """INSERT INTO expenses (date, category, amount, payee, payment, memo, receipt, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            data["date"],
            data["category"],
            int(data["amount"]),
            data.get("payee", ""),
            data.get("payment", ""),
            data.get("memo", ""),
            1 if data.get("receipt") else 0,
            now,
        ),
    )
    conn.commit()
    new_id = cur.lastrowid
    conn.close()
    return {"id": new_id}


def update_expense(expense_id, data):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """UPDATE expenses
           SET date=?, category=?, amount=?, payee=?, payment=?, memo=?, receipt=?
           WHERE id=?""",
        (
            data["date"],
            data["category"],
            int(data["amount"]),
            data.get("payee", ""),
            data.get("payment", ""),
            data.get("memo", ""),
            1 if data.get("receipt") else 0,
            expense_id,
        ),
    )
    conn.commit()
    conn.close()
    return {"id": expense_id}


def delete_expense(expense_id):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("DELETE FROM expenses WHERE id=?", (expense_id,))
    conn.commit()
    conn.close()
    return {"deleted": expense_id}


def get_summary(params):
    year = params.get("year", [str(datetime.date.today().year)])[0]
    conn = get_conn()
    cur = conn.cursor()

    by_month = [{"month": m, "total": 0} for m in range(1, 13)]
    rows = cur.execute(
        """SELECT substr(date,6,2) AS m, SUM(amount) AS total
           FROM expenses WHERE substr(date,1,4)=? GROUP BY m""",
        (str(year),),
    ).fetchall()
    for r in rows:
        idx = int(r["m"]) - 1
        if 0 <= idx < 12:
            by_month[idx]["total"] = r["total"]

    by_category = [
        {"category": r["category"], "total": r["total"], "count": r["count"]}
        for r in cur.execute(
            """SELECT category, SUM(amount) AS total, COUNT(*) AS count
               FROM expenses WHERE substr(date,1,4)=?
               GROUP BY category ORDER BY total DESC""",
            (str(year),),
        ).fetchall()
    ]

    total = cur.execute(
        "SELECT COALESCE(SUM(amount),0) AS t FROM expenses WHERE substr(date,1,4)=?",
        (str(year),),
    ).fetchone()["t"]

    count = cur.execute(
        "SELECT COUNT(*) AS c FROM expenses WHERE substr(date,1,4)=?",
        (str(year),),
    ).fetchone()["c"]

    conn.close()
    return {
        "year": int(year),
        "total": total,
        "count": count,
        "by_month": by_month,
        "by_category": by_category,
    }


def get_years():
    conn = get_conn()
    cur = conn.cursor()
    rows = cur.execute(
        "SELECT DISTINCT substr(date,1,4) AS y FROM expenses ORDER BY y DESC"
    ).fetchall()
    conn.close()
    years = [r["y"] for r in rows]
    this_year = str(datetime.date.today().year)
    if this_year not in years:
        years.insert(0, this_year)
    return years


def list_categories():
    conn = get_conn()
    cur = conn.cursor()
    rows = cur.execute(
        "SELECT name FROM categories ORDER BY sort, id"
    ).fetchall()
    conn.close()
    return [r["name"] for r in rows]


def add_category(name):
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            "INSERT INTO categories (name, sort) VALUES (?, (SELECT COALESCE(MAX(sort),0)+1 FROM categories))",
            (name,),
        )
        conn.commit()
    except sqlite3.IntegrityError:
        pass
    conn.close()
    return {"name": name}


def export_csv(params):
    """確定申告で使いやすい汎用CSV（Excel/会計ソフト取込用）。"""
    year = params.get("year", [str(datetime.date.today().year)])[0]
    rows = list_expenses({"year": [year]})
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["日付", "勘定科目", "金額", "支払先", "支払方法", "摘要", "領収書"])
    for r in sorted(rows, key=lambda x: x["date"]):
        writer.writerow(
            [
                r["date"],
                r["category"],
                r["amount"],
                r["payee"],
                r["payment"],
                r["memo"],
                "有" if r["receipt"] else "",
            ]
        )
    # Excelで文字化けしないようBOM付きUTF-8
    return ("﻿" + buf.getvalue()).encode("utf-8")


# ---------------------------------------------------------------------------
# HTTPハンドラ
# ---------------------------------------------------------------------------
class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass  # アクセスログは抑制

    def _send_json(self, obj, status=200):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_body(self):
        length = int(self.headers.get("Content-Length", 0))
        if length == 0:
            return {}
        raw = self.rfile.read(length)
        return json.loads(raw.decode("utf-8"))

    def _serve_static(self, path):
        if path == "/" or path == "":
            path = "/index.html"
        filepath = os.path.normpath(os.path.join(STATIC_DIR, path.lstrip("/")))
        if not filepath.startswith(STATIC_DIR) or not os.path.isfile(filepath):
            self.send_error(404, "Not Found")
            return
        ctype = {
            ".html": "text/html; charset=utf-8",
            ".js": "application/javascript; charset=utf-8",
            ".css": "text/css; charset=utf-8",
        }.get(os.path.splitext(filepath)[1], "application/octet-stream")
        with open(filepath, "rb") as f:
            body = f.read()
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    # -- GET ---------------------------------------------------------------
    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        params = parse_qs(parsed.query)
        try:
            if path == "/api/expenses":
                self._send_json(list_expenses(params))
            elif path == "/api/summary":
                self._send_json(get_summary(params))
            elif path == "/api/categories":
                self._send_json(list_categories())
            elif path == "/api/years":
                self._send_json(get_years())
            elif path == "/api/meta":
                self._send_json(
                    {"payments": PAYMENT_METHODS, "today": datetime.date.today().isoformat()}
                )
            elif path == "/api/export.csv":
                body = export_csv(params)
                year = params.get("year", ["all"])[0]
                self.send_response(200)
                self.send_header("Content-Type", "text/csv; charset=utf-8")
                self.send_header(
                    "Content-Disposition",
                    f'attachment; filename="keihi_{year}.csv"',
                )
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            else:
                self._serve_static(path)
        except Exception as e:
            self._send_json({"error": str(e)}, status=500)

    # -- POST --------------------------------------------------------------
    def do_POST(self):
        path = urlparse(self.path).path
        try:
            if path == "/api/expenses":
                self._send_json(create_expense(self._read_body()))
            elif path == "/api/categories":
                self._send_json(add_category(self._read_body()["name"]))
            else:
                self.send_error(404)
        except Exception as e:
            self._send_json({"error": str(e)}, status=500)

    # -- PUT ---------------------------------------------------------------
    def do_PUT(self):
        path = urlparse(self.path).path
        try:
            if path.startswith("/api/expenses/"):
                eid = int(path.rsplit("/", 1)[1])
                self._send_json(update_expense(eid, self._read_body()))
            else:
                self.send_error(404)
        except Exception as e:
            self._send_json({"error": str(e)}, status=500)

    # -- DELETE ------------------------------------------------------------
    def do_DELETE(self):
        path = urlparse(self.path).path
        try:
            if path.startswith("/api/expenses/"):
                eid = int(path.rsplit("/", 1)[1])
                self._send_json(delete_expense(eid))
            else:
                self.send_error(404)
        except Exception as e:
            self._send_json({"error": str(e)}, status=500)


def main():
    init_db()
    server = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    url = f"http://localhost:{PORT}"
    print("=" * 50)
    print("  経費管理アプリを起動しました")
    print(f"  ブラウザで開く: {url}")
    print("  終了するには Ctrl+C を押してください")
    print("=" * 50)
    # 1秒後にブラウザを自動で開く
    threading.Timer(1.0, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n終了しました。")
        server.shutdown()


if __name__ == "__main__":
    main()
