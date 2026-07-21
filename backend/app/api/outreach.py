import os
import urllib.parse
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from backend.app.database.models import get_db, User, APIKey, Profile, Resume, Recruiter, OutreachMessage
from backend.app.api.auth import get_current_user
from backend.app.services.outreach_service import resolve_email, generate_outreach_email, send_outreach_email
from backend.app.config import settings, decrypt_key
from scraper import search_recruiters

router = APIRouter(prefix="/outreach", tags=["Outreach"])

class RecruiterSearchRequest(BaseModel):
    company: str
    role_keywords: list = ["Recruiter", "Talent Acquisition", "Hiring Manager"]
    limit: int = 3

class EmailDraftRequest(BaseModel):
    recruiter_name: str
    recruiter_title: str
    company: str
    job_description: str = "Hiring opportunities matching my skill profile"
    custom_instruction: str = ""

class EmailSendRequest(BaseModel):
    recipient_email: str
    subject: str
    body: str

@router.post("/search")
def search_recruiters_endpoint(
    request: RecruiterSearchRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Searches recruiter LinkedIn URLs and resolves corporate emails."""
    if not request.company:
        raise HTTPException(status_code=400, detail="Company name is required.")
        
    hunter_entry = db.query(APIKey).filter(APIKey.user_id == current_user.id, APIKey.provider == "hunter").first()
    hunter_key = decrypt_key(hunter_entry.encrypted_key) if hunter_entry else ""
    
    try:
        leads = search_recruiters(request.company, request.role_keywords, limit=request.limit)
        
        # Resolve emails
        for lead in leads:
            resolved = resolve_email(
                lead["name"],
                lead["name"],
                lead["company"],
                hunter_api_key=hunter_key
            )
            lead["email"] = resolved["email"]
            lead["method"] = resolved["method"]
            lead["all_guesses"] = resolved["all_guesses"]
            
        return leads
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/draft")
def generate_draft(
    request: EmailDraftRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Generates a personalized outreach email draft using Gemini."""
    resume = db.query(Resume).filter(Resume.user_id == current_user.id).order_by(Resume.version.desc()).first()
    if not resume or not resume.raw_text:
        raise HTTPException(status_code=400, detail="Please upload your resume PDF first.")
        
    gemini_entry = db.query(APIKey).filter(APIKey.user_id == current_user.id, APIKey.provider == "gemini").first()
    gemini_key = decrypt_key(gemini_entry.encrypted_key) if gemini_entry else settings.DEFAULT_GROQ_API_KEY
    try:
        draft = generate_outreach_email(
            resume_text=resume.raw_text,
            recruiter_name=request.recruiter_name,
            recruiter_title=request.recruiter_title,
            company=request.company,
            job_desc=request.job_description,
            api_key=gemini_key,
            custom_instruction=request.custom_instruction
        )
        return draft
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/send")
def send_email_endpoint(
    request: EmailSendRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Sends the outreach email to a recruiter with the resume attached."""
    profile = db.query(Profile).filter(Profile.user_id == current_user.id).first()
    sender_email = profile.name if profile else None
    
    smtp_entry = db.query(APIKey).filter(APIKey.user_id == current_user.id, APIKey.provider == "smtp").first()
    sender_password = decrypt_key(smtp_entry.encrypted_key) if smtp_entry else ""
    
    if not sender_email or not sender_password:
        raise HTTPException(status_code=400, detail="SMTP credentials are not configured in settings.")
        
    resume_path = f"resumes/{current_user.id}_resume.pdf"
    if not os.path.exists(resume_path):
        raise HTTPException(status_code=400, detail="Local resume PDF file is missing.")
        
    # Read resume bytes
    with open(resume_path, "rb") as f:
        resume_bytes = f.read()
        
    filename = "Resume.pdf"
    
    try:
        success = send_outreach_email(
            sender_email=sender_email,
            sender_password=sender_password,
            recipient_email=request.recipient_email,
            subject=request.subject,
            body=request.body,
            resume_bytes=resume_bytes,
            resume_filename=filename
        )
        if success:
            # Seed recruiter details in psql tables
            recruiter = Recruiter(
                name=request.recipient_email.split("@")[0].capitalize(),
                contact_method=request.recipient_email,
                source="Direct"
            )
            db.add(recruiter)
            db.commit()
            db.refresh(recruiter)
            
            # Log outreach message
            outreach_msg = OutreachMessage(
                user_id=current_user.id,
                recruiter_id=recruiter.id,
                draft=request.body,
                sent=True,
                sent_at=datetime.utcnow()
            )
            db.add(outreach_msg)
            db.commit()
            return {"message": "Email sent successfully."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to send email: {str(e)}")
