---
name: grasp-testing
description: テストを書く/走らせる前に読む。pytest構成・SQLite in-memoryフィクスチャ・failing-test駆動の作法・PostgreSQL差の吸収・lint/typecheckコマンドを確認するとき必須。
---

# grasp-testing — テストの正典

## 何を使うか
- バックエンド: **pytest**（`backend/tests/`）。設定は `backend/pyproject.toml`。
- フロントエンド: 自動テスト基盤なし（バニラJS・ビルドなし）。手動/preview で確認。
- hook の純粋関数(`.claude/hooks/lib/`): **bats**（`brew install bats-core` が必要）。

## 実行コマンド（機械チェック義務 / CLAUDE.md §6）
```bash
cd backend && pytest                              # テスト
ruff check backend && ruff format --check backend # lint / format
mypy backend/app                                  # 型（任意・段階導入）
bats .claude/hooks/test/                           # hook純粋関数（bats導入時）
```
依存は `backend/requirements-dev.txt`（`pip install -r backend/requirements-dev.txt`）。

## failing-test 駆動（作業フロー §5）
1. まず**落ちるテスト**を書いて「未実装」を可視化する。
2. 通る最小実装を入れて緑化する。
3. pytest が緑になると hook がコードレビューを促す。

## テストの土台（重要）
- DBは **SQLite in-memory** を使う（PostgreSQL を立てずに高速・隔離）。
  `conftest.py` の `db` フィクスチャがセッションを供給し、毎テストでテーブルを作り直す。
- crud 層を直接呼んで検証するのが基本（API全体は FastAPI `TestClient` でも可）。

## PostgreSQL ⇄ SQLite 差の落とし穴（必読）
- `crud.get_summary` と年/月フィルタは `func.extract(...)` を使う＝**PostgreSQL専用**。
  **SQLite では動かない**。サンプルテストはこれらを避けている。
- extract 依存ロジックをテストしたいときは、(a) Postgres を立てて統合テストにする、
  (b) 日付の年月を別カラム/Python側で持つよう設計変更する、のどちらかをユーザーと相談。
  安易に「SQLiteで通った＝OK」としない。

## サンプル
- `backend/tests/test_crud_expenses.py` … 経費の作成→一覧取得、科目の追加→一覧。
  これを雛形に、新機能には対応するテストを必ず足す。
