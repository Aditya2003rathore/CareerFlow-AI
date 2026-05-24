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
        
        # Cleaned priority candidates (without 'models/' prefix, which the new SDK accepts)
        priority_list = [
            "gemini-1.5-flash",
            "gemini-1.5-flash-latest",
            "gemini-2.0-flash",
            "gemini-1.5-pro",
            "gemini-pro"
        ]
        for candidate in priority_list:
            # Check matches by checking exact or substring presence
            if any(candidate in m for m in available_models):
                return candidate
                
        # Look for any models containing gemini in name
        for m in available_models:
            if "gemini" in m:
                # Strip models/ prefix if present
                return m.split('/')[-1]
    except Exception as e:
        print(f"Error querying Gemini models: {str(e)}")
    return "gemini-1.5-flash"

def analyze_ats_compatibility(resume_text: str, job_description: str, api_key: str) -> dict:
    """
    Compares resume text with a job description using Gemini and returns an ATS analysis.
    """
    if not api_key:
        raise ValueError("Gemini API key is required.")
    if not resume_text.strip():
        raise ValueError("Resume text is empty.")
    if not job_description.strip():
        raise ValueError("Job description is empty.")

    client = genai.Client(api_key=api_key)
    selected_model = resolve_available_model(api_key)
    
    # Setup candidate lists to try in case of 429 quota limits
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

    # Construct the prompt
    prompt = f"""
You are an expert ATS (Applicant Tracking System) parser and technical recruiter.
Compare the candidate's Resume against the Job Description.

Analyze the resume for keyword matches, skill gaps, formatting, and relevance.
You must return your response in JSON format. The JSON should contain these exact keys:
1. "score": An integer from 0 to 100 representing the match percentage.
2. "matched_skills": A list of skills/keywords found in both.
3. "missing_skills": A list of important skills/keywords from the job description missing from the resume.
4. "actionable_tips": A list of specific, actionable advice to optimize the resume for this job description (e.g. "Add experience with GCP", "Highlight leadership in Agile projects").
5. "summary": A brief 2-3 sentence overview of the candidate's fit.

Resume:
{resume_text}

Job Description:
{job_description}
"""

    last_error = None
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
            last_error = e
            print(f"Generation failed with model {model_name}: {str(e)}")
            continue # Try next model
            
    # If all models failed
    return {
        "score": 0,
        "matched_skills": [],
        "missing_skills": [],
        "actionable_tips": [
            f"API Error: {str(last_error)}",
            "This error usually happens when your API key is invalid or exceeds its free tier quota limit.",
            "Please double check your API key in the sidebar or try again in a few seconds."
        ],
        "summary": "Failed to analyze the resume due to API rate limits or quota constraints."
    }
