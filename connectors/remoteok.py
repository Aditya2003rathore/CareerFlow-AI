import requests
from connectors.greenhouse import clean_html

def fetch_jobs(limit: int = 50) -> list:
    """
    Fetches job postings from the RemoteOK public API.
    """
    jobs = []
    url = "https://remoteok.com/api"
    headers = {
        # RemoteOK is sensitive to User-Agent
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/json"
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=12)
        if response.status_code == 200:
            data = response.json()
            if not isinstance(data, list):
                return []
                
            # First item is a legal notice/disclaimer, skip it
            for rj in data[1:limit+1]:
                if not isinstance(rj, dict):
                    continue
                    
                job_id = rj.get("id")
                if not job_id:
                    continue
                    
                # Clean descriptions (description is often HTML format)
                raw_desc = rj.get("description", "")
                clean_desc = clean_html(raw_desc)
                
                # Fetch skills/tags
                skills = rj.get("tags", [])
                if not isinstance(skills, list):
                    skills = []
                
                # Extract salary info
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
                    "description": clean_desc,
                    "skills": skills,
                    "source": "RemoteOK",
                    "posted_date": rj.get("date", "")
                })
    except Exception as e:
        print(f"Error fetching RemoteOK jobs: {str(e)}")
        
    return jobs
