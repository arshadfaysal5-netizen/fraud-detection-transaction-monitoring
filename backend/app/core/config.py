from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment (see .env.example)."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # --- App ---
    app_name: str = "real-time-fraud-detection"
    environment: str = "development"
    debug: bool = True
    api_origin: str = "http://localhost:8000"
    frontend_origin: str = "http://localhost:3000"

    # --- Security ---
    jwt_secret_key: str = "change-me-please"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7
    password_iterations: int = 260_000

    # --- Database ---
    postgres_db: str = "fraud_monitor"
    postgres_user: str = "fraud_app"
    postgres_password: str = "fraud_app_pw"
    postgres_host: str = "postgres"
    postgres_port: int = 5432
    database_url: str = "postgresql+psycopg://fraud_app:fraud_app_pw@postgres:5432/fraud_monitor"

    # --- Cache ---
    redis_host: str = "redis"
    redis_port: int = 6379
    redis_password: str = ""
    redis_db: int = 0
    redis_url: str = "redis://redis:6379/0"
    redis_ttl_velocity: int = 3600

    # --- Streaming ---
    kafka_bootstrap_servers: str = "kafka:9092"
    kafka_topic_tx_ingest: str = "tx.ingest"
    kafka_topic_tx_decisions: str = "tx.decisions"
    kafka_topic_alerts: str = "alerts"
    kafka_topic_audit: str = "audit"
    kafka_topic_ml_features: str = "ml.features"
    kafka_consumer_group: str = "fraud-engine"

    # --- Fraud engine ---
    risk_threshold_review: int = 50
    risk_threshold_block: int = 80
    risk_weight_rule: float = 0.45
    risk_weight_ml: float = 0.55

    # --- ML ---
    model_path: str = "ml/artifacts/model.joblib"

    @property
    def cors_origins(self) -> list[str]:
        return [self.frontend_origin, self.api_origin, "http://localhost:3000", "http://localhost:8000"]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()