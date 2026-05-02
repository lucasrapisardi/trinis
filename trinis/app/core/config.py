# PATH: /home/lumoura/trinis_ai/trinis/app/core/config.py
from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # ── App ──────────────────────────────────────────
    app_env: str = "development"
    app_secret_key: str = "change-me"
    app_base_url: str = "http://localhost:3000"

    # ── Database ─────────────────────────────────────
    database_url: str = "postgresql+asyncpg://productsync:password@localhost:5432/productsync"

    # ── Redis ────────────────────────────────────────
    redis_url: str = "redis://localhost:6379/0"

    # ── Auth (JWT) ───────────────────────────────────
    jwt_secret_key: str = "change-me"
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 60
    jwt_refresh_token_expire_days: int = 30

    # ── Shopify ──────────────────────────────────────
    shopify_app_client_id: str = ""
    shopify_app_client_secret: str = ""
    shopify_api_version: str = "2024-07"
    shopify_token_encryption_key: str = ""
    shopify_callback_url: str = ""

    # ── OpenAI ───────────────────────────────────────
    openai_api_key: str = ""

    # ── Stripe ───────────────────────────────────────
    stripe_secret_key: str = ""
    stripe_webhook_secret: str = ""
    stripe_free_price_id: str = ""
    stripe_starter_price_id: str = ""
    stripe_pro_price_id: str = ""
    stripe_business_price_id: str = ""
    stripe_starter_annual_price_id: str = ""
    stripe_pro_annual_price_id: str = ""
    stripe_business_annual_price_id: str = ""
    stripe_backup_basic_price_id: str = ""
    stripe_backup_standard_price_id: str = ""
    stripe_backup_premium_price_id: str = ""
    # Bulk Enhance
    stripe_bulk_enhance_essencial_price_id: str = ""
    stripe_bulk_enhance_avancado_price_id: str = ""
    stripe_bulk_enhance_ilimitado_price_id: str = ""
    # Credits one-time
    stripe_credits_starter_price_id: str = ""
    stripe_credits_growth_price_id: str = ""
    stripe_credits_scale_price_id: str = ""
    stripe_credits_pro_price_id: str = ""
    # AI providers
    google_api_key: str = ""
    anthropic_api_key: str = ""
    # Model add-on Stripe price IDs
    stripe_model_standard_price_id: str = ""
    stripe_model_premium_price_id: str = ""
    stripe_model_ultra_price_id: str = ""

    # ── Resend (email service) ────────────────────────
    resend_api_key: str = ""
    resend_from_domain: str = "resend.dev"

    # ── MinIO (image storage) ─────────────────────────
    minio_endpoint_url: str = "http://localhost:9000"
    minio_access_key: str = "productsync"
    minio_secret_key: str = "productsync123"

    # ── S3 (legacy) ──────────────────────────────────
    aws_access_key_id: str = ""
    aws_secret_access_key: str = ""
    aws_s3_bucket: str = "productsync-images"
    aws_s3_region: str = "us-east-1"

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()
