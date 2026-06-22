"""アプリ起動時に Alembic マイグレーションを適用するためのヘルパ。

起動時に `alembic upgrade head` 相当を実行し、DBスキーマを最新へ揃える。
cwd に依存しないよう、alembic.ini と alembic/ は backend/ からの絶対パスで解決する。
"""

from pathlib import Path

from alembic import command
from alembic.config import Config

from .config import settings

# このファイル: backend/app/migrations.py → backend/ を基準にする
_BACKEND_DIR = Path(__file__).resolve().parent.parent
_ALEMBIC_INI = _BACKEND_DIR / "alembic.ini"
_ALEMBIC_DIR = _BACKEND_DIR / "alembic"


def _config() -> Config:
    cfg = Config(str(_ALEMBIC_INI))
    # cwd に関係なくスクリプト位置と接続先を確定させる
    cfg.set_main_option("script_location", str(_ALEMBIC_DIR))
    cfg.set_main_option("sqlalchemy.url", settings.database_url)
    return cfg


def run_migrations() -> None:
    """未適用のマイグレーションをすべて適用する（head まで）。"""
    command.upgrade(_config(), "head")
