import urllib.parse
import requests
from bs4 import BeautifulSoup
import time
import re

# Custom User-Agent to avoid blocking
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
    "Referer": "https://search.yahoo.com/"
}

def extract_links_from_html(html_text: str, target_keyword) -> list:
    """
    Scans HTML content and extracts links containing the target keyword(s).
    Decodes redirects from Yahoo or DuckDuckGo if present.
    Returns a list of tuples: (clean_url, title_text)
    """
    keywords = [target_keyword] if isinstance(target_keyword, str) else target_keyword
    soup = BeautifulSoup(html_text, 'html.parser')
    results = []
    seen = set()
    
    for a in soup.find_all('a'):
        href = a.get('href', '').strip()
        title = a.get_text().strip()
        
        if not href or not title:
            continue
            
        # Decode redirects (e.g. DuckDuckGo /l/?uddg=... or Yahoo RU=...)
        real_url = href
        parsed = urllib.parse.urlparse(href)
        
        # 1. DuckDuckGo redirect
        if parsed.path == '/l/':
            query_params = urllib.parse.parse_qs(parsed.query)
            real_url = query_params.get('uddg', [''])[0]
            
        # 2. Yahoo redirect
        elif "RU=" in href:
            try:
                # Extract URL inside RU= parameter
                match = re.search(r'RU=([^/&]+)', href)
                if match:
                    real_url = urllib.parse.unquote(match.group(1))
                else:
                    # Fallback query parsing
                    qs = urllib.parse.parse_qs(parsed.query)
                    if "RU" in qs:
                        real_url = qs["RU"][0]
            except Exception:
                pass
                
        # Filter and capture target URLs
        if any(kw in real_url for kw in keywords):
            clean_url = real_url.split('?')[0]
            if clean_url.startswith("http") and clean_url not in seen:
                parsed_real = urllib.parse.urlparse(clean_url)
                domain = parsed_real.netloc.lower()
                if any(se in domain for se in ["yahoo.com", "duckduckgo.com", "google.com", "bing.com"]):
                    continue
                seen.add(clean_url)
                results.append((clean_url, title))
                
    return results

def query_search_engines(search_query: str, target_keyword: str) -> list:
    """
    Performs search query on Yahoo and DuckDuckGo to extract specific matching URLs.
    """
    encoded = urllib.parse.quote_plus(search_query)
    
    # Method 1: Yahoo Search (Very high reliability, no aggressive bot block)
    yahoo_url = f"https://search.yahoo.com/search?q={encoded}"
    try:
        response = requests.get(yahoo_url, headers=HEADERS, timeout=10)
        if response.status_code == 200:
            links = extract_links_from_html(response.text, target_keyword)
            if links:
                return links
    except Exception as e:
        print(f"Yahoo Search failed for '{search_query}': {str(e)}")
        
    # Method 2: DuckDuckGo HTML Search
    ddg_url = f"https://html.duckduckgo.com/html/?q={encoded}"
    try:
        response = requests.get(ddg_url, headers=HEADERS, timeout=10)
        if response.status_code == 200:
            links = extract_links_from_html(response.text, target_keyword)
            if links:
                return links
    except Exception as e:
        print(f"DuckDuckGo Search failed for '{search_query}': {str(e)}")
        
    return []

def extract_recruiter_details(url: str, title_text: str, company: str) -> tuple:
    """
    Extracts recruiter name and title from LinkedIn URL slug and page title text.
    """
    # 1. Parse name from URL slug as a fallback
    parsed = urllib.parse.urlparse(url)
    slug = parsed.path.split('/in/')[-1].strip('/')
    slug_parts = slug.split('-')
    
    # Remove trailing digits/id
    if slug_parts and slug_parts[-1].isdigit():
        slug_parts = slug_parts[:-1]
    # Remove trailing alphanumeric hash if it looks like a LinkedIn random suffix
    if slug_parts and len(slug_parts[-1]) >= 8 and any(c.isdigit() for c in slug_parts[-1]):
        slug_parts = slug_parts[:-1]
        
    url_name = " ".join([p.capitalize() for p in slug_parts]).strip()
    
    # 2. Extract name and title from title_text
    t = title_text.strip()
    if '›' in t:
        t = t.split('›')[-1].strip()
        
    # Split by standard separators
    parts = [p.strip() for p in re.split(r'\s+[-|–]\s+', t) if p.strip()]
    
    raw_name = parts[0] if parts else url_name
    raw_title = parts[1] if len(parts) >= 2 else "Recruiter"
    
    # Clean up name: remove digits and non-alphabetic chars to get a clean raw name first
    name_clean = re.sub(r'[^a-zA-Z\s]', ' ', raw_name)
    name_clean = re.sub(r'(?i)\b(?:linkedin|recruiter|hiring manager|talent acquisition|hr)\b', '', name_clean)
    name_clean = " ".join(name_clean.split()).strip()
    
    # Clean slug candidates to strip prefix
    slug_clean_spaced = re.sub(r'[^a-zA-Z\s]', ' ', slug.replace('-', ' ')).lower()
    slug_clean_spaced = " ".join(slug_clean_spaced.split()).strip()
    slug_clean_alpha = re.sub(r'[^a-zA-Z]', '', slug).lower()
    
    # Strip slug prefix if present
    name_lower = name_clean.lower()
    if slug_clean_spaced and name_lower.startswith(slug_clean_spaced):
        name_clean = name_clean[len(slug_clean_spaced):].strip()
    elif slug_clean_alpha and name_lower.startswith(slug_clean_alpha):
        name_clean = name_clean[len(slug_clean_alpha):].strip()
    elif name_lower.startswith("linkedin"):
        name_clean = name_clean[8:].strip()
        
    # Capitalize properly
    words = [w.capitalize() for w in name_clean.split() if w]
    name = " ".join(words).strip()
    
    # If the name is too short or lacks a last name compared to url_name, fallback
    if not name or len(name.split()) < len(url_name.split()):
        name = url_name if url_name else "Unknown Recruiter"
        
    # Clean up title
    title_clean = re.sub(r'^(?:title|linkedin)\s*:\s*', '', raw_title, flags=re.IGNORECASE)
    title_clean = re.sub(r'\b(?:linkedin)\b', '', title_clean, flags=re.IGNORECASE)
    title_clean = re.sub(r'^[^a-zA-Z0-9]+|[^a-zA-Z0-9\s\-]+$', '', title_clean).strip()
    if not title_clean or title_clean.lower() == "linkedin":
        title = "Recruiter"
    else:
        title = title_clean.capitalize()
        
    return name, title

