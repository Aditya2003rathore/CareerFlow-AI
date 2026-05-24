from google import genai
from google.genai import types
import json

def generate_outreach_email(
    resume_text: str,
    recruiter_name: str,
    recruiter_title: str,
    company: str,
    job_desc: str,
    api_key: str,
    custom_instruction: str = ""
) -> dict:
    """
    Generates a personalized recruiter outreach email using Gemini.
    Returns a dictionary with 'subject' and 'body'.
    Uses the new google-genai SDK.
    """
    if not api_key:
        raise ValueError("Gemini API key is required.")
        
    from ats_analyzer import resolve_available_model
    client = genai.Client(api_key=api_key)
    selected_model = resolve_available_model(api_key)
    
    candidates_to_try = [selected_model]
    priority_fallbacks = [
        "gemini-1.5-flash",
        "gemini-1.5-flash-latest",
        "gemini-2.0-flash",
        "gemini-1.5-pro",
        "gemini-pro"
    ]
    for c in priority_fallbacks:
        if c not in candidates_to_try:
            candidates_to_try.append(c)
            
    # Clean inputs
    r_name = recruiter_name.strip() if recruiter_name else "Hiring Manager"
    r_title = recruiter_title.strip() if recruiter_title else "Recruiter"
    comp = company.strip()
    
    # If no job description is specified, assume a generic title
    job = job_desc.strip() if job_desc else "open positions"

    prompt = f"""
You are a career consultant and expert copywriter specializing in technical recruiter outreach.
Write a highly personalized, compelling, and professional cold email to a recruiter on behalf of a job seeker.

Target Recruiter:
- Name: {r_name}
- Title: {r_title}
- Company: {comp}

Target Role / Job Description:
{job}

Candidate's Resume Text:
{resume_text}

Guidelines for the email:
1. **Subject Line**: Write a short, high-open-rate subject line (e.g. "Software Engineer Role - [Candidate Name]" or similar, personalized to {comp}).
2. **Greeting**: Use a professional greeting. If name is "Hiring Manager" or "Unknown Recruiter", use "Hi there," or "Dear Hiring Team,".
3. **Hook**: Start by mentioning the recruiter's work or the company's recent achievements/vision. Keep it brief.
4. **Value Proposition**: Connect 2-3 specific achievements or skills from the candidate's resume that directly align with the target role. Do not list everything; highlight only the most impressive matches.
5. **Length**: Keep the email short and punchy (120-180 words). Recruiter attention spans are short!
6. **Call to Action (CTA)**: Ask for a brief 10-minute call or suggest a follow-up. Mention that the resume is attached.
7. **Placeholder**: Leave a clear placeholder for the Candidate's Name (e.g., [My Name]) at the end, or use the name found at the top of the resume.

Custom Instructions (incorporate if provided):
{custom_instruction}

You must return the response in JSON format with these exact keys:
- "subject": The subject line of the email.
- "body": The full body of the email.
"""

    for model_name in candidates_to_try:
        try:
            response = client.models.generate_content(
                model=model_name,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json"
                )
            )
            
            result = json.loads(response.text)
            if "subject" not in result or "body" not in result:
                raise KeyError("JSON response missing required keys")
                
            return result
        except Exception as e:
            print(f"Draft generation failed with model {model_name}: {str(e)}")
            continue
            
    # Fallback template if all models failed
    return {
        "subject": f"Inquiry: Job Opportunities at {comp}",
        "body": f"Dear {r_name},\n\nI hope this email finds you well.\n\nI am reaching out because I am highly interested in opportunities at {comp} as a candidate matching your requirements. I have attached my resume for your review.\n\nI would welcome the opportunity to discuss how my background aligns with your hiring needs.\n\nBest regards,\n[My Name]"
    }
