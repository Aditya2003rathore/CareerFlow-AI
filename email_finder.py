import requests
import urllib.parse
from bs4 import BeautifulSoup
import re

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
}

def clean_company_name(company: str) -> str:
    """
    Cleans company names from suffixes like Inc, Corp, LLC.
    """
    comp = company.lower()
    for suffix in [" inc.", " inc", " corp.", " corp", " llc", " co.", " co", " ltd.", " ltd"]:
        if comp.endswith(suffix):
            comp = comp[:-len(suffix)].strip()
    return comp.strip()

def find_company_domain(company_name: str) -> str:
    """
    Searches DuckDuckGo to find the official website/domain of a company.
    E.g. "Google" -> "google.com"
    """
    cleaned_name = clean_company_name(company_name)
    if not cleaned_name:
        return ""
    
    # Try a simple guess first
    simple_guess = re.sub(r'[^a-z0-9]', '', cleaned_name.lower()) + ".com"
    
    # Do a quick DDG search to find the official website
    query = f'"{cleaned_name}" official website'
    encoded_query = urllib.parse.quote_plus(query)
    url = f"https://html.duckduckgo.com/html/?q={encoded_query}"
    
    try:
        response = requests.get(url, headers=HEADERS, timeout=8)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            results = soup.find_all('a', class_='result__url')
            for r in results:
                raw_link = r.get('href', '').strip()
                # Parse link from DDG redirect if needed
                parsed_link = urllib.parse.urlparse(raw_link)
                if parsed_link.path == '/l/':
                    query_params = urllib.parse.parse_qs(parsed_link.query)
                    real_url = query_params.get('uddg', [''])[0]
                else:
                    real_url = raw_link
                
                domain_match = urllib.parse.urlparse(real_url).netloc
                # Remove www.
                if domain_match.startswith("www."):
                    domain_match = domain_match[4:]
                
                # Filter out search engines, social media, directory sites
                ignore_domains = [
                    "linkedin.com", "facebook.com", "twitter.com", "wikipedia.org", 
                    "youtube.com", "instagram.com", "crunchbase.com", "glassdoor.com", 
                    "duckduckgo.com", "google.com", "yahoo.com"
                ]
                
                if domain_match and not any(d in domain_match for d in ignore_domains):
                    return domain_match
                    
        return simple_guess
    except Exception as e:
        print(f"Error resolving domain for {company_name}: {str(e)}")
        return simple_guess

def guess_email_patterns(first_name: str, last_name: str, domain: str) -> list:
    """
    Generates a list of common corporate email address patterns.
    """
    fn = first_name.lower().strip()
    ln = last_name.lower().strip()
    dom = domain.lower().strip()
    
    if not fn or not dom:
        return []
    
    patterns = []
    
    # 1. first.last@domain.com (most common in modern tech, e.g. Stripe, Google)
    if ln:
        patterns.append(f"{fn}.{ln}@{dom}")
    # 2. first_initial + last@domain.com (very common, e.g. jdoe@domain.com)
    if ln:
        patterns.append(f"{fn[0]}{ln}@{dom}")
    # 3. first@domain.com (common in startups, e.g. john@domain.com)
    patterns.append(f"{fn}@{dom}")
    # 4. first.last_initial@domain.com (e.g. john.d@domain.com)
    if ln:
        patterns.append(f"{fn}.{ln[0]}@{dom}")
    # 5. first + last@domain.com (e.g. johndoe@domain.com)
    if ln:
        patterns.append(f"{fn}{ln}@{dom}")
        
    return patterns

def resolve_email(first_name: str, last_name: str, company_name: str, hunter_api_key: str = "") -> dict:
    """
    Attempts to find the recruiter's email.
    Uses Hunter.io API if API key is provided.
    Falls back to finding company domain and guessing patterns.
    """
    fn = first_name.strip()
    ln = last_name.strip()
    
    # Clean up names (remove middle initials or emojis)
    fn = fn.split()[0] if fn else ""
    ln = ln.split()[-1] if ln else ""
    
    domain = find_company_domain(company_name)
    
    if not domain:
        return {
            "email": "",
            "method": "failed",
            "score": 0,
            "all_guesses": []
        }
        
    # Method 1: Hunter.io API (if API Key provided)
    if hunter_api_key:
        url = f"https://api.hunter.io/v2/email-finder?domain={domain}&first_name={fn}&last_name={ln}&api_key={hunter_api_key}"
        try:
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                data = response.json().get("data", {})
                email = data.get("email")
                score = data.get("score", 0)
                if email:
                    return {
                        "email": email,
                        "method": "Hunter.io API",
                        "score": score,
                        "all_guesses": [email]
                    }
        except Exception as e:
            print(f"Hunter.io API error: {str(e)}")
            
    # Method 2: Guessing patterns (Zero cost fallback)
    guesses = guess_email_patterns(fn, ln, domain)
    primary_email = guesses[0] if guesses else ""
    
    return {
        "email": primary_email,
        "method": "Pattern Guesser (AI Guess)",
        "score": 50, # Arbitrary medium confidence
        "all_guesses": guesses
    }
