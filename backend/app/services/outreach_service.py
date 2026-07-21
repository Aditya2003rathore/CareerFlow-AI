import smtplib
import requests
import urllib.parse
import re
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from bs4 import BeautifulSoup
# Google genai removed in favor of LiteLLM in ai_service

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
}

def clean_company_name(company: str) -> str:
    comp = company.lower()
    for suffix in [" inc.", " inc", " corp.", " corp", " llc", " co.", " co", " ltd.", " ltd"]:
        if comp.endswith(suffix):
            comp = comp[:-len(suffix)].strip()
    return comp.strip()

def find_company_domain(company_name: str) -> str:
    """Queries search engine to find the domain for a company name."""
    cleaned_name = clean_company_name(company_name)
    if not cleaned_name:
        return ""
    
    simple_guess = re.sub(r'[^a-z0-9]', '', cleaned_name.lower()) + ".com"
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
                parsed_link = urllib.parse.urlparse(raw_link)
                if parsed_link.path == '/l/':
                    query_params = urllib.parse.parse_qs(parsed_link.query)
                    real_url = query_params.get('uddg', [''])[0]
                else:
                    real_url = raw_link
                
                domain_match = urllib.parse.urlparse(real_url).netloc
                if domain_match.startswith("www."):
                    domain_match = domain_match[4:]
                
                ignore_domains = [
                    "linkedin.com", "facebook.com", "twitter.com", "wikipedia.org", 
                    "youtube.com", "instagram.com", "crunchbase.com", "glassdoor.com", 
                    "duckduckgo.com", "google.com", "yahoo.com"
                ]
                
                if domain_match and not any(d in domain_match for d in ignore_domains):
                    return domain_match
        return simple_guess
    except Exception as e:
        print(f"Outreach domain lookup error for '{company_name}': {str(e)}")
        return simple_guess

def guess_email_patterns(first_name: str, last_name: str, domain: str) -> list:
    fn = first_name.lower().strip()
    ln = last_name.lower().strip()
    dom = domain.lower().strip()
    
    if not fn or not dom:
        return []
    
    patterns = []
    if ln:
        patterns.append(f"{fn}.{ln}@{dom}")
        patterns.append(f"{fn[0]}{ln}@{dom}")
    patterns.append(f"{fn}@{dom}")
    if ln:
        patterns.append(f"{fn}.{ln[0]}@{dom}")
        patterns.append(f"{fn}{ln}@{dom}")
    return patterns

def resolve_email(first_name: str, last_name: str, company_name: str, hunter_api_key: str = "") -> dict:
    """Attempts to find the recruiter's email via Hunter.io API or corporate patterns."""
    fn = first_name.strip()
    ln = last_name.strip()
    
    fn = fn.split()[0] if fn else ""
    ln = ln.split()[-1] if ln else ""
    
    domain = find_company_domain(company_name)
    if not domain:
        return {"email": "", "method": "failed", "score": 0, "all_guesses": []}
        
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
            
    guesses = guess_email_patterns(fn, ln, domain)
    primary_email = guesses[0] if guesses else ""
    return {
        "email": primary_email,
        "method": "Pattern Guesser",
        "score": 50,
        "all_guesses": guesses
    }

from backend.app.services.ai_service import get_ai_completion

def generate_outreach_email(
    resume_text: str,
    recruiter_name: str,
    recruiter_title: str,
    company: str,
    job_desc: str,
    api_key: str,
    custom_instruction: str = ""
) -> dict:
    """Generates outreach email draft using get_ai_completion."""
    if not api_key:
        raise ValueError("AI API key is required.")
        
    r_name = recruiter_name.strip() if recruiter_name else "Hiring Manager"
    r_title = recruiter_title.strip() if recruiter_title else "Recruiter"
    comp = company.strip()
    job = job_desc.strip() if job_desc else "open positions"

    prompt = f"""
    Write a highly personalized, compelling technical recruiter cold email on behalf of a job seeker.
    
    Target Recruiter:
    - Name: {r_name}
    - Title: {r_title}
    - Company: {comp}
    
    Target Role:
    {job}
    
    Candidate's Resume Text:
    {resume_text}
    
    Guidelines:
    1. Short, high-open-rate subject line.
    2. Professional greeting (e.g. "Hi {r_name},").
    3. Hook: brief mention of the company's recent tech context.
    4. Match alignment: highlight 2 core skills/achievements matching the job.
    5. Short and punchy (120-180 words).
    6. Include a placeholder for the sender name at the end (e.g. [My Name]).
    
    Custom Instructions: {custom_instruction}
    
    Return a JSON containing:
    - "subject": The subject line
    - "body": The email body
    """
    
    try:
        response_text = get_ai_completion(prompt, api_key, "gemini/gemini-1.5-flash")
        start_idx = response_text.find("{")
        end_idx = response_text.rfind("}") + 1
        json_str = response_text[start_idx:end_idx]
        return json.loads(json_str)
    except Exception as e:
        print(f"AI draft generation failed: {str(e)}")
        return {
            "subject": f"Inquiry: Career Opportunities at {comp}",
            "body": f"Dear {r_name},\n\nI hope you are doing well.\n\nI am reaching out to express my interest in joining {comp}. I have attached my resume for review.\n\nBest regards,\n[My Name]"
        }

def send_outreach_email(
    sender_email: str,
    sender_password: str,
    recipient_email: str,
    subject: str,
    body: str,
    resume_bytes: bytes,
    resume_filename: str = "Resume.pdf",
    smtp_server: str = "smtp.gmail.com",
    smtp_port: int = 587
) -> bool:
    """Sends a PDF resume attachment to a recruiter via SMTP."""
    if not sender_email or not sender_password or not recipient_email:
        raise ValueError("SMTP Credentials and Recipient are required.")
        
    try:
        msg = MIMEMultipart()
        msg['From'] = sender_email
        msg['To'] = recipient_email
        msg['Subject'] = subject
        msg.attach(MIMEText(body, 'plain'))
        
        part = MIMEBase('application', 'octet-stream')
        part.set_payload(resume_bytes)
        encoders.encode_base64(part)
        part.add_header('Content-Disposition', f'attachment; filename="{resume_filename}"')
        msg.attach(part)
        
        server = smtplib.SMTP(smtp_server, smtp_port)
        server.starttls()
        server.login(sender_email, sender_password)
        server.sendmail(sender_email, recipient_email, msg.as_string())
        server.quit()
        return True
    except Exception as e:
        print(f"SMTP Outreach failed: {str(e)}")
        raise e
