import os
import urllib.parse
from datetime import datetime
from fastapi import APIRouter, Depends, BackgroundTasks, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from backend.app.database.models import get_db, User, Application, Job, Resume
from backend.app.api.auth import get_current_user
from backend.app.services.automation_service import apply_to_job

router = APIRouter(prefix="/automation", tags=["Automation"])

class ApplyRequest(BaseModel):
    job_url: str
    job_id: str
    mode: str = "Pre-Fill"  # Pre-Fill, Auto Apply
    headless: bool = False

def run_apply_pipeline(user_id: str, job_id: str, job_url: str, mode: str, headless: bool):
    """Background task to run Playwright auto-apply and update application state."""
    db = next(get_db())
    try:
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            return
            
        # Get profile JSON
        resume = db.query(Resume).filter(Resume.user_id == user_id).order_by(Resume.version.desc()).first()
        profile = json.loads(resume.parsed_json) if (resume and resume.parsed_json) else {}
        
        resume_path = f"resumes/{user_id}_resume.pdf"
        
        # Log callback
        def log_cb(text):
            print(f"[{user_id[:8]} Playwright Log] {text}")
            
        res = apply_to_job(
            profile=profile,
            resume_path=resume_path,
            job_url=job_url,
            mode=mode,
            headless=headless,
            logger=log_cb
        )
        
        # Update/create application status
        app_record = db.query(Application).filter(
            Application.user_id == user_id,
            Application.job_id == job_id
        ).first()
        
        if not app_record:
            app_record = Application(user_id=user_id, job_id=job_id)
            db.add(app_record)
            
        app_record.status = "applied" if res.get("submitted") else "saved"
        app_record.applied_at = datetime.utcnow()
        app_record.notes = f"Playwright Run Log: {res.get('message')}"
        app_record.updated_at = datetime.utcnow()
        
        db.commit()
    except Exception as e:
        print(f"Playwright pipeline failed for user '{user_id}': {str(e)}")
    finally:
        db.close()

import json

@router.post("/apply")
def trigger_apply(
    request: ApplyRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # Verify resume exists
    resume = db.query(Resume).filter(Resume.user_id == current_user.id).order_by(Resume.version.desc()).first()
    if not resume:
        raise HTTPException(status_code=400, detail="Please upload your resume PDF first.")
        
    resume_path = f"resumes/{current_user.id}_resume.pdf"
    
    # Save a copy to resumes/ directory if it doesn't exist but we have raw_text (or write it from DB in a real deployment)
    # For now, standard file upload writes to resumes/ username_resume.pdf. Let's make sure we write it for user.id:
    # Let's ensure parent folder exists
    os.makedirs("resumes", exist_ok=True)
    
    # Queue the automation run
    background_tasks.add_task(
        run_apply_pipeline, 
        str(current_user.id),
        request.job_id,
        request.job_url, 
        request.mode, 
        request.headless
    )
    
    return {"message": "Playwright automation initialized. Watch your browser popup!"}
