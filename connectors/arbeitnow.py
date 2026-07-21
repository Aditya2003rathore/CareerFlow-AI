import requests
from connectors.greenhouse import clean_html

def fetch_jobs(limit: int = 50) -> list:
    """
    Fetches job postings from the Arbeitnow API.
    """
    jobs = []
    url = "https://www.arbeitnow.com/api/job-board-api"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=12)
        if response.status_code == 200:
            data = response.json()
            raw_jobs = data.get("data", [])
            for rj in raw_jobs[:limit]:
                slug = rj.get("slug")
                if not slug:
                    continue
                    
                raw_desc = rj.get("description", "")
                clean_desc = clean_html(raw_desc)
                
                skills = rj.get("tags", [])
                if not isinstance(skills, list):
                    skills = []
                    
                jobs.append({
                    "id": f"arbeitnow-{slug}",
                    "title": rj.get("title", "").strip(),
                    "company": rj.get("company_name", "").strip(),
                    "location": rj.get("location", "Remote"),
                    "salary": "Not specified",
                    "url": rj.get("url", ""),
                    "description": clean_desc,
                    "skills": skills,
                    "source": "Arbeitnow",
                    "posted_date": str(rj.get("created_at", ""))
                })
    except Exception as e:
        print(f"Error fetching Arbeitnow jobs: {str(e)}")
        
    return jobs
