import json
import uuid
from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, create_engine, Boolean, Numeric, ARRAY
from sqlalchemy.orm import declarative_base, relationship, sessionmaker
from sqlalchemy.types import TypeDecorator, CHAR
from sqlalchemy.dialects.postgresql import UUID as pgUUID, JSONB, ARRAY as pgARRAY
from backend.app.config import settings

# Platform-independent GUID type (uses Postgres UUID, otherwise CHAR(36) on SQLite)
class GUID(TypeDecorator):
    impl = CHAR
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == 'postgresql':
            return dialect.type_descriptor(pgUUID(as_uuid=True))
        else:
            return dialect.type_descriptor(CHAR(36))

    def process_bind_param(self, value, dialect):
        if value is None:
            return value
        elif dialect.name == 'postgresql':
            return str(value)
        else:
            if not isinstance(value, uuid.UUID):
                try:
                    return str(uuid.UUID(value))
                except ValueError:
                    return str(value)
            else:
                return str(value)

    def process_result_value(self, value, dialect):
        if value is None:
            return value
        else:
            if not isinstance(value, uuid.UUID):
                try:
                    return uuid.UUID(value)
                except ValueError:
                    return value
            return value

# Setup database engine with PgBouncer connection pooling support (NullPool)
if "pgbouncer=true" in settings.DATABASE_URL.lower():
    from sqlalchemy.pool import NullPool
    engine = create_engine(
        settings.DATABASE_URL,
        poolclass=NullPool
    )
else:
    engine = create_engine(
        settings.DATABASE_URL,
        connect_args={"check_same_thread": False} if settings.DATABASE_URL.startswith("sqlite") else {}
    )

