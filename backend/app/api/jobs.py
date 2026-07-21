import json
from fastapi import APIRouter, Depends, BackgroundTasks, HTTPException, Request
from sqlalchemy.orm import Session
from sqlalchemy import or_, func
from datetime import datetime
from backend.app.database.models import get_db, Job, User, Company, Application, APIKey
from backend.app.api.auth import get_current_user
from backend.app.services.orchestrator import run_sync_orchestrator
from backend.app.services.ai_service import get_cached_or_compute_match
from backend.app.config import settings, decrypt_key

router = APIRouter(prefix="/jobs", tags=["Jobs"])

@router.get("/")
def list_jobs(
    q: str = "",
    remote: bool = False,
    location: str = "",
    salary_min: int = 0,
    tags: str = "",
    fresher: bool = False,
    source: str = "All",
    limit: int = 50,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Search jobs in normalized database cache with query parameters."""
    if source in ["LinkedIn", "Naukri", "Glassdoor"]:
        from scraper import search_live_jobs
        return search_live_jobs(q, location, source, limit=limit)
        
    query = db.query(Job).join(Company)
    
    if q.strip():
        parts = q.strip().split()
        for part in parts:
            query = query.filter(
                or_(
                    Job.title.like(f"%{part}%"),
                    Job.description.like(f"%{part}%"),
                    Company.name.like(f"%{part}%")
                )
            )
            
    if location.strip():
        query = query.filter(Job.location.like(f"%{location.strip()}%"))
        
    if remote:
        query = query.filter(Job.remote == True)
        
    if fresher:
        query = query.filter(Job.fresher == True)
        
    if salary_min > 0:
        query = query.filter(or_(Job.salary_min >= salary_min, Job.salary_max >= salary_min))
        
    if source and source != "All":
        query = query.filter(Job.source == source)
        
    # Get active jobs only
    query = query.filter(Job.active == True)
    
    jobs = query.order_by(Job.last_seen_at.desc()).limit(limit).all()
    
    results = []
    for j in jobs:
        try:
            skills = json.loads(j.skills)
        except Exception:
            skills = []
            
        # Get application stage if exists
        app_stage = "Discovered"
        user_app = db.query(Application).filter(Application.user_id == current_user.id, Application.job_id == j.id).first()
        if user_app:
            app_stage = user_app.status.capitalize()
            
        results.append({
            "id": str(j.id),
            "external_id": j.external_id,
            "title": j.title,
            "company": j.company.name if j.company else "Unknown",
            "location": j.location,
            "salary": f"₹{j.salary_min}–{j.salary_max} LPA" if (j.salary_min and j.salary_max) else "Not Specified",
            "url": j.apply_url,
            "description": j.description,
            "skills": skills,
            "source": j.source,
            "posted_date": j.posted_at.strftime("%Y-%m-%d") if j.posted_at else "Unknown",
            "stage": app_stage
        })
    return results

@router.get("/{id}")
def get_job_detail(
    id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Retrieve single job detail by UUID."""
    job = db.query(Job).filter(Job.id == id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job posting not found.")
        
    try:
        skills = json.loads(job.skills)
    except Exception:
        skills = []
        
    return {
        "id": str(job.id),
        "title": job.title,
        "company": job.company.name if job.company else "Unknown",
        "location": job.location,
        "url": job.apply_url,
        "description": job.description,
        "skills": skills,
        "source": job.source
    }

from pydantic import BaseModel
from typing import Optional

class SaveJobRequest(BaseModel):
    title: str
    company: str
    url: str
    location: str
    description: Optional[str] = None
    source: str

@router.post("/{id}/save")
def save_unsave_job(
    id: str,
    request: Optional[SaveJobRequest] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Toggles pipeline save/unsave state of a job for the authenticated user, creating it dynamically if supplied."""
    job = db.query(Job).filter(Job.id == id).first()
    if not job:
        if not request:
            raise HTTPException(status_code=404, detail="Job posting not found.")
            
        # Create company
        company = db.query(Company).filter(Company.name == request.company).first()
        if not company:
            company = Company(name=request.company)
            db.add(company)
            db.commit()
            db.refresh(company)
            
        # Create job
        job = Job(
            id=id,
            external_id=id,
            source=request.source,
            fingerprint=f"manual-{id}",
            title=request.title,
            company_id=company.id,
            location=request.location,
            apply_url=request.url,
            description=request.description or f"Saved from live {request.source}",
            skills="[]",
            active=True
        )
        db.add(job)
        db.commit()
        db.refresh(job)
        
    app_record = db.query(Application).filter(
        Application.user_id == current_user.id,
        Application.job_id == id
    ).first()
    
    if app_record:
        # Toggle between 'saved' and 'discovered'
        if app_record.status == "saved":
            app_record.status = "discovered"
        else:
            app_record.status = "saved"
    else:
        # Create a new application record
        app_record = Application(
            user_id=current_user.id,
            job_id=id,
            status="saved"
        )
        db.add(app_record)
        
    db.commit()
    return {"message": "Job status updated successfully.", "stage": app_record.status.capitalize()}

@router.get("/{id}/match")
def get_job_match(
    id: str,
    title: Optional[str] = None,
    company: Optional[str] = None,
    description: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Computes or retrieves cached AI match score analysis."""
    job = db.query(Job).filter(Job.id == id).first()
    
    gemini_entry = db.query(APIKey).filter(APIKey.user_id == current_user.id, APIKey.provider == "gemini").first()
    gemini_key = decrypt_key(gemini_entry.encrypted_key) if gemini_entry else settings.DEFAULT_GROQ_API_KEY
    
    if job:
        desc = job.description
    elif id.startswith("live-"):
        desc = description or f"Position: {title or 'Role'} at {company or 'Company'}."
    else:
        raise HTTPException(status_code=404, detail="Job posting not found.")
        
    try:
        match_analysis = get_cached_or_compute_match(
            db=db,
            user_id=current_user.id,
            job_id=id,
            job_description=desc,
            api_key=gemini_key
        )
        return match_analysis
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/sync")
def trigger_sync(
    request: Request,
    background_tasks: BackgroundTasks,
    custom_gh_boards: str = "",
    custom_lv_boards: str = "",
    db: Session = Depends(get_db)
):
    """Triggers background syncer cron run. Secured by SYNC_TOKEN checks."""
    auth_header = request.headers.get("Authorization")
    authorized = False
    
    if auth_header:
        if auth_header == f"Bearer {settings.SYNC_TOKEN}":
            authorized = True
        else:
            try:
                token = auth_header.split(" ")[1]
                get_current_user(token, db)
                authorized = True
            except Exception:
                pass
                
    if not authorized:
        raise HTTPException(status_code=401, detail="Unauthorized")
        
    gh_list = [c.strip() for c in custom_gh_boards.split(",") if c.strip()] if custom_gh_boards else None
    lv_list = [c.strip() for c in custom_lv_boards.split(",") if c.strip()] if custom_lv_boards else None
    
    background_tasks.add_task(run_sync_orchestrator, None, gh_list, lv_list)
    return {"message": "Sync started in background."}

@router.get("/stats")
def get_stats(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    total = db.query(Job).count()
    sources = {}
    sources_query = db.query(Job.source, func.count(Job.id)).group_by(Job.source).all()
    for src, count in sources_query:
        sources[src] = count
        
    return {
        "total": total,
        "sources": sources
    }
