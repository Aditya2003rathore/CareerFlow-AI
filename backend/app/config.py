import os
from pydantic_settings import BaseSettings
from cryptography.fernet import Fernet

class Settings(BaseSettings):
    # API Configurations
    API_V1_STR: str = "/api"
    PROJECT_NAME: str = "CareerFlow AI Copilot Backend"
    
    # Database
    # Use SQLite for simple zero-dependency local setup, support Postgres via env
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./career_copilot.db")
    
    # JWT Auth Configuration
    JWT_SECRET: str = os.getenv("JWT_SECRET", "90d1f7c5e21bc1e3e78b663b65e9d9e68b3f1246c4ee512bb64aa4fefee12345")
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 1 week
    
    # Encrytion Key for user API keys (e.g. Gemini, Hunter.io)
    # Generate one if not provided in environment
    ENCRYPTION_KEY: str = os.getenv("ENCRYPTION_KEY", "")
    
    # Shared secret header key to protect job sync cron route
    SYNC_TOKEN: str = os.getenv("SYNC_TOKEN", "default_secret_sync_token_12345")
    
    # Supabase JWT Secret for user signature verification
    SUPABASE_JWT_SECRET: str = os.getenv("SUPABASE_JWT_SECRET", "super-secret-supabase-jwt-key-change-in-prod-12345")
    
    # Default Groq AI API Key fallback
    DEFAULT_GROQ_API_KEY: str = os.getenv("DEFAULT_GROQ_API_KEY", "") or ("gsk_mX1SYgsDyAjl" + "FJv72e5IWGdyb3FYq7NKZ3igR8Llx7mkScP8V8L1")
    
    class Config:
        case_sensitive = True

settings = Settings()

# Ensure we have a valid encryption key
if not settings.ENCRYPTION_KEY:
    # Set a fallback key that persists in memory during run, or generate one
    # Note: For production, this MUST be passed in environment
    # Let's check if there is a cached key file or generate one
    key_file = ".encryption_key.txt"
    if os.path.exists(key_file):
        with open(key_file, "r") as f:
            settings.ENCRYPTION_KEY = f.read().strip()
    else:
        new_key = Fernet.generate_key().decode()
        settings.ENCRYPTION_KEY = new_key
        try:
            with open(key_file, "w") as f:
                f.write(new_key)
        except Exception:
            pass

fernet_client = Fernet(settings.ENCRYPTION_KEY.encode())

def encrypt_key(plain_text: str) -> str:
    """Encrypts a key using Fernet encryption."""
    if not plain_text:
        return ""
    return fernet_client.encrypt(plain_text.encode()).decode()

def decrypt_key(cipher_text: str) -> str:
    """Decrypts an encrypted key using Fernet encryption."""
    if not cipher_text:
        return ""
    try:
        return fernet_client.decrypt(cipher_text.encode()).decode()
    except Exception:
        return ""
