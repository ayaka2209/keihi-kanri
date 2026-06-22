"""Alembic 環境設定。

接続先(DATABASE_URL)とモデル定義はアプリ本体(app/)から流用する。
- 接続先: app.config.settings.database_url（.env / 環境変数から読む）
- 比較対象スキーマ: app.database.Base.metadata（全モデルを import して登録）
"""

from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool

from alembic import context
from app import models  # noqa: F401  Base にテーブルを登録するため必要

# アプリ本体の設定・モデルを読み込む（prepend_sys_path=. で backend/ が import パスに入る）
from app.config import settings
from app.database import Base

# Alembic Config（alembic.ini の値にアクセスできる）
config = context.config

# .ini のダミー値ではなく、アプリの設定から接続先を流し込む
config.set_main_option("sqlalchemy.url", settings.database_url)

# Python ロギング設定
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# autogenerate が比較する「あるべきスキーマ」
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """オフライン(URLのみ)モードでマイグレーションを実行する。"""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """オンライン(Engine接続)モードでマイグレーションを実行する。"""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
