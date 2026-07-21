import requests
import html

DEFAULT_COMPANIES = [
    "openai", "stripe", "airbnb", "vercel", "figma", "hashicorp", "reddit", 
    "pinterest", "cloudflare", "uber", "cockroachlabs", "flexport", "ramp", "temporal"
]

def clean_html(html_text: str) -> str:
    """Simple HTML tag stripper to get clean text for the description."""
    if not html_text:
        return ""
    import re
    # Remove HTML tags
    clean = re.sub(r'<[^>]+>', ' ', html_text)
    # Decode HTML entities
    clean = html.unescape(clean)
    # Normalize whitespace
    clean = re.sub(r'\s+', ' ', clean)
    return clean.strip()

def fetch_jobs(companies: list = None) -> list:
    """
    Fetches job postings from Greenhouse API boards for specified company slugs.
    """
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
                    # Parse location
                    loc = rj.get("location", {})
                    location_str = loc.get("name", "Remote / Headless") if isinstance(loc, dict) else str(loc)
                    
                    # Clean description
                    raw_desc = rj.get("content", "")
                    clean_desc = clean_html(raw_desc)
                    
                    # Normalize job data
                    jobs.append({
                        "id": f"greenhouse-{company}-{rj.get('id')}",
                        "title": rj.get("title", "").strip(),
                        "company": company.capitalize(),
                        "location": location_str,
                        "salary": "Not specified",  # Greenhouse API doesn't have a standard salary field
                        "url": rj.get("absolute_url", ""),
                        "description": clean_desc,
                        "skills": [],  # Will be populated later or left empty for prompt matching
                        "source": "Greenhouse",
                        "posted_date": rj.get("updated_at", "")
                    })
        except Exception as e:
            print(f"Error fetching Greenhouse jobs for company '{company}': {str(e)}")
            
    return jobs
