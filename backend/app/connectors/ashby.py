import requests
from backend.app.connectors.greenhouse import clean_html

DEFAULT_COMPANIES = [
    "concept2", "linear", "retool", "dbt", "vercel", "notion", "lattice", 
    "temporal", "levels", "fly", "multiverse", "sanity"
]

def fetch_jobs(companies: list = None) -> list:
    """Fetches and normalizes job openings from Ashby boards."""
    if not companies:
        companies = DEFAULT_COMPANIES
        
    jobs = []
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    for company in companies:
        company = company.strip().lower()
        if not company:
            continue
            
        url = f"https://api.ashbyhq.com/v1/org/{company}/postings"
        try:
            response = requests.get(url, headers=headers, timeout=10)
            if response.status_code == 200:
                data = response.json()
                results = data.get("results", [])
                for rj in results:
                    desc_parts = []
                    info = rj.get("info", "")
                    if info:
                        desc_parts.append(clean_html(info))
                        
                    sections = rj.get("descriptionHtmlSections", [])
                    if isinstance(sections, list):
                        for sec in sections:
                            title = sec.get("title", "")
                            body = sec.get("body", "")
                            if title:
                                desc_parts.append(f"\n{title}:")
                            if body:
                                desc_parts.append(clean_html(body))
                                
                    jobs.append({
                        "id": f"ashby-{company}-{rj.get('id')}",
                        "title": rj.get("title", "").strip(),
                        "company": company.capitalize(),
                        "location": rj.get("location", "Remote"),
                        "salary": "Not specified",
                        "url": rj.get("jobBoardUrl", ""),
                        "description": "\n".join(desc_parts).strip(),
                        "skills": [],
                        "source": "Ashby",
                        "posted_date": rj.get("publishedAt", "")
                    })
        except Exception as e:
            print(f"Ashby sync error for '{company}': {str(e)}")
            
    return jobs
