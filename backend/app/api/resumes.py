import json
import io
import os
import uuid
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from backend.app.database.models import get_db, User, Resume, APIKey, Profile
from backend.app.api.auth import get_current_user
from backend.app.services.ai_service import parse_resume_profile
from ats_analyzer import extract_text_from_pdf
from backend.app.config import settings, decrypt_key

router = APIRouter(prefix="/resume", tags=["Resumes"])

class ProfileUpdate(BaseModel):
    name: str = ""
    email: str = ""
    phone: str = ""
    location: str = ""
    linkedin: str = ""
    github: str = ""
    portfolio: str = ""
    skills: list = []
    summary: str = ""
    college: str = ""
    cgpa: float = 0.0
    branch: str = ""
    grad_year: int = 2024
    experience_level: str = "fresher"

@router.post("")
async def upload_and_parse_resume(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """POST /api/resume: Uploads a PDF resume, parses it, and stores versioned JSON."""
    if not file.filename.endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF resumes are supported.")
        
    try:
        contents = await file.read()
        resume_text = extract_text_from_pdf(io.BytesIO(contents))
        
        # Get Gemini or default Groq key
        gemini_entry = db.query(APIKey).filter(APIKey.user_id == current_user.id, APIKey.provider == "gemini").first()
        gemini_key = decrypt_key(gemini_entry.encrypted_key) if gemini_entry else settings.DEFAULT_GROQ_API_KEY
        
        # Parse resume using LiteLLM/Groq/Gemini
        parsed_data = parse_resume_profile(resume_text, gemini_key)
        
        # Determine version
        latest = db.query(Resume).filter(Resume.user_id == current_user.id).order_by(Resume.version.desc()).first()
        new_version = (latest.version + 1) if latest else 1
        
        # Save resume record
        resume = Resume(
            user_id=current_user.id,
            raw_text=resume_text,
            parsed_json=json.dumps(parsed_data),
            version=new_version
        )
        db.add(resume)
        
        # Save/update profiles record
        profile = db.query(Profile).filter(Profile.user_id == current_user.id).first()
        if not profile:
            profile = Profile(user_id=current_user.id)
            db.add(profile)
            
        profile.name = parsed_data.get("name")
        profile.college = parsed_data.get("college")
        profile.cgpa = parsed_data.get("cgpa")
        profile.branch = parsed_data.get("branch")
        profile.grad_year = parsed_data.get("grad_year")
        profile.experience_level = parsed_data.get("experience_level")
        
        db.commit()
        return {
            "version": new_version,
            "profile": parsed_data,
            "message": "Resume uploaded and parsed successfully."
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to process resume: {str(e)}")

@router.get("")
def get_latest_resume(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """GET /api/resume: Retrieves the latest parsed resume JSON."""
    resume = db.query(Resume).filter(Resume.user_id == current_user.id).order_by(Resume.version.desc()).first()
    if not resume:
        raise HTTPException(status_code=404, detail="No resume has been uploaded yet.")
        
    try:
        return json.loads(resume.parsed_json)
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to parse resume JSON data.")

@router.patch("")
def update_parsed_resume(
    profile_data: ProfileUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """PATCH /api/resume: Edits parsed fields after user review."""
    resume = db.query(Resume).filter(Resume.user_id == current_user.id).order_by(Resume.version.desc()).first()
    if not resume:
        raise HTTPException(status_code=404, detail="No resume record found to update.")
        
    profile_dict = profile_data.dict()
    resume.parsed_json = json.dumps(profile_dict)
    
    # Also update profiles table
    profile = db.query(Profile).filter(Profile.user_id == current_user.id).first()
    if profile:
        profile.name = profile_data.name
        profile.college = profile_data.college
        profile.cgpa = profile_data.cgpa
        profile.branch = profile_data.branch
        profile.grad_year = profile_data.grad_year
        profile.experience_level = profile_data.experience_level
        
    db.commit()
    return {"message": "Resume details updated successfully.", "profile": profile_dict}
