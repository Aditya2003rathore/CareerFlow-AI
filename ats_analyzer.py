import json
from pypdf import PdfReader
from google import genai
from google.genai import types
import io

def extract_text_from_pdf(pdf_file) -> str:
    """
    Extracts all text from a PDF file-like object.
    """
    try:
        reader = PdfReader(pdf_file)
        text = ""
        for page in reader.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text + "\n"
        return text.strip()
    except Exception as e:
        raise ValueError(f"Failed to extract text from PDF: {str(e)}")

def resolve_available_model(api_key: str) -> str:
    """
    Dynamically queries available models for the given API key to select a supported option.
    Uses the new google-genai SDK.
    """
    try:
        client = genai.Client(api_key=api_key)
        available_models = [m.name for m in client.models.list()]
        
        priority_list = [
            "gemini-2.5-flash",
            "gemini-1.5-flash",
            "gemini-1.5-flash-latest",
            "gemini-2.0-flash",
            "gemini-1.5-pro",
            "gemini-pro"
        ]
        for candidate in priority_list:
            if any(candidate in m for m in available_models):
                return candidate
                
        for m in available_models:
            if "gemini" in m:
                return m.split('/')[-1]
    except Exception as e:
        print(f"Error querying Gemini models: {str(e)}")
    return "gemini-1.5-flash"

def parse_resume_profile(resume_text: str, api_key: str) -> dict:
    """
    Parses raw resume text into a structured JSON profile using Gemini.
    This runs once upon upload to build a clean profile for fast, cheap matching.
    """
    if not api_key:
        raise ValueError("Gemini API key is required.")
    if not resume_text.strip():
        raise ValueError("Resume text is empty.")
        
    client = genai.Client(api_key=api_key)
    selected_model = resolve_available_model(api_key)
    
    prompt = f"""
    You are an expert ATS parser and resume parser.
    Extract candidate information from the Resume Text below and format it into a valid JSON object.
    
    The JSON object must contain these exact keys:
    1. "name": The full name of the candidate.
    2. "email": Candidate's email address.
    3. "phone": Candidate's phone number.
    4. "location": Candidate's current location/city (if specified).
    5. "linkedin": Candidate's LinkedIn profile URL.
    6. "github": Candidate's GitHub profile URL.
    7. "portfolio": Candidate's portfolio website URL.
    8. "skills": A clean list of core technical skills/keywords (e.g. ["Python", "FastAPI", "Docker", "AWS", "Git"]).
    9. "summary": A brief 2-3 sentence overview of the candidate's career experience and domain.
    10. "education": A list of dicts, each having keys: "degree", "field_of_study", "school", "year".
    11. "projects": A list of dicts, each having keys: "title", "description", "skills_used".
    
    Resume Text:
    {resume_text}
    """
    
    try:
        response = client.models.generate_content(
            model=selected_model,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json"
            )
        )
        profile = json.loads(response.text)
        
        # Ensure fallback defaults for required keys
        profile.setdefault("name", "Unknown Candidate")
        profile.setdefault("email", "")
        profile.setdefault("phone", "")
        profile.setdefault("location", "")
        profile.setdefault("linkedin", "")
        profile.setdefault("github", "")
        profile.setdefault("portfolio", "")
        profile.setdefault("skills", [])
        profile.setdefault("summary", "")
        profile.setdefault("education", [])
        profile.setdefault("projects", [])
        
        return profile
    except Exception as e:
        print(f"Resume parsing failed: {str(e)}")
        # Return a shell dict if parsing fails completely
        return {
            "name": "Failed to parse name",
            "email": "",
            "phone": "",
            "location": "",
            "linkedin": "",
            "github": "",
            "portfolio": "",
            "skills": [],
            "summary": "Could not automatically parse resume text. Please check your API key and try re-uploading.",
            "education": [],
            "projects": []
        }

def evaluate_match(parsed_profile: dict, job_description: str, api_key: str) -> dict:
    """
    Token-optimized matcher. Compares only the extracted profile information
    (skills, summary, projects) with the job description to calculate compatibility.
    """
    if not api_key:
        raise ValueError("Gemini API key is required.")
    if not parsed_profile:
        raise ValueError("Parsed profile is empty.")
    if not job_description.strip():
        raise ValueError("Job description is empty.")
        
    client = genai.Client(api_key=api_key)
    selected_model = resolve_available_model(api_key)
    
    # Minimize token count by extracting only high-signal sections
    candidate_summary = parsed_profile.get("summary", "")
    candidate_skills = ", ".join(parsed_profile.get("skills", []))
    projects_list = []
    for proj in parsed_profile.get("projects", []):
        projects_list.append(f"- {proj.get('title')}: {proj.get('description')} (Skills: {', '.join(proj.get('skills_used', []))})")
    projects_summary = "\n".join(projects_list)
    
    prompt = f"""
    You are an expert ATS (Applicant Tracking System) parser and technical recruiter.
    Compare the candidate's core profile achievements and skills against the Job Description.
    
    Candidate Core Info:
    - Summary: {candidate_summary}
    - Skills: {candidate_skills}
    - Key Projects:
    {projects_summary}
    
    Job Description:
    {job_description}
    
    Analyze the alignment and return your response in JSON format. The JSON should contain these exact keys:
    1. "score": An integer from 0 to 100 representing the match percentage.
    2. "matched_skills": A list of skills/keywords found in both.
    3. "missing_skills": A list of important skills/keywords from the job description missing from candidate profile.
    4. "actionable_tips": A list of specific, actionable advice to optimize the resume for this job description.
    5. "summary": A brief 2-3 sentence overview of why they are or aren't a good fit.
    """
    
    try:
        response = client.models.generate_content(
            model=selected_model,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json"
            )
        )
        result = json.loads(response.text)
        
        # Ensure default values if keys are missing
        if "score" not in result:
            result["score"] = 50
        else:
            try:
                result["score"] = int(result["score"])
            except ValueError:
                result["score"] = 50
                
        result.setdefault("matched_skills", [])
        result.setdefault("missing_skills", [])
        result.setdefault("actionable_tips", [])
        result.setdefault("summary", "Could not generate analysis summary.")
        return result
    except Exception as e:
        print(f"Evaluation failed: {str(e)}")
        return {
            "score": 0,
            "matched_skills": [],
            "missing_skills": [],
            "actionable_tips": [f"Evaluation error: {str(e)}"],
            "summary": "Failed to analyze the profile match."
        }

def analyze_ats_compatibility(resume_text: str, job_description: str, api_key: str) -> dict:
    """
    Legacy wrapper function to preserve backwards compatibility.
    Parses resume on the fly and then evaluates matching.
    """
    profile = parse_resume_profile(resume_text, api_key)
    return evaluate_match(profile, job_description, api_key)
