import os
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # Database
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///e:/razor/backend/recoverai.db")

    # Policy Defaults
    MAX_RETRIES: int = int(os.getenv("MAX_RETRIES", 2))
    MAX_RECOVERY_WINDOW_HOURS: int = int(os.getenv("MAX_RECOVERY_WINDOW_HOURS", 48))
    HIGH_VALUE_THRESHOLD_INR: float = float(os.getenv("HIGH_VALUE_THRESHOLD_INR", 20000.0))

    # Keys (optional for live AI, heuristic engine handles fallback)
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")

    # Razorpay Test Credentials (for optional real test-mode integration)
    RAZORPAY_KEY_ID: str = os.getenv("RAZORPAY_KEY_ID", "")
    RAZORPAY_KEY_SECRET: str = os.getenv("RAZORPAY_KEY_SECRET", "")

    # Simulator Config
    SIMULATOR_TICK_SPEED_SECONDS: int = 5

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

settings = Settings()
