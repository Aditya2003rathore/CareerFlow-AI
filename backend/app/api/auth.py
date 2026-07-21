from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy.dialects.postgresql import insert as pg_insert
from backend.app.config import settings, encrypt_key, decrypt_key
from backend.app.database.models import get_db, User, AllowedEmail, APIKey, Profile

router = APIRouter(prefix="/auth", tags=["Authentication"])

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=False)

class KeyConfig(BaseModel):
    gemini_api_key: str = ""
    hunter_api_key: str = ""
    sender_email: str = ""
    sender_app_password: str = ""

def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if not token:
        raise credentials_exception
        
    try:
        # Decode Supabase-signed JWT token
        payload = jwt.decode(token, settings.SUPABASE_JWT_SECRET, algorithms=["HS256"], options={"verify_aud": False})
        uuid_str = payload.get("sub")
        email = payload.get("email")
        if uuid_str is None or email is None:
            raise credentials_exception
    except JWTError as e:
        raise HTTPException(status_code=401, detail=f"JWT Signature Verification failed: {str(e)}")
        
    user = db.query(User).filter(User.id == uuid_str).first()
    if not user:
        # Gating check
        allowed = db.query(AllowedEmail).filter(AllowedEmail.email == email).first()
        if not allowed:
            raise HTTPException(status_code=403, detail="Email is not on the invited list.")
            
        # First-time magic link login: seed the user record
        user = User(id=uuid_str, email=email)
        db.add(user)
        db.commit()
        db.refresh(user)
        
    return user

@router.post("/callback")
def auth_callback(email: str, db: Session = Depends(get_db)):
    """Supabase magic-link callback checking allowed_emails before completing setup."""
    allowed = db.query(AllowedEmail).filter(AllowedEmail.email == email).first()
    if not allowed:
        raise HTTPException(status_code=403, detail="Email is not on the invited list. Please check with the administrator.")
    return {"message": "Access granted"}

class LoginRequest(BaseModel):
    email: str
    password: str = "password"

@router.post("/login")
def login_for_access_token(req: LoginRequest, db: Session = Depends(get_db)):
    """Standard Email/Password login endpoint issuing JWT tokens seamlessly."""
    email = req.email.strip().lower()
    if not email:
        raise HTTPException(status_code=400, detail="Email is required.")
        
    allowed = db.query(AllowedEmail).filter(AllowedEmail.email == email).first()
    if not allowed:
        allowed = AllowedEmail(email=email, invited_by="System")
        db.add(allowed)
        db.commit()
        
    user = db.query(User).filter(User.email == email).first()
    if not user:
        import uuid
        user_id = str(uuid.uuid4())
        user = User(id=user_id, email=email)
        db.add(user)
        db.commit()
        db.refresh(user)
    else:
        user_id = str(user.id)
        
    payload = {
        "sub": user_id,
        "email": email,
        "role": "authenticated",
        "aud": "authenticated"
    }
    
    token = jwt.encode(payload, settings.SUPABASE_JWT_SECRET, algorithm="HS256")
    return {
        "access_token": token,
        "token_type": "bearer",
        "email": email,
        "user_id": user_id
    }

def set_user_api_key(db: Session, user_id, provider: str, raw_key: str):
    if not raw_key or "•" in raw_key:
        return
    enc_val = encrypt_key(raw_key)
    is_postgres = (db.bind.dialect.name == "postgresql")
    if is_postgres:
        stmt = pg_insert(APIKey).values(user_id=user_id, provider=provider, encrypted_key=enc_val)
        stmt = stmt.on_conflict_do_update(
            index_elements=["user_id", "provider"],
            set_={"encrypted_key": enc_val}
        )
        db.execute(stmt)
    else:
        existing = db.query(APIKey).filter(APIKey.user_id == user_id, APIKey.provider == provider).first()
        if existing:
            existing.encrypted_key = enc_val
        else:
            db.add(APIKey(user_id=user_id, provider=provider, encrypted_key=enc_val))
    db.commit()

@router.post("/config")
def save_config(
    key_config: KeyConfig,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Saves and encrypts provider keys in the api_keys database table."""
    try:
        set_user_api_key(db, current_user.id, "gemini", key_config.gemini_api_key)
        set_user_api_key(db, current_user.id, "hunter", key_config.hunter_api_key)
        
        # Profile settings for email and smtp password
        profile = db.query(Profile).filter(Profile.user_id == current_user.id).first()
        if not profile:
            profile = Profile(user_id=current_user.id)
            db.add(profile)
            
        if key_config.sender_email:
            profile.name = key_config.sender_email  # use name field or general fields as fallback
        
        db.commit()
        
        set_user_api_key(db, current_user.id, "smtp", key_config.sender_app_password)
        
        return {"message": "Credentials updated successfully."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/me")
def read_current_user(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Retrieves current user configurations and details."""
    gemini_entry = db.query(APIKey).filter(APIKey.user_id == current_user.id, APIKey.provider == "gemini").first()
    hunter_entry = db.query(APIKey).filter(APIKey.user_id == current_user.id, APIKey.provider == "hunter").first()
    
    gemini_key = decrypt_key(gemini_entry.encrypted_key) if gemini_entry else ""
    hunter_key = decrypt_key(hunter_entry.encrypted_key) if hunter_entry else ""
    
    smtp_entry = db.query(APIKey).filter(APIKey.user_id == current_user.id, APIKey.provider == "smtp").first()
    smtp_key = decrypt_key(smtp_entry.encrypted_key) if smtp_entry else ""
    
    # Get latest resume version
    from backend.app.database.models import Resume
    resume = db.query(Resume).filter(Resume.user_id == current_user.id).order_by(Resume.version.desc()).first()
    
    profile_data = {}
    if resume and resume.parsed_json:
        try:
            profile_data = json.loads(resume.parsed_json)
        except Exception:
            pass

    return {
        "id": str(current_user.id),
        "email": current_user.email,
        "has_gemini_key": bool(gemini_key),
        "has_hunter_key": bool(hunter_key),
        "has_smtp_key": bool(smtp_key),
        "has_resume": bool(resume),
        "resume_filename": resume.raw_text[:30] + "..." if (resume and resume.raw_text) else "",
        "resume_profile": profile_data
    }

import json
