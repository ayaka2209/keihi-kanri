---
name: grasp-backend-architecture
description: APIエンドポイント追加・変更、crud(リポジトリ層)の修正、層の責務やDI、CSV出力を扱う前に読む。backend/app/ を触るとき必須。
---

# grasp-backend-architecture — バックエンドの正典

対象: `backend/app/main.py`, `crud.py`, `schemas.py`

## 層構造（越えない）
```
main.py    API層       ルーティング・HTTP・依存性注入のみ。SQLAlchemy を直接書かない。
crud.py    リポジトリ層  DB操作はすべてここ。引数で user_id を受け取り本人分だけ扱う。
schemas.py 型           Pydantic。入力検証(amount>=0 等)と出力整形。
models.py  ORM          → grasp-db
```
**鉄則: DBに触る処理は crud.py のみ。** main.py から `select(...)` を書き始めたら設計違反。

## API追加の手順
1. `schemas.py` に入出力モデルを定義（バリデーションをここに集約）。
2. `crud.py` に DB操作関数を追加（第1引数に `db`、続けて `user_id`）。
3. `main.py` にルートを追加し、crud を呼ぶだけにする。
4. **テストを先に書く**（[grasp-testing](../grasp-testing/SKILL.md)）→ 緑化。

## 既存の約束ごと
- 認証は暫定。`current_user_id()` が先頭ユーザーを返す（**Phase 3 でトークン化予定**）。
  新APIも必ず `uid: int = Depends(current_user_id)` を通す。
- 静的ファイルのマウント `app.mount("/", StaticFiles(...))` は**全APIルート定義の後**に置く
  （先に置くと "/" が全リクエストを横取りする）。新APIはこのマウント行より上に追加する。
- CSV出力は Excel 文字化け回避のため **BOM付きUTF-8**。この方式を踏襲する。
- エラーは `HTTPException(404, ...)` 等で返す。crud は「無ければ None/False」を返し、
  HTTP変換は main.py 側で行う（層の責務分離）。

## 起動・確認
- `cd backend && uvicorn app.main:app --reload --port 8765`
- API docs: `http://localhost:8765/docs` ／ 画面: `http://localhost:8765/`
- ポートは **8765 固定**。
