from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from datetime import datetime
from backend.app.database.models import get_db, User, Application, Job, Company
from backend.app.api.auth import get_current_user

router = APIRouter(prefix="/applications", tags=["Applications"])

class ApplicationCreate(BaseModel):
    job_id: str
    status: str = "discovered"

class ApplicationUpdate(BaseModel):
    status: str
    notes: str = None

@router.post("")
def create_application(
    app_in: ApplicationCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """POST /api/applications: Create tracker entry."""
    # Check if job exists
    job = db.query(Job).filter(Job.id == app_in.job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job posting not found.")
        
    # Check if existing application exists
    existing = db.query(Application).filter(
        Application.user_id == current_user.id,
        Application.job_id == app_in.job_id
    ).first()
    
    if existing:
        existing.status = app_in.status
        db.commit()
        db.refresh(existing)
        return existing
        
    new_app = Application(
        user_id=current_user.id,
        job_id=app_in.job_id,
        status=app_in.status
    )
    db.add(new_app)
    db.commit()
    db.refresh(new_app)
    return new_app

@router.patch("/{id}")
def update_application(
    id: str,
    app_up: ApplicationUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """PATCH /api/applications/{id}: Move pipeline stage."""
    app_record = db.query(Application).filter(
        Application.id == id,
        Application.user_id == current_user.id
    ).first()
    
    if not app_record:
        raise HTTPException(status_code=404, detail="Application tracker entry not found.")
        
    # Validate stage status
    valid_statuses = ["discovered", "saved", "applied", "interview", "offer", "rejected"]
    if app_up.status not in valid_statuses:
        raise HTTPException(status_code=400, detail=f"Invalid pipeline status. Must be one of {valid_statuses}")
        
    app_record.status = app_up.status
    if app_up.status == "applied" and not app_record.applied_at:
        app_record.applied_at = datetime.utcnow()
        
    if app_up.notes is not None:
        app_record.notes = app_up.notes
        
    app_record.updated_at = datetime.utcnow()
    db.commit()
    return app_record

@router.get("")
def list_applications(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """GET /api/applications: List, grouped by stage."""
    apps = db.query(Application).filter(Application.user_id == current_user.id).all()
    
    stages = {
        "discovered": [],
        "saved": [],
        "applied": [],
        "interview": [],
        "offer": [],
        "rejected": []
    }
    
    for a in apps:
        job_detail = {}
        if a.job:
            job_detail = {
                "id": str(a.job.id),
                "title": a.job.title,
                "company": a.job.company.name if a.job.company else "Unknown",
                "salary": f"₹{a.job.salary_min}–{a.job.salary_max} LPA" if (a.job.salary_min and a.job.salary_max) else "Not Specified"
            }
        stages[a.status].append({
            "id": str(a.id),
            "job": job_detail,
            "applied_at": a.applied_at.strftime("%Y-%m-%d") if a.applied_at else None,
            "notes": a.notes
        })
        
    return stages
