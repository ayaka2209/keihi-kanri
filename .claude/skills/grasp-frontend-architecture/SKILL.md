---
name: grasp-frontend-architecture
description: 画面(static/ の HTML/CSS/バニラJS)を変更する、APIとの契約(fetch)を扱う前に読む。ビルドの有無・タブ構成・API呼び出し規約を確認するとき必須。
---

# grasp-frontend-architecture — フロントエンドの正典

対象: `static/index.html`, `static/app.js`, `static/style.css`

## 大前提
- **バニラ JS / HTML / CSS。ビルドステップは無い**（npm も bundler も無い）。
  TypeScript・フレームワーク・パッケージを勝手に導入しない。必要ならユーザーに相談。
- FastAPI の `StaticFiles` で配信される（`backend` から見て `../../static`）。
- `app.js` は `"use strict";` のプレーンスクリプト。モジュール分割していない。

## 構成
- 画面は3タブ: **経費を入力 / 一覧 / 集計・確定申告**。
- 共通ヘルパ: `$`/`$$`(セレクタ)、`api(path, opts)`(fetchラッパ)、`yen(n)`(円表示)。
- グローバル状態: `META`(支払方法・今日) と `CATEGORIES`(科目一覧)。起動時に `/api/meta`
  `/api/categories` から取得して保持する。

## API契約（バックエンドと必ず揃える）
- すべて `/api/*`。JSON でやり取り。`api()` は `res.ok` でなければ throw する。
- 主なエンドポイント: `/api/meta` `/api/expenses`(GET/POST/PUT/DELETE) `/api/summary`
  `/api/years` `/api/categories`(GET/POST) `/api/export.csv`。
- **FEを変えてAPIの形が変わるなら、backend(schemas/main)も同時に直す**。
  契約を片側だけ変えない。変更時は [grasp-backend-architecture](../grasp-backend-architecture/SKILL.md) も読む。

## テスト/レビューの扱い
- FEには自動テスト基盤が無い。**FEのみの変更なら pytest はスキップ可**（理由を一言述べる）。
- 動作確認は `uvicorn` 起動 → `curl http://localhost:8765/...` か preview ツールで行う。
