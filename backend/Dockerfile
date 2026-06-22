# v2 アプリ（FastAPI）を焼き込む本番寄りイメージ。
#
# ビルドは「リポジトリ直下」を context にして行う（画面ファイル static/ も含めるため）:
#   docker compose up -d --build
#
# 構造のポイント:
#   アプリは backend/app から見て ../../static を配信するため、
#   イメージ内でも /app/backend と /app/static の位置関係を保つ。
FROM python:3.12-slim

# Python の出力をすぐログに流す（コンテナ運用の定番）
ENV PYTHONUNBUFFERED=1

WORKDIR /app/backend

# 依存だけ先にコピーして install する。
# こうするとコード変更時も「依存レイヤー」のキャッシュが効き、再ビルドが速い。
COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# アプリ本体と画面ファイルを焼き込む（自己完結＝どこでも同じものが動く）
COPY backend/ /app/backend/
COPY static/ /app/static/

EXPOSE 8765

# コンテナ内では 0.0.0.0 で待ち受ける（127.0.0.1 だと外から繋がらない）
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8765"]
