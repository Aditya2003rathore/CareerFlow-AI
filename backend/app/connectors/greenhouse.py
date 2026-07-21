import requests
import html
import re

DEFAULT_COMPANIES = [
    "openai", "stripe", "airbnb", "vercel", "figma", "hashicorp", "reddit", 
    "pinterest", "cloudflare", "uber", "cockroachlabs", "flexport", "ramp", "temporal"
]

def clean_html(html_text: str) -> str:
    """Strips HTML tags and decodes entities to normalize job description text."""
    if not html_text:
        return ""
    clean = re.sub(r'<[^>]+>', ' ', html_text)
    clean = html.unescape(clean)
    clean = re.sub(r'\s+', ' ', clean)
    return clean.strip()

def fetch_jobs(companies: list = None) -> list:
    """Fetches and normalizes job openings from Greenhouse boards."""
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
            
        url = f"https://boards-api.greenhouse.io/v1/boards/{company}/jobs?content=true"
        try:
            response = requests.get(url, headers=headers, timeout=10)
            if response.status_code == 200:
                data = response.json()
                raw_jobs = data.get("jobs", [])
                for rj in raw_jobs:
                    loc = rj.get("location", {})
                    location_str = loc.get("name", "Remote") if isinstance(loc, dict) else str(loc)
                    
                    jobs.append({
                        "id": f"greenhouse-{company}-{rj.get('id')}",
                        "title": rj.get("title", "").strip(),
                        "company": company.capitalize(),
                        "location": location_str,
                        "salary": "Not specified",
                        "url": rj.get("absolute_url", ""),
                        "description": clean_html(rj.get("content", "")),
                        "skills": [],
                        "source": "Greenhouse",
                        "posted_date": rj.get("updated_at", "")
                    })
        except Exception as e:
            print(f"Greenhouse sync error for '{company}': {str(e)}")
            
    return jobs
