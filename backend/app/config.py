"""
設定の一元管理。

環境変数（または .env ファイル）から値を読み込みます。
パスワードや接続先をコードに直書きしないのが「でかいシステム」の基本作法です。
本番環境では .env を使わず、サーバーの環境変数で上書きできます。
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # DBへの接続文字列。.env から読み込まれる。
    database_url: str = "postgresql+psycopg2://keihi:keihi_dev_password@localhost:5432/keihi"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


# アプリ全体で使い回す設定インスタンス
settings = Settings()
