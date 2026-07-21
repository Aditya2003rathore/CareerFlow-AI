import requests
from connectors.greenhouse import clean_html

def fetch_jobs(limit: int = 50) -> list:
    """
    Fetches remote software development job postings from Remotive API.
    """
    jobs = []
    url = "https://remotive.com/api/remote-jobs?category=software-development"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=12)
        if response.status_code == 200:
            data = response.json()
            raw_jobs = data.get("jobs", [])
            for rj in raw_jobs[:limit]:
                job_id = rj.get("id")
                if not job_id:
                    continue
                    
                raw_desc = rj.get("description", "")
                clean_desc = clean_html(raw_desc)
                
                skills = rj.get("tags", [])
                if not isinstance(skills, list):
                    skills = []
                    
                salary = rj.get("salary", "Not specified")
                if not salary:
                    salary = "Not specified"
                    
                jobs.append({
                    "id": f"remotive-{job_id}",
                    "title": rj.get("title", "").strip(),
                    "company": rj.get("company_name", "").strip(),
                    "location": rj.get("candidate_required_location", "Remote"),
                    "salary": str(salary),
                    "url": rj.get("url", ""),
                    "description": clean_desc,
                    "skills": skills,
                    "source": "Remotive",
                    "posted_date": rj.get("publication_date", "")
                })
    except Exception as e:
        print(f"Error fetching Remotive jobs: {str(e)}")
        
    return jobs
