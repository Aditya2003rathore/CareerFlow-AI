import requests
from backend.app.connectors.greenhouse import clean_html

def fetch_jobs(limit: int = 50) -> list:
    """Fetches job listings from RemoteOK API."""
    jobs = []
    url = "https://remoteok.com/api"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/json"
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=12)
        if response.status_code == 200:
            data = response.json()
            if not isinstance(data, list):
                return []
                
            for rj in data[1:limit+1]:
                if not isinstance(rj, dict):
                    continue
                    
                job_id = rj.get("id")
                if not job_id:
                    continue
                    
                skills = rj.get("tags", [])
                if not isinstance(skills, list):
                    skills = []
                
                salary = rj.get("salary", "Not specified")
                if isinstance(salary, list):
                    salary = " - ".join([str(s) for s in salary])
                elif not salary:
                    salary = "Not specified"
                    
                jobs.append({
                    "id": f"remoteok-{job_id}",
                    "title": rj.get("position", "").strip(),
                    "company": rj.get("company", "").strip(),
                    "location": rj.get("location", "Remote"),
                    "salary": str(salary),
                    "url": rj.get("url", ""),
                    "description": clean_html(rj.get("description", "")),
                    "skills": skills,
                    "source": "RemoteOK",
                    "posted_date": rj.get("date", "")
                })
    except Exception as e:
        print(f"RemoteOK sync error: {str(e)}")
        
    return jobs