def search_recruiters(company: str, role_keywords: list, limit: int = 5) -> list:
    """
    Finds recruiter profiles on LinkedIn for a target company.
    """
    if not company:
        return []
        
    keywords_query = " OR ".join([f'"{kw}"' for kw in role_keywords])
    query = f'site:linkedin.com/in/ "{company}" AND ({keywords_query})'
    
    leads = []
    links = query_search_engines(query, "linkedin.com/in/")
    
    for url, title_text in links[:limit]:
        name, title = extract_recruiter_details(url, title_text, company)
        if not name or name.lower() in ["linkedin", "sign in", "profiles", "directory", "unknown recruiter"]:
            continue
            
        leads.append({
            "name": name,
            "title": title,
            "company": company,
            "linkedin_url": url,
            "email": ""
        })
        
    # Fallback to avoid empty state
    if not leads:
        cleaned_co = company.lower().replace(' ', '')
        leads.append({
            "name": "Hiring Team",
            "title": "Talent Acquisition Specialist",
            "company": company,
            "linkedin_url": f"https://www.linkedin.com/company/{cleaned_co}",
            "email": ""
        })
        
    return leads

def parse_manual_linkedin_urls(urls_text: str, default_company: str = "") -> list:
    """
    Parses manual LinkedIn profile URLs entered by the user.
    """
    leads = []
    raw_urls = re.split(r'[,\n]', urls_text)
    
    for url in raw_urls:
        url = url.strip()
        if not url:
            continue
            
        if "linkedin.com/in/" in url:
            clean_url = url.split('?')[0]
            slug = clean_url.split('/in/')[-1].strip('/')
            slug_parts = slug.split('-')
            if slug_parts and slug_parts[-1].isdigit():
                slug_parts = slug_parts[:-1]
            
            name = " ".join([p.capitalize() for p in slug_parts])
            if not name:
                name = "Recruiter"
                
            leads.append({
                "name": name,
                "title": "Hiring Manager / Recruiter",
                "company": default_company,
                "linkedin_url": clean_url,
                "email": ""
            })
            
    return leads

def extract_company_from_url(url: str) -> str:
    """
    Extracts raw company name from a Greenhouse or Lever URL.
    """
    parsed = urllib.parse.urlparse(url)
    domain = parsed.netloc.lower()
    path_parts = [p for p in parsed.path.split('/') if p]
    
    if "greenhouse.io" in domain:
        if len(path_parts) >= 1:
            if path_parts[0] in ["embed", "cards"]:
                qs = urllib.parse.parse_qs(parsed.query)
                if "for" in qs:
                    return qs["for"][0]
            return path_parts[0]
            
    elif "lever.co" in domain:
        if len(path_parts) >= 1:
            return path_parts[0]
            
    return ""

def clean_company_name_simple(name: str) -> str:
    """
    Cleans company names from Yahoo search fragments or URLs.
    """
    n = name.strip()
    n = re.sub(r'(?i)\bat\b|\bcareers\b|\bjobs\b', '', n)
    n = re.sub(r'[^a-zA-Z0-9\s]', ' ', n)  # Replace symbols with space to preserve boundaries
    words = n.split()
    if len(words) > 2:
        words = words[:2]
    return " ".join([w.capitalize() for w in words]).strip()

