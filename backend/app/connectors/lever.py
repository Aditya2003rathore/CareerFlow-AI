import requests
from backend.app.connectors.greenhouse import clean_html

DEFAULT_COMPANIES = [
    "lever", "vercel", "figma", "bolt", "netflix", "openai", "ashby", "stripe", 
    "substack", "palantir", "replit", "scale", "clerk", "posthog"
]

def fetch_jobs(companies: list = None) -> list:
    """Fetches and normalizes job openings from Lever boards."""
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
            
        url = f"https://api.lever.co/v0/postings/{company}?mode=json"
        try:
            response = requests.get(url, headers=headers, timeout=10)
            if response.status_code == 200:
                raw_jobs = response.json()
                if not isinstance(raw_jobs, list):
                    continue
                    
                for rj in raw_jobs:
                    categories = rj.get("categories", {})
                    location_str = categories.get("location", "Remote")
                    
                    desc_list = []
                    description_html = rj.get("descriptionHtml", "")
                    if description_html:
                        desc_list.append(clean_html(description_html))
                    lists = rj.get("lists", [])
                    if isinstance(lists, list):
                        for lst in lists:
                            stitle = lst.get("text", "")
                            scontent = lst.get("content", "")
                            if stitle:
                                desc_list.append(f"\n{stitle}:")
                            if scontent:
                                desc_list.append(clean_html(scontent))
                                
                    additional = rj.get("additionalPlain", "")
                    if additional:
                        desc_list.append(f"\nAdditional Details:\n{additional}")
                        
                    jobs.append({
                        "id": f"lever-{company}-{rj.get('id')}",
                        "title": rj.get("title", "").strip(),
                        "company": company.capitalize(),
                        "location": location_str,
                        "salary": "Not specified",
                        "url": rj.get("hostedUrl", ""),
                        "description": "\n".join(desc_list).strip(),
                        "skills": [],
                        "source": "Lever",
                        "posted_date": str(rj.get("createdAt", ""))
                    })
        except Exception as e:
            print(f"Lever sync error for '{company}': {str(e)}")
            
    return jobs
