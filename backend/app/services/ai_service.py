import json
import litellm
from backend.app.database.models import SessionLocal, MatchScore, Resume

# Disable LiteLLM logging to avoid telemetry noise
litellm.telemetry = False

from backend.app.config import settings

def get_ai_completion(prompt: str, api_key: str = "", provider_model: str = "gemini/gemini-1.5-flash") -> str:
    """Routes to LiteLLM completion with strict 20s timeout, automatic Groq default key fallback, and quota handling."""
    key_to_use = api_key.strip() if api_key and api_key.strip() else settings.DEFAULT_GROQ_API_KEY
    
    def _execute_completion(target_key: str):
        provider = "gemini"
        models_to_try = []
        
        if target_key.startswith("gsk_"):
            provider = "groq"
            os.environ["GROQ_API_KEY"] = target_key
            models_to_try = [
                "groq/llama-3.3-70b-versatile",
                "groq/llama-3.1-8b-instant",
                "groq/llama3-8b-8192"
            ]
        elif target_key.startswith("sk-or-"):
            provider = "openrouter"
            os.environ["OPENROUTER_API_KEY"] = target_key
            models_to_try = [
                "openrouter/google/gemini-2.5-flash",
                "openrouter/meta-llama/llama-3.1-8b-instruct:free"
            ]
        else:
            provider = "gemini"
            os.environ["GEMINI_API_KEY"] = target_key
            models_to_try = [
                "gemini/gemini-2.0-flash",
                "gemini/gemini-flash-latest",
                "gemini/gemini-2.0-flash-lite",
                provider_model
            ]
        
        last_err = None
        for model in models_to_try:
            try:
                response = litellm.completion(
                    model=model,
                    messages=[{"role": "user", "content": prompt}],
                    api_key=target_key,
                    timeout=20.0
                )
                content = response.choices[0].message.content
                os.environ.pop("GROQ_API_KEY", None)
                os.environ.pop("OPENROUTER_API_KEY", None)
                os.environ.pop("GEMINI_API_KEY", None)
                return content
            except Exception as e:
                last_err = e
                err_msg = str(e).lower()
                if "notfound" not in err_msg and "not_found" not in err_msg and "404" not in err_msg:
                    break
        
        os.environ.pop("GROQ_API_KEY", None)
        os.environ.pop("OPENROUTER_API_KEY", None)
        os.environ.pop("GEMINI_API_KEY", None)
        raise RuntimeError(f"LiteLLM error ({provider}): {str(last_err)}")

    try:
        return _execute_completion(key_to_use)
    except Exception as primary_error:
        p_err_str = str(primary_error).lower()
        is_quota = any(term in p_err_str for term in ["rate_limit", "429", "quota", "exceeded", "limit_reached"])
        
        # If primary key wasn't the default Groq key, try fallback to default Groq key
        if key_to_use != settings.DEFAULT_GROQ_API_KEY:
            try:
                return _execute_completion(settings.DEFAULT_GROQ_API_KEY)
            except Exception:
                pass
                
        if is_quota or key_to_use == settings.DEFAULT_GROQ_API_KEY:
            raise RuntimeError("API quota limit reached on default Groq key. Please navigate to Settings / Keys to add your custom Gemini or Groq API key to continue auto-scoring.")
        raise primary_error