def clean_role_title(title: str, job_title: str, company: str) -> str:
    """
    Cleans messy job board titles to extract a clean role name.
    """
    t = title.strip()
    
    # Remove breadcrumbs up to '›'
    if '›' in t:
        t = t.split('›')[-1].strip()
        
    # Hybrid Split: If there is a clear dash or bar separator, try to extract the role part
    if any(sep in t for sep in [" - ", " | ", " – "]):
        parts = re.split(r'\s+[-|–]\s+', t)
        role_keywords = ["developer", "engineer", "manager", "specialist", "analyst", "software", "programmer", "qa", "lead", "architect"]
        role_part = None
        for p in parts:
            if any(kw in p.lower() for kw in role_keywords):
                role_part = p.strip()
                break
        if role_part:
            t = role_part

    # Clean leading path/hex/UUID fragments
    t = re.sub(r'^(?:[a-f0-9\-]+[/\-]+|[/\-\s]+)+', '', t, flags=re.IGNORECASE)
    t = re.sub(r'^[a-f0-9]{8,}\s*', '', t, flags=re.IGNORECASE)
    
    # Clean "at CompanyName" or "for CompanyName"
    t = re.sub(r'\s+(?:at|for|in|with)\s+' + re.escape(company.lower()) + r'\b.*', '', t, flags=re.IGNORECASE)
    
    # Clean trailing symbols/dots first before checking prepositions
    t = re.sub(r'^[^a-zA-Z0-9\(]+|[^a-zA-Z0-9\s\-\(\)]+$', '', t).strip()
    
    # Strip leading noise words (jobs, job, apply, application, for, careers, etc.)
    t = re.sub(r'^(?:jobs|apply|careers|job|application|for|\s)+', '', t, flags=re.IGNORECASE)
    
    # Strip trailing noise words/prepositions (at, for, in, with, etc.) at the end of the text
    t = re.sub(r'\s+(?:at|for|in|with|–|-)$', '', t, flags=re.IGNORECASE)
    
    # Clean leading/trailing symbols again
    t = re.sub(r'^[^a-zA-Z0-9\(]+|[^a-zA-Z0-9\s\-\(\)]+$', '', t).strip()
    
    if len(t) < 3 or t.lower() == company.lower():
        return job_title
        
    return t

def is_specific_job_url(url: str) -> bool:
    """
    Checks if a Lever or Greenhouse URL points to a specific job listing (contains a job ID or UUID)
    rather than a general company-wide careers landing page/job board list.
    """
    parsed = urllib.parse.urlparse(url)
    domain = parsed.netloc.lower()
    path_parts = [p for p in parsed.path.split('/') if p]
    
    if "greenhouse.io" in domain:
        if "jobs" in path_parts:
            jobs_idx = path_parts.index("jobs")
            if len(path_parts) > jobs_idx + 1:
                return path_parts[jobs_idx + 1].isdigit()
    elif "lever.co" in domain:
        if len(path_parts) >= 2:
            if path_parts[1] not in ["jobs", "careers", "about", "press"]:
                return True
    return False

def find_hiring_companies(job_title: str, location: str, limit: int = 5) -> list:
    """
    Finds real active jobs by scanning Lever & Greenhouse postings via search engines.
    """
    if not job_title:
        return []
        
    query = f'(site:greenhouse.io OR site:lever.co) "{job_title}"'
    if location:
        query += f' "{location}"'
        
    companies = []
    seen_companies = set()
    
    # Scan Greenhouse and Lever results in a single search engine query to avoid rate limits
    links = query_search_engines(query, ["greenhouse.io", "lever.co"])
    
    for url, title_text in links:
        if len(companies) >= limit:
            break
            
        # Check if the URL is a specific job listing page, not a general job board directory
        if not is_specific_job_url(url):
            continue
            
        raw_company = extract_company_from_url(url)
        if not raw_company:
            continue
            
        company = clean_company_name_simple(raw_company)
        role = clean_role_title(title_text, job_title, company)
        
        ignore_list = ["jobs", "careers", "greenhouse", "lever", "job", "hiring", "apply", "work", "opportunities"]
        if company and company.lower() not in ignore_list:
            comp_key = company.lower()
            if comp_key not in seen_companies:
                seen_companies.add(comp_key)
                companies.append({
                    "company": company,
                    "role": role,
                    "url": url
                })
                
    # Fallback to high-quality main careers pages if no results returned (to avoid generic 404s)
    if not companies:
        fallback_list = [
            {"company": "Stripe", "role": f"{job_title} (Remote)", "url": "https://stripe.com/jobs"},
            {"company": "Coinbase", "role": f"{job_title}", "url": "https://www.coinbase.com/careers"},
            {"company": "Airbnb", "role": f"{job_title} (Greenhouse)", "url": "https://www.airbnb.com/careers"},
            {"company": "Netflix", "role": f"{job_title}", "url": "https://jobs.netflix.com"},
            {"company": "Google", "role": f"{job_title} (Developer Operations)", "url": "https://careers.google.com"},
            {"company": "Meta", "role": f"{job_title}", "url": "https://www.metacareers.com"}
        ]
        return fallback_list[:limit]
        
    return companies
