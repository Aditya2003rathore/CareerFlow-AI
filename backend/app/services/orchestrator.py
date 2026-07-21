import time
import random
import json
import httpx
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from backend.app.database.models import Job, Company, SyncRun, SessionLocal
from backend.app.connectors import fetch_all_jobs

def fetch_with_retry(url: str, max_retries: int = 3, timeout: float = 15.0) -> httpx.Response | None:
    """Fetches a URL with exponential backoff, jitter, and 429 Retry-After handling."""
    for attempt in range(max_retries):
        try:
            r = httpx.get(url, timeout=timeout)
            if r.status_code == 429:
                wait = int(r.headers.get("Retry-After", 2 ** attempt))
                time.sleep(wait)
                continue
            r.raise_for_status()
            return r
        except (httpx.TimeoutException, httpx.HTTPStatusError):
            if attempt == max_retries - 1:
                return None
            time.sleep((2 ** attempt) + random.uniform(0, 1))
    return None

def upsert_job_records(db: Session, normalized_jobs: list) -> int:
    """Atomic upserts job records into Postgres/SQLite using batching to prevent locks."""
    new_count = 0
    is_postgres = (db.bind.dialect.name == "postgresql")

    # Pre-fetch and cache companies
    companies = {c.name.lower(): c for c in db.query(Company).all()}
    
    missing_companies = set()
    for jd in normalized_jobs:
        company_name = jd.get("company", "Unknown").strip()
        if company_name.lower() not in companies:
            missing_companies.add(company_name)
            
    if missing_companies:
        for name in missing_companies:
            new_company = Company(name=name)
            db.add(new_company)
        db.commit()
        companies = {c.name.lower(): c for c in db.query(Company).all()}

    # Cache existing jobs for SQLite fallback
    existing_jobs = {}
    if not is_postgres:
        existing_jobs = {j.fingerprint: j for j in db.query(Job).all()}

    for jd in normalized_jobs:
        company_name = jd.get("company", "Unknown").strip()
        company = companies.get(company_name.lower())
        company_id = company.id if company else None

        skills_str = json.dumps(jd.get("skills", []))
        
        job_data = {
            "external_id": str(jd.get("id")),
            "source": jd.get("source"),
            "fingerprint": jd.get("fingerprint") or jd.get("id"),
            "title": jd.get("title"),
            "company_id": company_id,
            "location": jd.get("location"),
            "remote": jd.get("remote", False),
            "salary_min": jd.get("salary_min"),
            "salary_max": jd.get("salary_max"),
            "currency": jd.get("currency", "INR"),
            "description": jd.get("description"),
            "skills": skills_str,
            "apply_url": jd.get("url"),
            "fresher": jd.get("fresher", False),
            "active": True,
            "posted_at": datetime.utcnow()
        }

        if is_postgres:
            stmt = pg_insert(Job).values(**job_data)
            stmt = stmt.on_conflict_do_update(
                index_elements=["fingerprint"],
                set_={"last_seen_at": datetime.utcnow(), "active": True}
            )
            res = db.execute(stmt)
            if res.rowcount > 0:
                new_count += 1
        else:
            existing = existing_jobs.get(job_data["fingerprint"])
            if existing:
                for k, v in job_data.items():
                    setattr(existing, k, v)
                existing.last_seen_at = datetime.utcnow()
                existing.active = True
            else:
                db.add(Job(**job_data))
                new_count += 1
                
    db.commit()
    return new_count

def deactivate_stale_jobs(db: Session):
    """Deactivates jobs not seen in the last 3 sync cycles (active = False)."""
    # Deactivate jobs whose last_seen_at is older than 24 hours (approx 3 runs of 6 hours)
    threshold = datetime.utcnow() - timedelta(hours=24)
    db.query(Job).filter(Job.active == True, Job.last_seen_at < threshold).update({"active": False})
    db.commit()

async def run_sync_orchestrator(db_session: Session = None, custom_gh: list = None, custom_lv: list = None) -> dict:
    """Executes idempotent Job sync pipeline ensuring lock safety."""
    db = db_session if db_session is not None else SessionLocal()
    
    try:
        # Check if a sync run is currently active
        active = db.query(SyncRun).filter(SyncRun.status == "running").first()
        if active:
            return {"skipped": "sync already in progress"}

        # Register start run
        run_log = SyncRun(status="running")
        db.add(run_log)
        db.commit()
        db.refresh(run_log)

        found_count = 0
        new_count = 0
        errors_list = []

        try:
            # Fetch normalized listings
            raw_listings = fetch_all_jobs(custom_gh, custom_lv)
            found_count = len(raw_listings)

            # Upsert jobs
            new_count = upsert_job_records(db, raw_listings)

            # Deactivate stale
            deactivate_stale_jobs(db)

            # Update log success
            run_log.status = "success"
            run_log.finished_at = datetime.utcnow()
            run_log.jobs_found = found_count
            run_log.jobs_new = new_count
            db.commit()
            
        except Exception as e:
            # Log failure
            errors_list.append({"source": "orchestrator", "error": str(e)})
            run_log.status = "failed"
            run_log.finished_at = datetime.utcnow()
            run_log.errors = json.dumps(errors_list)
            db.commit()

        return {
            "status": run_log.status,
            "jobs_found": found_count,
            "jobs_new": new_count,
            "errors": errors_list
        }
    finally:
        if db_session is None:
            db.close()
