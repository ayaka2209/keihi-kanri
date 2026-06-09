"""
pytest 共通フィクスチャ。

DB は SQLite in-memory を使う（PostgreSQL を立てずに高速・隔離してテストする）。
各テストごとにテーブルを作り直し、終わったら破棄する。

注意: crud.get_summary や年/月フィルタは PostgreSQL 専用の func.extract を使うため
SQLite では動かない。これらに依存するテストは書かない（grasp-testing 参照）。
"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app import models  # noqa: F401  Base にテーブルを登録するためインポートする


@pytest.fixture
def db():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine)
    TestingSession = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    session = TestingSession()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(engine)
        engine.dispose()