# Enable WAL mode and performance pragmas for SQLite
from sqlalchemy import event
@event.listens_for(engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    if settings.DATABASE_URL.startswith("sqlite"):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.close()

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class User(Base):
    __tablename__ = "users"
    
    id = Column(GUID, primary_key=True, default=uuid.uuid4)
    email = Column(String, unique=True, index=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    profiles = relationship("Profile", back_populates="user", uselist=False, cascade="all, delete-orphan")
    resumes = relationship("Resume", back_populates="user", cascade="all, delete-orphan")
    api_keys = relationship("APIKey", back_populates="user", cascade="all, delete-orphan")
    applications = relationship("Application", back_populates="user", cascade="all, delete-orphan")
    outreach_messages = relationship("OutreachMessage", back_populates="user", cascade="all, delete-orphan")

class AllowedEmail(Base):
    __tablename__ = "allowed_emails"
    
    email = Column(String, primary_key=True, index=True)
    invited_by = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

class Profile(Base):
    __tablename__ = "profiles"
    
    user_id = Column(GUID, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    name = Column(String, nullable=True)
    college = Column(String, nullable=True)
    cgpa = Column(Numeric(3, 2), nullable=True)
    branch = Column(String, nullable=True)
    grad_year = Column(Integer, nullable=True)
    experience_level = Column(String, nullable=True)  # fresher, junior, mid, senior
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    user = relationship("User", back_populates="profiles")

class Resume(Base):
    __tablename__ = "resumes"
    
    id = Column(GUID, primary_key=True, default=uuid.uuid4)
    user_id = Column(GUID, ForeignKey("users.id", ondelete="CASCADE"))
    raw_text = Column(Text, nullable=True)
    parsed_json = Column(Text, nullable=True)  # Stored as string locally, or parsed JSONB
    version = Column(Integer, default=1)
    uploaded_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    user = relationship("User", back_populates="resumes")

class APIKey(Base):
    __tablename__ = "api_keys"
    
    user_id = Column(GUID, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    provider = Column(String, primary_key=True)  # gemini, hunter, smtp
    encrypted_key = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    user = relationship("User", back_populates="api_keys")

class Company(Base):
    __tablename__ = "companies"
    
    id = Column(GUID, primary_key=True, default=uuid.uuid4)
    name = Column(String, unique=True, nullable=False)
    careers_url = Column(String, nullable=True)
    ats_type = Column(String, nullable=True)
    
    # Relationships
    jobs = relationship("Job", back_populates="company", cascade="all, delete-orphan")
    recruiters = relationship("Recruiter", back_populates="company", cascade="all, delete-orphan")

class Job(Base):
    __tablename__ = "jobs"
    
    id = Column(GUID, primary_key=True, default=uuid.uuid4)
    external_id = Column(String, nullable=False)
    source = Column(String, nullable=False)
    fingerprint = Column(String, unique=True, nullable=False)
    title = Column(String, nullable=False)
    company_id = Column(GUID, ForeignKey("companies.id", ondelete="SET NULL"), nullable=True)
    location = Column(String, nullable=True)
    remote = Column(Boolean, default=False)
    salary_min = Column(Integer, nullable=True)
    salary_max = Column(Integer, nullable=True)
    currency = Column(String, default="INR")
    description = Column(Text, nullable=True)
    skills = Column(Text, default="[]")  # JSON list string fallback
    apply_url = Column(String, nullable=False)
    fresher = Column(Boolean, default=False)
    active = Column(Boolean, default=True)
    posted_at = Column(DateTime, nullable=True)
    last_seen_at = Column(DateTime, default=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    company = relationship("Company", back_populates="jobs")
    applications = relationship("Application", back_populates="job", cascade="all, delete-orphan")

class MatchScore(Base):
    __tablename__ = "match_scores"
    
    user_id = Column(GUID, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    job_id = Column(GUID, ForeignKey("jobs.id", ondelete="CASCADE"), primary_key=True)
    resume_version = Column(Integer, primary_key=True)
    score = Column(Integer, nullable=True)
    missing_skills = Column(Text, default="[]")  # JSON list string fallback
    explanation = Column(Text, nullable=True)
    computed_at = Column(DateTime, default=datetime.utcnow)

class Application(Base):
    __tablename__ = "applications"
    
    id = Column(GUID, primary_key=True, default=uuid.uuid4)
    user_id = Column(GUID, ForeignKey("users.id", ondelete="CASCADE"))
    job_id = Column(GUID, ForeignKey("jobs.id", ondelete="SET NULL"), nullable=True)
    status = Column(String, default="discovered")  # discovered, saved, applied, interview, offer, rejected
    applied_at = Column(DateTime, nullable=True)
    notes = Column(Text, nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    user = relationship("User", back_populates="applications")
    job = relationship("Job", back_populates="applications")

class Watchlist(Base):
    __tablename__ = "watchlists"
    
    user_id = Column(GUID, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    company_id = Column(GUID, ForeignKey("companies.id", ondelete="CASCADE"), primary_key=True)

class Recruiter(Base):
    __tablename__ = "recruiters"
    
    id = Column(GUID, primary_key=True, default=uuid.uuid4)
    company_id = Column(GUID, ForeignKey("companies.id", ondelete="SET NULL"), nullable=True)
    name = Column(String, nullable=True)
    role = Column(String, nullable=True)
    contact_method = Column(String, nullable=True)
    source = Column(String, nullable=True)
    
    # Relationships
    company = relationship("Company", back_populates="recruiters")
    outreach_messages = relationship("OutreachMessage", back_populates="recruiter", cascade="all, delete-orphan")

class OutreachMessage(Base):
    __tablename__ = "outreach_messages"
    
    id = Column(GUID, primary_key=True, default=uuid.uuid4)
    user_id = Column(GUID, ForeignKey("users.id", ondelete="CASCADE"))
    recruiter_id = Column(GUID, ForeignKey("recruiters.id", ondelete="CASCADE"))
    draft = Column(Text, nullable=True)
    sent = Column(Boolean, default=False)
    sent_at = Column(DateTime, nullable=True)
    
    # Relationships
    user = relationship("User", back_populates="outreach_messages")
    recruiter = relationship("Recruiter", back_populates="outreach_messages")

class SyncRun(Base):
    __tablename__ = "sync_runs"
    
    id = Column(GUID, primary_key=True, default=uuid.uuid4)
    started_at = Column(DateTime, default=datetime.utcnow)
    finished_at = Column(DateTime, nullable=True)
    status = Column(String, default="running")  # running, success, failed
    jobs_found = Column(Integer, default=0)
    jobs_new = Column(Integer, default=0)
    errors = Column(Text, default="[]")  # JSON list string fallback

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def init_db_schema():
    Base.metadata.create_all(bind=engine)
