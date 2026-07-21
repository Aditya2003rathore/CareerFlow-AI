import sqlite3
import os
import json
from datetime import datetime, timedelta

DB_FILE = "jobs.db"

def get_db_connection():
    """Returns a connection to the SQLite database with row factory enabled."""
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Initializes the database schema if it doesn't already exist."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS jobs (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            company TEXT NOT NULL,
            location TEXT,
            salary TEXT,
            url TEXT UNIQUE,
            description TEXT,
            skills TEXT, -- stored as JSON string
            source TEXT,
            posted_date TEXT,
            imported_at TEXT NOT NULL
        )
    """)
    conn.commit()
    conn.close()
    print("SQLite Database initialized successfully.")

def store_jobs(jobs: list):
    """
    Inserts or updates a list of normalized job dictionaries into the database.
    """
    if not jobs:
        return
        
    init_db()
    conn = get_db_connection()
    cursor = conn.cursor()
    
    imported_at = datetime.now().isoformat()
    
    inserted_count = 0
    for job in jobs:
        skills_json = json.dumps(job.get("skills", []))
        try:
            cursor.execute("""
                INSERT INTO jobs (
                    id, title, company, location, salary, url, description, skills, source, posted_date, imported_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    title=excluded.title,
                    company=excluded.company,
                    location=excluded.location,
                    salary=excluded.salary,
                    url=excluded.url,
                    description=excluded.description,
                    skills=excluded.skills,
                    source=excluded.source,
                    posted_date=excluded.posted_date,
                    imported_at=excluded.imported_at
            """, (
                job.get("id"),
                job.get("title", ""),
                job.get("company", ""),
                job.get("location", ""),
                job.get("salary", "Not specified"),
                job.get("url", ""),
                job.get("description", ""),
                skills_json,
                job.get("source", ""),
                job.get("posted_date", ""),
                imported_at
            ))
            inserted_count += 1
        except Exception as e:
            # Handle potential duplicate URL constraint or other SQLite errors gracefully
            print(f"Skipping job insertion for '{job.get('title')}' at '{job.get('company')}': {str(e)}")
            continue
            
    conn.commit()
    conn.close()
    print(f"Successfully stored/updated {inserted_count} jobs in the local SQLite cache.")

def search_jobs(keywords: str = "", location: str = "", source: str = "All", limit: int = 100) -> list:
    """
    Queries jobs stored in SQLite using SQL filters.
    """
    init_db()
    conn = get_db_connection()
    cursor = conn.cursor()
    
    query = "SELECT * FROM jobs WHERE 1=1"
    params = []
    
    if keywords.strip():
        # Split keywords to allow multi-word searches (e.g. "python developer")
        keyword_parts = keywords.strip().split()
        for part in keyword_parts:
            query += " AND (title LIKE ? OR description LIKE ?)"
            params.extend([f"%{part}%", f"%{part}%"])
            
    if location.strip():
        # Allow multi-word location (e.g. "New York")
        query += " AND (location LIKE ?)"
        params.append(f"%{location.strip()}%")
        
    if source and source != "All":
        query += " AND source = ?"
        params.append(source)
        
    query += " ORDER BY imported_at DESC LIMIT ?"
    params.append(limit)
    
    try:
        cursor.execute(query, params)
        rows = cursor.fetchall()
        
        results = []
        for row in rows:
            # Parse skills back to list
            try:
                skills_list = json.loads(row["skills"])
            except Exception:
                skills_list = []
                
            results.append({
                "id": row["id"],
                "title": row["title"],
                "company": row["company"],
                "location": row["location"],
                "salary": row["salary"],
                "url": row["url"],
                "description": row["description"],
                "skills": skills_list,
                "source": row["source"],
                "posted_date": row["posted_date"]
            })
        return results
    except Exception as e:
        print(f"Search query failed: {str(e)}")
        return []
    finally:
        conn.close()

def clear_old_jobs(days: int = 30):
    """Deletes jobs imported more than `days` ago to manage space."""
    init_db()
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cutoff_date = (datetime.now() - timedelta(days=days)).isoformat()
    try:
        cursor.execute("DELETE FROM jobs WHERE imported_at < ?", (cutoff_date,))
        conn.commit()
        print(f"Purged cached jobs older than {days} days.")
    except Exception as e:
        print(f"Failed to clear old jobs: {str(e)}")
    finally:
        conn.close()

def get_job_stats() -> dict:
    """Returns total job counts and counts by source in the database."""
    init_db()
    conn = get_db_connection()
    cursor = conn.cursor()
    
    stats = {"total": 0, "sources": {}}
    try:
        cursor.execute("SELECT COUNT(*) as total FROM jobs")
        stats["total"] = cursor.fetchone()["total"]
        
        cursor.execute("SELECT source, COUNT(*) as count FROM jobs GROUP BY source")
        for row in cursor.fetchall():
            stats["sources"][row["source"]] = row["count"]
    except Exception as e:
        print(f"Failed to fetch job statistics: {str(e)}")
    finally:
        conn.close()
    return stats
