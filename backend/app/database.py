"""
データベース接続の土台（SQLAlchemy）。

- engine     : DBへの実際の接続プール
- SessionLocal: 1リクエストごとに使う「作業セッション」を作る工場
- Base       : 全ORMモデルの親クラス
- get_db     : FastAPIが各APIにセッションを渡すための仕組み（依存性注入）
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

from .config import settings

# pool_pre_ping=True : 切れたコネクションを自動で検知して張り直す（本番で重要）
engine = create_engine(settings.database_url, pool_pre_ping=True)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    """1リクエスト = 1セッション。終わったら必ず閉じる。"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
