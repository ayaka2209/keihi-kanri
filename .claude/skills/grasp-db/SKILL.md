---
name: grasp-db
description: DBスキーマ・モデル(User/Category/Expense)・マルチテナント設計・PostgreSQL/SQLite差・マイグレーション方針を扱う前に読む。データ構造を変える/クエリを書くとき必須。
---

# grasp-db — データベースの正典

対象: `backend/app/models.py`, `backend/app/database.py`, `backend/app/config.py`

## DB
- 本番/開発とも **PostgreSQL 16**（`docker compose up -d` で起動、ボリューム `pgdata`）。
- 接続は `config.py` の `DATABASE_URL`（`.env` から読む）。**`.env` は触らない・コミットしない**。
- テストだけ **SQLite in-memory**（[grasp-testing](../grasp-testing/SKILL.md)）。

## スキーマ（3テーブル）
- `users` … id / name / created_at
- `categories` … id / **user_id(FK)** / name / sort
- `expenses` … id / **user_id(FK)** / date / category(科目名) / amount(円・整数) / payee / payment / memo / receipt(bool) / created_at

## 設計の鉄則
- **マルチテナント先取り**: 単一ユーザー運用でも、すべてのデータは `user_id` を持つ。
  クエリには必ず `where(... .user_id == user_id)` を入れる（他人のデータを混ぜない）。
- `expenses.category` は科目名の文字列。`categories` テーブルとは FK で結ばず緩く連携している
  （現状仕様）。これを正規化したくなったら**必ずユーザーに相談**。
- 金額 `amount` は整数（円）。小数・通貨型にしない。

## PostgreSQL ⇄ SQLite の差（重要な落とし穴）
- 集計/フィルタで `func.extract("year"/"month", date)` を使っている（`crud.py`）。
  これは PostgreSQL 前提。**SQLite では EXTRACT が無く動かない**ため、
  テストでは extract 依存の関数（`get_summary` / 年月フィルタ）を避けるか、別途吸収する。

## マイグレーション（Alembic 導入済み）
- **Alembic でスキーマ管理する**。設定は `backend/alembic.ini` と `backend/alembic/`
  （`env.py` が `app.config.settings.database_url` と `app.database.Base.metadata` を流用）。
- アプリ起動時に `app/migrations.py` の `run_migrations()`（= `alembic upgrade head`）が
  自動実行され、未適用のマイグレーションを当てる（`main.py` の lifespan）。
  ※ 旧来の `Base.metadata.create_all()` は廃止。**テスト(conftest)だけは create_all のまま**
  （テストはマイグレーションを介さず models から直接スキーマを作る）。
- **スキーマを変える手順**（モデル編集後）:
  ```bash
  cd backend
  alembic revision --autogenerate -m "変更内容"   # versions/ に生成 → 必ず中身を確認
  alembic upgrade head                              # 適用（起動時にも自動適用される）
  ```
  自動生成ファイル `alembic/versions/*.py` は lint 対象外（`ruff` で extend-exclude 済み）。
- 既存DBを後から Alembic 管理下に置くときは `alembic stamp head`（作成済みを適用済み扱い）。
