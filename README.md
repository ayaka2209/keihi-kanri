# 経費管理アプリ（青色申告向け）

手書きの経費メモを卒業し、確定申告のときに「年間集計」と「CSV」をボタン一発で出せるローカルWebアプリです。
追加インストール不要で、Macに最初から入っている Python だけで動きます。

## 使い方

### 1. 起動する

ターミナルを開き、このフォルダで次のコマンドを実行します。

```bash
cd ~/keihi-kanri
python3 app.py
```

数秒でブラウザが自動的に開きます（開かない場合は手動で http://localhost:8765 へ）。
**終了するときはターミナルで `Ctrl + C`** を押します。

### 2. 経費を入力する

「経費を入力」タブで、日付・勘定科目・金額を入れて「登録する」。
金額を入れたあと続けて入力できるよう、日付と科目は残ります。

### 3. 一覧で確認・修正する

「一覧」タブで年・月・科目・キーワードで絞り込み。各行の「編集」「削除」で修正できます。

### 4. 確定申告のとき

「集計・確定申告」タブで年を選ぶと：

- **年間経費合計**
- **科目別集計**（確定申告書の経費欄にそのまま転記できます）
- **月別の推移グラフ**
- **CSVダウンロード**（Excel や会計ソフトに取り込み可能。文字化けしないUTF-8）

## データの保存場所

すべて同じフォルダの `keihi.db`（SQLite）に保存されます。
**バックアップはこの `keihi.db` ファイルをコピーするだけ**でOKです。

## 勘定科目について

青色申告決算書の標準的な経費科目を最初から登録済みです。
不足する科目は「集計・確定申告」タブの一番下から追加できます。

## v2（FastAPI + PostgreSQL）を Docker で起動する

上の手順は v1（`legacy/app.py`・SQLite・追加インストール不要）の使い方です。
開発対象の **v2** は FastAPI + PostgreSQL で動き、DB とアプリの両方をコンテナで起動します。

### 前提
- Docker エンジンが動いていること（`docker info` でエラーが出なければOK）。
  - macOS 14 Sonoma 以降: Docker Desktop。
  - macOS 13 Ventura など古いOS: Colima 等で docker エンジンを用意（`docker compose` はそのまま使える）。

### 起動・停止

```bash
docker compose up -d --build   # ビルドして起動（コードを変更したら毎回これ）
docker compose up -d           # コード未変更なら再ビルド不要
docker compose ps              # コンテナの状態を確認
docker compose logs app -f     # アプリのログを追う（Ctrl+C で離脱）
docker compose stop            # 止める（コンテナ・データは残る）
docker compose down            # コンテナを削除（データ pgdata は残る）
```

起動後、ブラウザで **http://localhost:8765** を開く（ポートは 8765 固定）。
API ドキュメントは http://localhost:8765/docs 。

### 注意
- データは名前付きボリューム `pgdata` に保存され、`down` してもデータは消えません。
  **`docker compose down -v` は実行しないこと**（`-v` を付けるとデータごと全消し）。
- `.env` は使わず、接続先（`DATABASE_URL`）は `docker-compose.yml` の `app` サービスに設定済み。

### Docker を使わずローカルで動かす場合
DB だけ Docker で起動し、アプリは Mac 上で直接動かすこともできます。

```bash
docker compose up -d db                                    # DBだけ起動
cd backend && uvicorn app.main:app --reload --port 8765    # アプリは直接起動
```

## 今後の拡張（メモ）

- レシート写真からのOCR自動入力
- 収入（売上）の管理と損益計算
- 会計ソフト（freee / 弥生）専用フォーマットでのエクスポート