def parse_resume_profile(resume_text: str, api_key: str = "", provider_model: str = "gemini/gemini-1.5-flash") -> dict:
    """Parses raw resume text into structured JSON profile."""
    effective_key = api_key.strip() if api_key and api_key.strip() else settings.DEFAULT_GROQ_API_KEY
    if not resume_text.strip():
        raise ValueError("Resume text is empty.")
    if not resume_text.strip():
        raise ValueError("Resume text is empty.")
        
    prompt = f"""
    You are an expert technical resume parser.
    Extract candidate information from the Resume Text below and format it into a valid JSON object.
    
    The JSON object must contain these exact keys:
    1. "name": The full name of the candidate.
    2. "email": Candidate's email address.
    3. "phone": Candidate's phone number.
    4. "location": Candidate's current location/city.
    5. "linkedin": Candidate's LinkedIn profile URL.
    6. "github": Candidate's GitHub profile URL.
    7. "portfolio": Candidate's portfolio website URL.
    8. "skills": A clean list of core technical skills/keywords (e.g. ["Python", "FastAPI", "Docker", "AWS", "Git"]).
    9. "summary": A brief 2-3 sentence overview of the candidate's career experience and domain.
    10. "college": College/University name.
    11. "cgpa": CGPA (float/numeric, e.g., 9.2).
    12. "branch": Degree branch (e.g. Computer Science).
    13. "grad_year": Graduation year (int, e.g. 2024).
    14. "experience_level": Check one from ('fresher', 'junior', 'mid', 'senior').
    
    Resume Text:
    {resume_text}
    """
    
    response_text = get_ai_completion(prompt, api_key, provider_model)
    # Find JSON bounds in case markdown wrapper block exists
    try:
        start_idx = response_text.find("{")
        end_idx = response_text.rfind("}") + 1
        json_str = response_text[start_idx:end_idx]
        profile = json.loads(json_str)
    except Exception:
        raise ValueError("Failed to extract valid JSON from AI response.")
        
    # Standard normalization fallbacks
    profile.setdefault("name", "Unknown Candidate")
    profile.setdefault("email", "")
    profile.setdefault("phone", "")
    profile.setdefault("location", "")
    profile.setdefault("linkedin", "")
    profile.setdefault("github", "")
    profile.setdefault("portfolio", "")
    profile.setdefault("skills", [])
    profile.setdefault("summary", "")
    profile.setdefault("college", "")
    profile.setdefault("cgpa", 0.0)
    profile.setdefault("branch", "")
    profile.setdefault("grad_year", None)
    profile.setdefault("experience_level", "fresher")
    
    return profile

def get_cached_or_compute_match(
    db, 
    user_id, 
    job_id, 
    job_description: str, 
    api_key: str, 
    provider_model: str = "gemini/gemini-1.5-flash"
) -> dict:
    """Checks the match_scores table for existing caches before invoking AI model."""
    # Find latest resume version for this user
    resume = db.query(Resume).filter(Resume.user_id == user_id).order_by(Resume.version.desc()).first()
    if not resume:
        raise ValueError("Please upload a resume first.")

    # Check cached match score
    cached = db.query(MatchScore).filter(
        MatchScore.user_id == user_id,
        MatchScore.job_id == job_id,
        MatchScore.resume_version == resume.version
    ).first()
    
    if cached:
        return {
            "score": cached.score,
            "matched_skills": json.loads(cached.missing_skills) if cached.missing_skills.startswith("[") else [], # fallback mapping
            "missing_skills": json.loads(cached.missing_skills) if cached.missing_skills.startswith("[") else [],
            "explanation": cached.explanation
        }

    # If no cache, invoke AI model
    parsed_profile = json.loads(resume.parsed_json) if resume.parsed_json else {}
    candidate_summary = parsed_profile.get("summary", "")
    candidate_skills = ", ".join(parsed_profile.get("skills", []))
    
    prompt = f"""
    You are an expert ATS matching engine.
    Compare the candidate's core profile achievements and skills against the Job Description.
    
    Candidate Core Info:
    - Summary: {candidate_summary}
    - Skills: {candidate_skills}
    
    Job Description:
    {job_description}
    
    Analyze the alignment and return your response in JSON format. The JSON should contain these exact keys:
    1. "score": An integer from 0 to 100 representing the match percentage.
    2. "matched_skills": A list of skills/keywords found in both.
    3. "missing_skills": A list of important skills/keywords from the job description missing from candidate profile.
    4. "actionable_tips": A list of specific, actionable advice to optimize the resume.
    5. "summary": A brief 2-3 sentence overview of why they are or aren't a good fit.
    """
    
    response_text = get_ai_completion(prompt, api_key, provider_model)
    
    try:
        start_idx = response_text.find("{")
        end_idx = response_text.rfind("}") + 1
        json_str = response_text[start_idx:end_idx]
        result = json.loads(json_str)
    except Exception:
        raise ValueError("Failed to extract valid JSON analysis from AI response.")
        
    score = int(result.get("score", 50))
    matched_list = result.get("matched_skills", [])
    missing_list = result.get("missing_skills", [])
    actionable_tips = result.get("actionable_tips", [])
    summary = result.get("summary", "")

    # Save to cache
    match_entry = MatchScore(
        user_id=user_id,
        job_id=job_id,
        resume_version=resume.version,
        score=score,
        missing_skills=json.dumps(missing_list),
        explanation=summary
    )
    db.add(match_entry)
    db.commit()

    return {
        "score": score,
        "matched_skills": matched_list,
        "missing_skills": missing_list,
        "actionable_tips": actionable_tips,
        "summary": summary
    }
