from fastapi import FastAPI, Depends
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from backend.app.config import settings
from backend.app.database.models import init_db_schema, get_db
from backend.app.api import auth, jobs, resumes, automation, outreach, applications

app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json"
)

# CORS configurations
origins = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:8000",
    "http://127.0.0.1:8000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Startup hook to initialize schemas and seed allowed emails list
@app.on_event("startup")
def startup_event():
    init_db_schema()
    
    from backend.app.database.models import SessionLocal, AllowedEmail
    db = SessionLocal()
    try:
        # Seed allowed email list
        for email in ["admin@example.com", "user@example.com", "aditya@example.com"]:
            if not db.query(AllowedEmail).filter(AllowedEmail.email == email).first():
                db.add(AllowedEmail(email=email, invited_by="system"))
        
        # Reset any stuck sync runs from previous crash/restart
        from backend.app.database.models import SyncRun
        db.query(SyncRun).filter(SyncRun.status == "running").update({"status": "failed"})
        
        db.commit()
        print("Default database schemas and allowed emails seeded successfully.")
    except Exception as e:
        print(f"Database seeding failed: {str(e)}")
    finally:
        db.close()

# Health check route verifying database connectivity as per §8 specifications
@app.get("/api/health", tags=["Health"])
def health(db: Session = Depends(get_db)):
    try:
        db.execute("SELECT 1")
        return {"status": "ok", "db": "connected"}
    except Exception:
        return JSONResponse(
            status_code=503, 
            content={"status": "degraded", "db": "unreachable"}
        )

# Include REST routes
app.include_router(auth.router, prefix=settings.API_V1_STR)
app.include_router(jobs.router, prefix=settings.API_V1_STR)
app.include_router(resumes.router, prefix=settings.API_V1_STR)
app.include_router(automation.router, prefix=settings.API_V1_STR)
app.include_router(outreach.router, prefix=settings.API_V1_STR)
app.include_router(applications.router, prefix=settings.API_V1_STR)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
