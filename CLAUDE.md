# CLAUDE.md — このプロジェクトの憲法

> このファイルと `.claude/skills/` は **唯一の正典** です。
> 記憶・推測・一般論で実装してはいけません。判断に迷ったら、必ずここと
> 関連 Skill を読み直してから手を動かすこと。書いていないことは勝手に決めず、
> ユーザーに確認すること。

---

## 1. プロダクト概要

- **何のシステムか**: 経費管理アプリ（青色申告向け）。経費の入力・一覧・年間集計・
  科目別集計・CSV出力（確定申告用）を行うローカルWebアプリ。
- **誰が使うか**: 青色申告をする個人事業主。**現在は単一ユーザー・ローカル運用**。
- **スコープ**: 経費の記録と確定申告のための集計まで。
  収入管理・レシートOCR・会計ソフト連携は将来の拡張（未着手）。

### 2系統が同居している（最重要）

| | v1（凍結） | v2（現役・開発対象） |
|---|---|---|
| 場所 | `legacy/app.py` | `backend/` |
| 実装 | Python標準ライブラリのみ | FastAPI + SQLAlchemy 2.0 |
| DB | SQLite (`keihi.db`) | PostgreSQL 16 (docker) |

- **新規開発・修正はすべて v2 (`backend/`) に対して行う。**
- `legacy/` は動く参照実装として**凍結**。ユーザーの明示的な指示なく変更しない。

---

## 2. 基本アーキテクチャ

### バックエンド（`backend/app/`）— 層を越えない
```
main.py      API層      ルーティングのみ。DB操作を書かない。
  ↓
crud.py      リポジトリ層  DB操作はすべてここに閉じ込める。
  ↓
models.py    ORM        User / Category / Expense（user_id でマルチテナント）
schemas.py   Pydantic   APIの入出力の型（バリデーション）
config.py / database.py  設定・接続
```
- **DBに触る処理は crud.py のみ**。main.py から直接 SQLAlchemy を叩かない。
- 詳細は [grasp-backend-architecture](.claude/skills/grasp-backend-architecture/SKILL.md) と
  [grasp-db](.claude/skills/grasp-db/SKILL.md)。

### フロントエンド（`static/`）
- バニラJS / HTML / CSS。**ビルドステップなし**。FastAPI の `StaticFiles` で配信。
- 詳細は [grasp-frontend-architecture](.claude/skills/grasp-frontend-architecture/SKILL.md)。

### DB
- 本番/開発とも PostgreSQL 16（`docker compose up -d`）。
- テストは SQLite in-memory（[grasp-testing](.claude/skills/grasp-testing/SKILL.md)）。

---

## 3. 固定ルール

- **ポートは 8765 固定**（API・画面とも）。
- DB接続は `.env`（`DATABASE_URL`）から読む。**`.env` はコミット禁止・直接編集禁止**。
  値を変えるときはユーザーに依頼する。
- PostgreSQL のデータは名前付きボリューム `pgdata` に保存。
  `docker compose down -v`（データ全消し）は実行しない。

---

## 4. Skills ファースト原則

**着手前に、関連する `grasp-*` Skill を必ず読む。** どれを読むかは各 Skill の
`description`（「いつ読むべきか」）で判断する。

| 触る対象 | 読む Skill |
|---|---|
| DBスキーマ・モデル・マイグレーション | `grasp-db` |
| API追加・crud変更・層の責務 | `grasp-backend-architecture` |
| static/ のJS/HTML/CSS・API契約 | `grasp-frontend-architecture` |
| 業務フロー・青色申告の科目 | `grasp-user-flow` |
| テストを書く/走らせる | `grasp-testing` |

---

## 5. 作業フロー

1. **要求を理解する** — 曖昧なら確認する。
2. **関連 Skill を読む**（Skills ファースト原則）。
3. **failing test を先に書く** — まず落ちるテストで「できていない」を示す。
4. **緑化する** — テストが通る最小実装を入れる。
5. **自動レビュー** — pytest が緑になると hook がコードレビューを促す（階層4）。
6. **lint / typecheck** — 下記の機械チェックを通す。

---

## 6. 実装後の機械チェック義務

コードを変更したら、コミット前に以下を**実行して緑を確認する**こと。

```bash
# テスト
cd backend && pytest

# lint / format（チェックのみ）
ruff check backend && ruff format --check backend

# 型チェック（任意・段階導入）
mypy backend/app
```

- FE（`static/`）のみの変更で backend に影響しない場合は pytest をスキップしてよい。
  その場合も「なぜスキップしたか」を一言述べること。
- 失敗したら、失敗内容を**そのまま報告**してから直す。緑だと偽らない。

---

## 7. コミット規約

- **コミットメッセージは日本語で書く**（要約・本文とも）。
- 末尾の `Co-Authored-By:` 行は英語のまま残す。
