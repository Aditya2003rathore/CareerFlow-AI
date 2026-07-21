import streamlit as st
import io
import time
import json
import os
import subprocess
import sys
from datetime import datetime
from ats_analyzer import extract_text_from_pdf, parse_resume_profile, evaluate_match
from scraper import search_recruiters, parse_manual_linkedin_urls
from email_finder import resolve_email
from generator import generate_outreach_email
from sender import send_outreach_email
from db_manager import store_jobs, search_jobs, init_db, get_job_stats, clear_old_jobs
from connectors import fetch_all_jobs
from auto_applier import apply_to_job

# Set page configuration
st.set_page_config(
    page_title="CareerFlow AI | Ultimate Autonomous Job Copilot",
    page_icon=None,
    layout="wide",
    initial_sidebar_state="expanded"
)

# Authorized users dictionary
USER_CREDENTIALS = {
    "admin": "admin#123",
    "user": "test#123"
}

AUDIT_LOG_FILE = "audit_log.json"
USER_CONFIG_FILE = "config_users.json"

def load_audit_logs() -> list:
    """Loads historical email and application audit logs."""
    if os.path.exists(AUDIT_LOG_FILE):
        try:
            with open(AUDIT_LOG_FILE, "r") as f:
                return json.load(f)
        except Exception:
            return []
    return []

def log_transaction(username: str, type_str: str, company: str, target: str, status: str, details: str = ""):
    """Logs a transaction (email outreach or auto-application) to the audit log."""
    logs = load_audit_logs()
    log_entry = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "user": username,
        "type": type_str,  # "Outreach Email" or "Auto Application"
        "company": company,
        "target": target,  # Email address or Job URL
        "status": status,
        "details": details
    }
    logs.append(log_entry)
    try:
        with open(AUDIT_LOG_FILE, "w") as f:
            json.dump(logs, f, indent=4)
    except Exception as e:
        print(f"Failed to write to audit log: {str(e)}")

def load_user_configs() -> dict:
    """Loads persistent user configurations from the JSON storage file."""
    if os.path.exists(USER_CONFIG_FILE):
        try:
            with open(USER_CONFIG_FILE, "r") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def save_user_config(username: str, user_data: dict) -> bool:
    """Saves or updates a user's persistent keys and profile JSON."""
    configs = load_user_configs()
    if username in configs:
        configs[username].update(user_data)
    else:
        configs[username] = user_data
    try:
        with open(USER_CONFIG_FILE, "w") as f:
            json.dump(configs, f, indent=4)
        return True
    except Exception:
        return False

RESUME_DIR = "resumes"

def get_user_resume_path(username: str) -> str:
    """Calculates the target path for a user's saved PDF resume."""
    os.makedirs(RESUME_DIR, exist_ok=True)
    return os.path.join(RESUME_DIR, f"{username}_resume.pdf")

def load_user_resume(username: str) -> tuple:
    """
    Loads saved resume bytes, filename, and raw text for a user.
    Returns (bytes, filename, text, parsed_profile)
    """
    path = get_user_resume_path(username)
    if os.path.exists(path):
        try:
            with open(path, "rb") as f:
                pdf_bytes = f.read()
            configs = load_user_configs()
            user_info = configs.get(username, {})
            filename = user_info.get("resume_filename", "resume.pdf")
            text = extract_text_from_pdf(io.BytesIO(pdf_bytes))
            profile = user_info.get("resume_profile", {})
            return pdf_bytes, filename, text, profile
        except Exception:
            return None, "", "", {}
    return None, "", "", {}

def save_user_resume(username: str, pdf_bytes: bytes, filename: str, profile_data: dict = None) -> bool:
    """Saves a user's resume PDF and profile details to disk and config."""
    path = get_user_resume_path(username)
    try:
        with open(path, "wb") as f:
            f.write(pdf_bytes)
        configs = load_user_configs()
        if username not in configs:
            configs[username] = {}
        configs[username]["resume_filename"] = filename
        if profile_data:
            configs[username]["resume_profile"] = profile_data
            
        with open(USER_CONFIG_FILE, "w") as f:
            json.dump(configs, f, indent=4)
        return True
    except Exception:
        return False

def delete_user_resume(username: str) -> bool:
    """Deletes the user's resume PDF and clears profile details."""
    path = get_user_resume_path(username)
    try:
        if os.path.exists(path):
            os.remove(path)
        configs = load_user_configs()
        if username in configs:
            if "resume_filename" in configs[username]:
                del configs[username]["resume_filename"]
            if "resume_profile" in configs[username]:
                del configs[username]["resume_profile"]
            with open(USER_CONFIG_FILE, "w") as f:
                json.dump(configs, f, indent=4)
        return True
    except Exception:
        return False

# Session State initialization
if 'authenticated' not in st.session_state:
    st.session_state.authenticated = False
if 'current_user' not in st.session_state:
    st.session_state.current_user = ""
if 'resume_text' not in st.session_state:
    st.session_state.resume_text = ""
if 'resume_bytes' not in st.session_state:
    st.session_state.resume_bytes = None
if 'resume_filename' not in st.session_state:
    st.session_state.resume_filename = ""
if 'resume_profile' not in st.session_state:
    st.session_state.resume_profile = {}
if 'match_scores' not in st.session_state:
    st.session_state.match_scores = {}
if 'leads' not in st.session_state:
    st.session_state.leads = []
if 'drafts' not in st.session_state:
    st.session_state.drafts = {}
if 'discovered_jobs' not in st.session_state:
    st.session_state.discovered_jobs = []
if 'pipeline_logs' not in st.session_state:
    st.session_state.pipeline_logs = {}

# Session states for key credentials
if 'user_gemini_key' not in st.session_state:
    st.session_state.user_gemini_key = ""
if 'user_hunter_key' not in st.session_state:
    st.session_state.user_hunter_key = ""
if 'user_sender_email' not in st.session_state:
    st.session_state.user_sender_email = ""
if 'user_app_password' not in st.session_state:
    st.session_state.user_app_password = ""
if 'config_loaded' not in st.session_state:
    st.session_state.config_loaded = False
if 'theme' not in st.session_state:
    st.session_state.theme = "dark"

def reset_user_session():
    st.session_state.resume_text = ""
    st.session_state.resume_bytes = None
    st.session_state.resume_filename = ""
    st.session_state.resume_profile = {}
    st.session_state.match_scores = {}
    st.session_state.leads = []
    st.session_state.drafts = {}
    st.session_state.discovered_jobs = []
    st.session_state.pipeline_logs = {}
    st.session_state.user_gemini_key = ""
    st.session_state.user_hunter_key = ""
    st.session_state.user_sender_email = ""
    st.session_state.user_app_password = ""

def render_theme_toggle(key_prefix: str = ""):
    theme_emoji = "☀️" if st.session_state.theme == "dark" else "🌙"
    theme_label = "Switch to Light Mode" if st.session_state.theme == "dark" else "Switch to Dark Mode"
    if st.button(f"{theme_emoji} {theme_label}", key=f"{key_prefix}theme_toggle_btn", use_container_width=True):
        st.session_state.theme = "light" if st.session_state.theme == "dark" else "dark"
        st.rerun()

# Inject Global Premium Theme CSS (Glassmorphism & animations)
theme = st.session_state.theme
if theme == "light":
    st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@300;400;500;600;700;800&display=swap');
    
    html, body, [class*="css"], .stMarkdown {
        font-family: 'Plus Jakarta Sans', sans-serif;
        color: #334155;
    }
    
    .stApp {
        background-color: #F8FAFC;
        background-image: 
            radial-gradient(at 0% 0%, rgba(99, 102, 241, 0.08) 0px, transparent 50%),
            radial-gradient(at 50% 0%, rgba(59, 130, 246, 0.06) 0px, transparent 50%),
            radial-gradient(at 100% 100%, rgba(147, 51, 234, 0.05) 0px, transparent 50%);
        background-attachment: fixed;
    }
    
    header[data-testid="stHeader"] {
        background: transparent;
    }
    
    .login-container {
        max-width: 450px;
        margin: 5% auto;
        padding: 3rem 2.5rem;
        background: linear-gradient(135deg, rgba(255, 255, 255, 0.8) 0%, rgba(241, 245, 249, 0.9) 100%);
        backdrop-filter: blur(20px);
        border: 1px solid rgba(99, 102, 241, 0.2);
        border-radius: 24px;
        box-shadow: 0 20px 40px rgba(99, 102, 241, 0.05), 0 0 30px rgba(99, 102, 241, 0.03);
        text-align: center;
    }
    
    .login-logo {
        font-size: 2.5rem;
        font-weight: 800;
        letter-spacing: -0.05em;
        background: linear-gradient(135deg, #6366F1 0%, #4F46E5 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 0.5rem;
        filter: drop-shadow(0 2px 8px rgba(99, 102, 241, 0.1));
    }
    
    .login-subtitle {
        font-size: 0.95rem;
        color: #64748B;
        margin-bottom: 2rem;
    }
    
    .dash-header {
        background: linear-gradient(135deg, rgba(255, 255, 255, 0.7) 0%, rgba(241, 245, 249, 0.5) 100%);
        backdrop-filter: blur(16px);
        border: 1px solid rgba(99, 102, 241, 0.1);
        padding: 2rem 2.5rem;
        border-radius: 24px;
        margin-bottom: 2.5rem;
        box-shadow: 0 10px 30px rgba(99, 102, 241, 0.05);
        display: flex;
        justify-content: space-between;
        align-items: center;
        flex-wrap: wrap;
        gap: 1rem;
    }
    
    .dash-logo-text {
        font-size: 2rem;
        font-weight: 800;
        letter-spacing: -0.04em;
        background: linear-gradient(135deg, #6366F1 0%, #4F46E5 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        filter: drop-shadow(0 2px 8px rgba(99, 102, 241, 0.1));
    }
    
    .dash-sub-text {
        font-size: 0.9rem;
        color: #475569;
        margin-top: 0.3rem;
    }
    
    .glass-card {
        background: linear-gradient(135deg, rgba(255, 255, 255, 0.7) 0%, rgba(241, 245, 249, 0.5) 100%);
        backdrop-filter: blur(12px);
        border: 1px solid rgba(99, 102, 241, 0.1);
        border-radius: 20px;
        padding: 1.8rem;
        margin-bottom: 1.5rem;
        box-shadow: 0 4px 20px rgba(0, 0, 0, 0.05);
        transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
        color: #334155;
    }
    .glass-card:hover {
        transform: translateY(-4px);
        border-color: rgba(99, 102, 241, 0.3);
        box-shadow: 0 8px 30px rgba(99, 102, 241, 0.12);
    }
    
    .score-circle-container {
        display: flex;
        flex-direction: column;
        align-items: center;
        margin: 1.5rem 0;
    }
    
    .radial-score {
        width: 160px;
        height: 160px;
        border-radius: 50%;
        background: conic-gradient(#6366F1 var(--score-angle), #E2E8F0 0deg);
        display: flex;
        align-items: center;
        justify-content: center;
        position: relative;
        box-shadow: 0 10px 30px rgba(99, 102, 241, 0.15);
    }
    
    .radial-score::before {
        content: '';
        position: absolute;
        width: 132px;
        height: 132px;
        border-radius: 50%;
        background: #F8FAFC;
    }
    
    .radial-score-value {
        position: absolute;
        font-size: 2.8rem;
        font-weight: 800;
        background: linear-gradient(135deg, #0F172A 0%, #334155 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
    }
    
    .badge {
        display: inline-block;
        padding: 0.3rem 0.75rem;
        border-radius: 9999px;
        font-size: 0.75rem;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        margin-right: 0.5rem;
        box-shadow: 0 2px 8px rgba(0, 0, 0, 0.05);
    }
    
    .badge-success { background: rgba(16, 185, 129, 0.1); color: #059669; border: 1px solid rgba(16, 185, 129, 0.2); }
    .badge-warning { background: rgba(245, 158, 11, 0.1); color: #D97706; border: 1px solid rgba(245, 158, 11, 0.2); }
    .badge-error { background: rgba(239, 68, 68, 0.1); color: #DC2626; border: 1px solid rgba(239, 68, 68, 0.2); }
    .badge-blue { background: rgba(59, 130, 246, 0.1); color: #1D4ED8; border: 1px solid rgba(59, 130, 246, 0.2); }
    
    button[data-testid="stBaseButton-primary"] {
        background: linear-gradient(135deg, #6366F1 0%, #4F46E5 100%) !important;
        color: white !important;
        border: none !important;
        border-radius: 12px !important;
        padding: 0.6rem 1.5rem !important;
        font-weight: 600 !important;
        box-shadow: 0 4px 14px rgba(99, 102, 241, 0.3) !important;
        transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1) !important;
    }
    
    button[data-testid="stBaseButton-primary"]:hover {
        transform: translateY(-2px) !important;
        box-shadow: 0 6px 20px rgba(99, 102, 241, 0.5) !important;
        background: linear-gradient(135deg, #4F46E5 0%, #4338CA 100%) !important;
    }
    
    button[data-testid="stBaseButton-secondary"] {
        background-color: #FFFFFF !important;
        color: #334155 !important;
        border: 1px solid rgba(0, 0, 0, 0.1) !important;
        border-radius: 12px !important;
        padding: 0.6rem 1.5rem !important;
        font-weight: 600 !important;
        transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1) !important;
        box-shadow: 0 2px 6px rgba(0, 0, 0, 0.05) !important;
    }
    
    button[data-testid="stBaseButton-secondary"]:hover {
        transform: translateY(-2px) !important;
        background-color: #F8FAFC !important;
        border-color: rgba(0, 0, 0, 0.15) !important;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1) !important;
    }
    
    div[data-baseweb="tab-list"] {
        gap: 0.5rem !important;
        background-color: rgba(241, 245, 249, 0.8) !important;
        padding: 6px !important;
        border-radius: 16px !important;
        border: 1px solid rgba(0, 0, 0, 0.05) !important;
        margin-bottom: 2rem !important;
    }
    
    button[data-baseweb="tab"] {
        background-color: transparent !important;
        color: #64748B !important;
        border: none !important;
        border-radius: 12px !important;
        padding: 10px 24px !important;
        font-weight: 600 !important;
        font-size: 0.95rem !important;
        transition: all 0.2s ease !important;
        height: auto !important;
    }
    
    button[data-baseweb="tab"][aria-selected="true"] {
        background-color: rgba(99, 102, 241, 0.1) !important;
        color: #4F46E5 !important;
        border-bottom: none !important;
    }
    
    div[data-baseweb="input"], div[data-baseweb="textarea"], div[data-baseweb="select"] {
        background-color: #FFFFFF !important;
        border: 1px solid rgba(0, 0, 0, 0.1) !important;
        border-radius: 12px !important;
    }
    
    div[data-testid="stFileUploader"] section {
        background-color: rgba(241, 245, 249, 0.5) !important;
        border: 2px dashed rgba(99, 102, 241, 0.2) !important;
        border-radius: 16px !important;
        padding: 2rem !important;
    }
    
    section[data-testid="stSidebar"] {
        background-color: #FFFFFF !important;
        border-right: 1px solid rgba(0, 0, 0, 0.06) !important;
    }
    
    div[data-testid="stAlert"] {
        background-color: rgba(255, 255, 255, 0.6) !important;
        backdrop-filter: blur(8px) !important;
        border-radius: 16px !important;
        border: 1px solid rgba(0, 0, 0, 0.05) !important;
    }
</style>
""", unsafe_allow_html=True)
else:
    st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@300;400;500;600;700;800&display=swap');
    
    html, body, [class*="css"], .stMarkdown {
        font-family: 'Plus Jakarta Sans', sans-serif;
        color: #E2E8F0;
    }
    
    .stApp {
        background-color: #030712;
        background-image: 
            radial-gradient(at 0% 0%, rgba(99, 102, 241, 0.15) 0px, transparent 50%),
            radial-gradient(at 50% 0%, rgba(59, 130, 246, 0.1) 0px, transparent 50%),
            radial-gradient(at 100% 100%, rgba(147, 51, 234, 0.08) 0px, transparent 50%),
            radial-gradient(at 10% 80%, rgba(244, 63, 94, 0.05) 0px, transparent 40%);
        background-attachment: fixed;
    }
    
    header[data-testid="stHeader"] {
        background: transparent;
    }
    
    .login-container {
        max-width: 450px;
        margin: 5% auto;
        padding: 3rem 2.5rem;
        background: linear-gradient(135deg, rgba(15, 23, 42, 0.8) 0%, rgba(7, 10, 19, 0.95) 100%);
        backdrop-filter: blur(20px);
        border: 1px solid rgba(99, 102, 241, 0.2);
        border-radius: 24px;
        box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.5), 0 0 40px rgba(99, 102, 241, 0.1);
        text-align: center;
    }
    
    .login-logo {
        font-size: 2.5rem;
        font-weight: 800;
        letter-spacing: -0.05em;
        background: linear-gradient(135deg, #A5B4FC 0%, #6366F1 50%, #3B82F6 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 0.5rem;
        filter: drop-shadow(0 2px 8px rgba(99, 102, 241, 0.2));
    }
    
    .login-subtitle {
        font-size: 0.95rem;
        color: #94A3B8;
        margin-bottom: 2rem;
    }
    
    .dash-header {
        background: linear-gradient(135deg, rgba(15, 23, 42, 0.6) 0%, rgba(30, 41, 59, 0.45) 100%);
        backdrop-filter: blur(16px);
        border: 1px solid rgba(255, 255, 255, 0.08);
        padding: 2rem 2.5rem;
        border-radius: 24px;
        margin-bottom: 2.5rem;
        box-shadow: 0 10px 30px rgba(0, 0, 0, 0.3), inset 0 1px 0 rgba(255, 255, 255, 0.05);
        display: flex;
        justify-content: space-between;
        align-items: center;
        flex-wrap: wrap;
        gap: 1rem;
    }
    
    .dash-logo-text {
        font-size: 2rem;
        font-weight: 800;
        letter-spacing: -0.04em;
        background: linear-gradient(135deg, #A5B4FC 0%, #818CF8 50%, #60A5FA 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        filter: drop-shadow(0 2px 8px rgba(129, 140, 248, 0.15));
    }
    
    .dash-sub-text {
        font-size: 0.9rem;
        color: #94A3B8;
        margin-top: 0.3rem;
    }
    
    .glass-card {
        background: linear-gradient(135deg, rgba(30, 41, 59, 0.45) 0%, rgba(15, 23, 42, 0.3) 100%);
        backdrop-filter: blur(12px);
        border: 1px solid rgba(255, 255, 255, 0.06);
        border-radius: 20px;
        padding: 1.8rem;
        margin-bottom: 1.5rem;
        box-shadow: 0 8px 32px rgba(0, 0, 0, 0.2);
        transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
    }
    .glass-card:hover {
        transform: translateY(-4px);
        border-color: rgba(99, 102, 241, 0.2);
        box-shadow: 0 12px 40px rgba(99, 102, 241, 0.12), 0 4px 12px rgba(0, 0, 0, 0.3);
    }
    
    .score-circle-container {
        display: flex;
        flex-direction: column;
        align-items: center;
        margin: 1.5rem 0;
    }
    
    .radial-score {
        width: 160px;
        height: 160px;
        border-radius: 50%;
        background: conic-gradient(#6366F1 var(--score-angle), #1E293B 0deg);
        display: flex;
        align-items: center;
        justify-content: center;
        position: relative;
        box-shadow: 0 10px 30px rgba(99, 102, 241, 0.25), inset 0 2px 4px rgba(255, 255, 255, 0.05);
    }
    
    .radial-score::before {
        content: '';
        position: absolute;
        width: 132px;
        height: 132px;
        border-radius: 50%;
        background: #030712;
        box-shadow: inset 0 4px 10px rgba(0, 0, 0, 0.3);
    }
    
    .radial-score-value {
        position: absolute;
        font-size: 2.8rem;
        font-weight: 800;
        background: linear-gradient(135deg, #FFFFFF 0%, #CBD5E1 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
    }
    
    .badge {
        display: inline-block;
        padding: 0.3rem 0.75rem;
        border-radius: 9999px;
        font-size: 0.75rem;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        margin-right: 0.5rem;
        box-shadow: 0 2px 8px rgba(0, 0, 0, 0.15);
    }
    
    .badge-success { background: rgba(16, 185, 129, 0.15); color: #34D399; border: 1px solid rgba(16, 185, 129, 0.25); }
    .badge-warning { background: rgba(245, 158, 11, 0.15); color: #FBBF24; border: 1px solid rgba(245, 158, 11, 0.25); }
    .badge-error { background: rgba(239, 68, 68, 0.15); color: #F87171; border: 1px solid rgba(239, 68, 68, 0.25); }
    .badge-blue { background: rgba(59, 130, 246, 0.15); color: #60A5FA; border: 1px solid rgba(59, 130, 246, 0.25); }
    
    button[data-testid="stBaseButton-primary"] {
        background: linear-gradient(135deg, #6366F1 0%, #4F46E5 100%) !important;
        color: white !important;
        border: none !important;
        border-radius: 12px !important;
        padding: 0.6rem 1.5rem !important;
        font-weight: 600 !important;
        box-shadow: 0 4px 14px rgba(99, 102, 241, 0.4) !important;
        transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1) !important;
    }
    
    button[data-testid="stBaseButton-primary"]:hover {
        transform: translateY(-2px) !important;
        box-shadow: 0 6px 20px rgba(99, 102, 241, 0.6) !important;
        background: linear-gradient(135deg, #4F46E5 0%, #4338CA 100%) !important;
    }
    
    button[data-testid="stBaseButton-secondary"] {
        background-color: rgba(30, 41, 59, 0.6) !important;
        color: #E2E8F0 !important;
        border: 1px solid rgba(255, 255, 255, 0.08) !important;
        border-radius: 12px !important;
        padding: 0.6rem 1.5rem !important;
        font-weight: 600 !important;
        transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1) !important;
        box-shadow: 0 4px 10px rgba(0, 0, 0, 0.15) !important;
    }
    
    button[data-testid="stBaseButton-secondary"]:hover {
        transform: translateY(-2px) !important;
        background-color: rgba(51, 65, 85, 0.8) !important;
        border-color: rgba(255, 255, 255, 0.15) !important;
        box-shadow: 0 6px 15px rgba(0, 0, 0, 0.25) !important;
    }
    
    div[data-baseweb="tab-list"] {
        gap: 0.5rem !important;
        background-color: rgba(15, 23, 42, 0.5) !important;
        padding: 6px !important;
        border-radius: 16px !important;
        border: 1px solid rgba(255, 255, 255, 0.05) !important;
        margin-bottom: 2rem !important;
    }
    
    button[data-baseweb="tab"] {
        background-color: transparent !important;
        color: #94A3B8 !important;
        border: none !important;
        border-radius: 12px !important;
        padding: 10px 24px !important;
        font-weight: 600 !important;
        font-size: 0.95rem !important;
        transition: all 0.2s ease !important;
        height: auto !important;
    }
    
    button[data-baseweb="tab"][aria-selected="true"] {
        background-color: rgba(99, 102, 241, 0.15) !important;
        color: #A5B4FC !important;
        border-bottom: none !important;
    }
    
    div[data-baseweb="input"], div[data-baseweb="textarea"], div[data-baseweb="select"] {
        background-color: rgba(15, 23, 42, 0.6) !important;
        border: 1px solid rgba(255, 255, 255, 0.08) !important;
        border-radius: 12px !important;
    }
    
    div[data-testid="stFileUploader"] section {
        background-color: rgba(15, 23, 42, 0.5) !important;
        border: 2px dashed rgba(99, 102, 241, 0.2) !important;
        border-radius: 16px !important;
        padding: 2rem !important;
    }
    
    section[data-testid="stSidebar"] {
        background-color: #030712 !important;
        border-right: 1px solid rgba(255, 255, 255, 0.05) !important;
    }
    
    div[data-testid="stAlert"] {
        background-color: rgba(30, 41, 59, 0.4) !important;
        backdrop-filter: blur(8px) !important;
        border-radius: 16px !important;
        border: 1px solid rgba(255, 255, 255, 0.05) !important;
    }
</style>
""", unsafe_allow_html=True)

# --- LOGIN SCREEN WORKFLOW ---
if not st.session_state.authenticated:
    st.markdown("""
    <div class="login-container">
        <div class="login-logo">CareerFlow AI</div>
        <div class="login-subtitle">Autonomous AI Job Application & Cold Mail Copilot</div>
    </div>
    """, unsafe_allow_html=True)
    
    col_l1, col_l2, col_l3 = st.columns([1.2, 1.8, 1.2])
    with col_l2:
        login_tab, register_tab = st.tabs(["Log In", "Create Account"])
        
        with login_tab:
            with st.form("login_form"):
                username = st.text_input("Username", placeholder="Enter username", key="login_username")
                password = st.text_input("Password", type="password", placeholder="Enter password", key="login_password")
                login_btn = st.form_submit_button("Authenticate Access", use_container_width=True)
                
                if login_btn:
                    username_clean = username.strip()
                    configs = load_user_configs()
                    
                    is_valid = False
                    if username_clean in USER_CREDENTIALS and USER_CREDENTIALS[username_clean] == password:
                        is_valid = True
                    elif username_clean in configs and configs[username_clean].get("password") == password:
                        is_valid = True
                        
                    if is_valid:
                        st.session_state.authenticated = True
                        st.session_state.current_user = username_clean
                        st.session_state.config_loaded = False  # Trigger reload for this user
                        st.success("Access Authorized. Initializing dashboard...")
                        time.sleep(0.5)
                        st.rerun()
                    else:
                        st.error("Invalid username or credentials. Please try again.")
                        
        with register_tab:
            with st.form("register_form"):
                new_username = st.text_input("New Username", placeholder="Enter a new username", key="reg_username")
                new_password = st.text_input("New Password", type="password", placeholder="Enter a password", key="reg_password")
                confirm_password = st.text_input("Confirm Password", type="password", placeholder="Confirm your password", key="reg_confirm_password")
                register_btn = st.form_submit_button("Register Account", use_container_width=True)
                
                if register_btn:
                    username_clean = new_username.strip()
                    password_clean = new_password.strip()
                    confirm_clean = confirm_password.strip()
                    
                    configs = load_user_configs()
                    
                    if not username_clean:
                        st.error("Username cannot be empty.")
                    elif not username_clean.isalnum():
                        st.error("Username must contain only alphanumeric characters.")
                    elif len(username_clean) < 3:
                        st.error("Username must be at least 3 characters long.")
                    elif not password_clean:
                        st.error("Password cannot be empty.")
                    elif len(password_clean) < 6:
                        st.error("Password must be at least 6 characters long.")
                    elif password_clean != confirm_clean:
                        st.error("Passwords do not match.")
                    elif username_clean in USER_CREDENTIALS or username_clean in configs:
                        st.error("Username is already taken.")
                    else:
                        reg_data = {"password": password_clean}
                        if save_user_config(username_clean, reg_data):
                            st.success("Account created successfully! Log in to continue.")
                        else:
                            st.error("Failed to create account.")
                            
        st.write("")
        render_theme_toggle("login_")
    st.stop()

# Initialize Database on first launch
init_db()

# Load user profile and configuration keys
if not st.session_state.config_loaded:
    reset_user_session()
    user_configs = load_user_configs()
    current_config = user_configs.get(st.session_state.current_user, {})
    st.session_state.user_gemini_key = current_config.get("gemini_api_key", "")
    st.session_state.user_hunter_key = current_config.get("hunter_api_key", "")
    st.session_state.user_sender_email = current_config.get("sender_email", "")
    st.session_state.user_app_password = current_config.get("sender_app_password", "")
    
    # Load user's saved resume PDF and profile
    res_bytes, res_filename, res_text, res_profile = load_user_resume(st.session_state.current_user)
    if res_bytes:
        st.session_state.resume_bytes = res_bytes
        st.session_state.resume_filename = res_filename
        st.session_state.resume_text = res_text
        st.session_state.resume_profile = res_profile
        
    st.session_state.config_loaded = True

# --- AUTHORIZED DASHBOARD WORKFLOW ---
col_head1, col_head2 = st.columns([8, 2])
with col_head1:
    st.markdown(f"""
    <div class="dash-header">
        <div>
            <div class="dash-logo-text">CareerFlow AI Copilot</div>
            <div class="dash-sub-text">Welcome back, <b>{st.session_state.current_user}</b>. Account profile: <b>Active</b>.</div>
        </div>
    </div>
    """, unsafe_allow_html=True)
with col_head2:
    st.markdown("<div style='height: 25px;'></div>", unsafe_allow_html=True)
    if st.button("Terminate Session", use_container_width=True):
        reset_user_session()
        st.session_state.authenticated = False
        st.session_state.current_user = ""
        st.session_state.config_loaded = False
        st.rerun()

# --- SIDEBAR: Configuration Inputs ---
with st.sidebar:
    st.markdown(f"### Profile: {st.session_state.current_user.capitalize()}")
    render_theme_toggle("sidebar_")
    st.markdown("---")
    st.markdown("##### Configuration & Key Store")
    
    user_gemini = st.text_input(
        "Gemini API Key",
        type="password",
        value=st.session_state.user_gemini_key,
        help="Used for Resume Parsing, AI Scoring, and Outreach Drafting."
    )
    st.markdown("[Get a free Gemini API Key](https://aistudio.google.com/)")
        
    user_hunter = st.text_input(
        "Hunter.io API Key (Optional)",
        type="password",
        value=st.session_state.user_hunter_key,
        help="Optional API key used to lookup corporate recruiter emails."
    )
    
    st.markdown("---")
    st.markdown("##### SMTP Email Outreach credentials")
    user_email = st.text_input(
        "Gmail Address", 
        value=st.session_state.user_sender_email,
        placeholder="you@gmail.com"
    )
    user_app_pw = st.text_input(
        "Gmail App Password",
        type="password",
        value=st.session_state.user_app_password,
        help="Generate a 16-character App Password in Google Account Settings."
    )
    st.markdown("[Generate App Password](https://myaccount.google.com/apppasswords)")
    
    # Save parameters to session
    st.session_state.user_gemini_key = user_gemini
    st.session_state.user_hunter_key = user_hunter
    st.session_state.user_sender_email = user_email
    st.session_state.user_app_password = user_app_pw

    if st.button("Save Profile Credentials", type="primary", use_container_width=True):
        creds = {
            "gemini_api_key": user_gemini.strip(),
            "hunter_api_key": user_hunter.strip(),
            "sender_email": user_email.strip(),
            "sender_app_password": user_app_pw.strip()
        }
        if save_user_config(st.session_state.current_user, creds):
            st.success("Credentials saved to profile.")
        else:
            st.error("Failed to save credentials.")

    if st.button("Clear Saved Credentials", use_container_width=True):
        configs = load_user_configs()
        if st.session_state.current_user in configs:
            for k in ["gemini_api_key", "hunter_api_key", "sender_email", "sender_app_password"]:
                if k in configs[st.session_state.current_user]:
                    del configs[st.session_state.current_user][k]
            try:
                with open(USER_CONFIG_FILE, "w") as f:
                    json.dump(configs, f, indent=4)
                st.session_state.user_gemini_key = ""
                st.session_state.user_hunter_key = ""
                st.session_state.user_sender_email = ""
                st.session_state.user_app_password = ""
                st.success("Credentials cleared.")
                st.rerun()
            except Exception:
                st.error("Failed to clear credentials.")

# Define navigation tabs
is_admin = st.session_state.current_user == "admin"
if is_admin:
    tab1, tab2, tab3, tab4 = st.tabs(["Resume & Profile", "Job Discovery Hub", "Recruiter Outreach", "System Audit Logs"])
else:
    tab1, tab2, tab3 = st.tabs(["Resume & Profile", "Job Discovery Hub", "Recruiter Outreach"])

# --- TAB 1: RESUME & PROFILE WORKSPACE ---
with tab1:
    st.markdown("### Profile Builder and Resume Parser")
    st.markdown("Upload your PDF resume to extract contacts, tech skills, and projects, enabling one-click applications.")
    
    col_p1, col_p2 = st.columns([1, 1.2], gap="large")
    
    with col_p1:
        st.markdown("##### Upload Resume PDF")
        
        # File Uploader
        label_text = "Upload PDF Resume"
        if st.session_state.resume_filename:
            label_text += f" (Current: {st.session_state.resume_filename})"
        uploaded_file = st.file_uploader(label_text, type=["pdf"])
        
        if uploaded_file is not None:
            if (st.session_state.resume_filename != uploaded_file.name or 
                st.session_state.resume_bytes is None):
                try:
                    with st.spinner("Loading and extracting text from PDF..."):
                        pdf_bytes = uploaded_file.read()
                        text = extract_text_from_pdf(io.BytesIO(pdf_bytes))
                        
                        st.session_state.resume_text = text
                        st.session_state.resume_bytes = pdf_bytes
                        st.session_state.resume_filename = uploaded_file.name
                        
                        # Save resume file immediately
                        save_user_resume(st.session_state.current_user, pdf_bytes, uploaded_file.name)
                        st.success(f"Loaded resume: {uploaded_file.name}")
                except Exception as e:
                    st.error(f"Error loading PDF: {str(e)}")
                    
        if st.session_state.resume_filename:
            # Parse Resume button
            if st.button("🤖 Build AI Profile From Resume", type="primary", use_container_width=True):
                if not st.session_state.user_gemini_key:
                    st.error("Gemini API Key is required to parse the resume.")
                else:
                    with st.spinner("AI is parsing your resume into a structured profile..."):
                        profile = parse_resume_profile(st.session_state.resume_text, st.session_state.user_gemini_key)
                        st.session_state.resume_profile = profile
                        
                        # Save profile JSON permanently
                        configs = load_user_configs()
                        if st.session_state.current_user not in configs:
                            configs[st.session_state.current_user] = {}
                        configs[st.session_state.current_user]["resume_profile"] = profile
                        save_user_config(st.session_state.current_user, configs[st.session_state.current_user])
                        
                        st.success("Successfully generated structured profile!")
                        st.rerun()
                        
            if st.button("Delete Resume & Profile Details", type="secondary", use_container_width=True):
                if delete_user_resume(st.session_state.current_user):
                    reset_user_session()
                    st.success("Resume data cleared.")
                    st.rerun()
                    
        st.markdown("---")
        st.markdown("##### 🔧 Automation Engine Diagnostics")
        st.markdown("To enable auto-apply browser filling, install the required automation binaries:")
        
        if st.button("Install Browser Automation Tools (Playwright)", use_container_width=True):
            with st.spinner("Installing Playwright chromium binaries... (this may take a minute)"):
                try:
                    # Run pip install playwright first
                    subprocess.run([sys.executable, "-m", "pip", "install", "playwright"], capture_output=True)
                    # Install chromium browser
                    proc = subprocess.run([sys.executable, "-m", "playwright", "install", "chromium"], capture_output=True, text=True)
                    if proc.returncode == 0:
                        st.success("Playwright Chromium browser installed successfully!")
                    else:
                        st.error(f"Playwright installation failed:\n{proc.stdout}\n{proc.stderr}")
                except Exception as e:
                    st.error(f"Error during installation: {str(e)}")
                    
    with col_p2:
        st.markdown("##### Structured Profile Details")
        profile = st.session_state.resume_profile
        
        if not profile:
            st.info("No AI profile generated yet. Upload your resume and click 'Build AI Profile' to populate your fields.")
        else:
            with st.form("profile_editor_form"):
                edit_name = st.text_input("Name", value=profile.get("name", ""))
                edit_email = st.text_input("Email", value=profile.get("email", ""))
                edit_phone = st.text_input("Phone", value=profile.get("phone", ""))
                edit_loc = st.text_input("Location", value=profile.get("location", ""))
                
                edit_linkedin = st.text_input("LinkedIn Profile URL", value=profile.get("linkedin", ""))
                edit_github = st.text_input("GitHub Profile URL", value=profile.get("github", ""))
                edit_portfolio = st.text_input("Portfolio Website URL", value=profile.get("portfolio", ""))
                
                # Skills comma separated list
                skills_list = profile.get("skills", [])
                edit_skills = st.text_area("Skills (comma-separated)", value=", ".join(skills_list))
                
                edit_summary = st.text_area("Summary", value=profile.get("summary", ""), height=100)
                
                save_profile_btn = st.form_submit_button("Save Profile Adjustments", use_container_width=True)
                
                if save_profile_btn:
                    # Construct updated profile
                    updated_skills = [s.strip() for s in edit_skills.split(",") if s.strip()]
                    updated_profile = {
                        "name": edit_name.strip(),
                        "email": edit_email.strip(),
                        "phone": edit_phone.strip(),
                        "location": edit_loc.strip(),
                        "linkedin": edit_linkedin.strip(),
                        "github": edit_github.strip(),
                        "portfolio": edit_portfolio.strip(),
                        "skills": updated_skills,
                        "summary": edit_summary.strip(),
                        "education": profile.get("education", []),
                        "projects": profile.get("projects", [])
                    }
                    st.session_state.resume_profile = updated_profile
                    
                    configs = load_user_configs()
                    if st.session_state.current_user not in configs:
                        configs[st.session_state.current_user] = {}
                    configs[st.session_state.current_user]["resume_profile"] = updated_profile
                    save_user_config(st.session_state.current_user, configs[st.session_state.current_user])
                    st.success("Profile saved and updated successfully!")
                    st.rerun()

# --- TAB 2: JOB DISCOVERY HUB ---
with tab2:
    st.markdown("### Job Board Aggregator & Apply Console")
    st.markdown("Fetch job openings via public ATS APIs and remote boards into a local database cache, rank matches, and launch applications.")
    
    if not st.session_state.resume_profile:
        st.info("Please upload your resume and build an AI profile in the 'Resume & Profile' tab to discover jobs.")
    else:
        # DB Statistics
        stats = get_job_stats()
        sources_str = ", ".join([f"{count} {src}" for src, count in stats.get("sources", {}).items()])
        st.markdown(f"""
        <div class="glass-card" style="padding: 1rem 1.8rem; border-color: rgba(99,102,241,0.25);">
            <div style="font-size:0.9rem; color:#A5B4FC;">Local Database Cache Status:</div>
            <div style="font-size:1.6rem; font-weight:800; color:#F8FAFC;">{stats.get('total', 0)} Active Listings</div>
            <div style="font-size:0.85rem; color:#94A3B8; margin-top:0.2rem;">Sources: {sources_str if sources_str else "Empty (Please sync)"}</div>
        </div>
        """, unsafe_allow_html=True)
        
        # Sync Controls
        col_s1, col_s2, col_s3 = st.columns([1, 1.5, 1.2])
        with col_s1:
            st.write("")
            st.write("")
            sync_btn = st.button("🔄 Sync Job Cache (Fetch APIs)", type="primary", use_container_width=True)
        with col_s2:
            custom_greenhouse = st.text_input("Custom Greenhouse Boards", placeholder="e.g. openai, stripe, airbnb", help="Comma-separated company slugs.")
        with col_s3:
            custom_lever = st.text_input("Custom Lever Boards", placeholder="e.g. vercel, figma, bolt", help="Comma-separated company slugs.")
            
        if sync_btn:
            with st.spinner("Aggregating listings from Greenhouse, Lever, Ashby, RemoteOK, Remotive, and Arbeitnow..."):
                try:
                    # Split custom values
                    gh_list = [c.strip() for c in custom_greenhouse.split(",") if c.strip()] if custom_greenhouse else None
                    lv_list = [c.strip() for c in custom_lever.split(",") if c.strip()] if custom_lever else None
                    
                    # Fetch all jobs
                    new_jobs = fetch_all_jobs(custom_greenhouse=gh_list, custom_lever=lv_list)
                    # Bulk store inside local sqlite db
                    store_jobs(new_jobs)
                    st.success(f"Database sync successful! Loaded jobs into sqlite storage.")
                    time.sleep(0.5)
                    st.rerun()
                except Exception as e:
                    st.error(f"Failed to sync jobs: {str(e)}")
                    
        st.write("---")
        st.markdown("##### Filter and Query Cache")
        
        col_f1, col_f2, col_f3 = st.columns([1.5, 1, 1])
        with col_f1:
            search_query = st.text_input("Job Title / Keywords", placeholder="e.g. Python Developer, Software Engineer")
        with col_f2:
            location_query = st.text_input("Location Filter", placeholder="e.g. Remote, India, San Francisco")
        with col_f3:
            source_options = ["All", "Greenhouse", "Lever", "Ashby", "RemoteOK", "Remotive", "Arbeitnow"]
            source_query = st.selectbox("Job Board Source", options=source_options)
            
        # SQL search query execution
        results = search_jobs(keywords=search_query, location=location_query, source=source_query)
        
        if not results:
            st.info("No matching job listings found in database. Try widening your filters or running a Cache Sync above.")
        else:
            st.markdown(f"**Found {len(results)} matches in cache.**")
            
            # Options for application mode defaults
            col_opt1, col_opt2 = st.columns(2)
            with col_opt1:
                app_mode = st.radio("Automation Action Default:", ["Pre-Fill (Visible Browser popup)", "Auto Apply (Silent Background / Headless)"], horizontal=True)
                playwright_headless = True if "Silent" in app_mode else False
                playwright_mode = "Auto Apply" if "Silent" in app_mode else "Pre-Fill"
            with col_opt2:
                min_match_display = st.slider("Filter results by Match Score greater than:", min_value=0, max_value=100, value=0)
                
            st.write("")
            
            # Display Job Cards
            for idx, job in enumerate(results):
                job_id = job["id"]
                url = job["url"]
                source = job["source"]
                
                # Determine apply classification
                # Greenhouse and Lever urls are auto-apply supported
                is_supported_ats = source in ["Greenhouse", "Lever"]
                apply_badge = "<span class='badge badge-success'>🟢 One-Click Apply</span>" if is_supported_ats else "<span class='badge badge-blue'>🔵 Manual Apply</span>"
                
                # Retrieve existing score if calculated
                score = st.session_state.match_scores.get(job_id, None)
                
                # Filter out card if match score is below minimum
                if score is not None and score < min_match_display:
                    continue
                    
                score_html = f"<span class='badge badge-warning'>{score}% Match</span>" if score is not None else ""
                
                st.markdown(f"""
                <div class="glass-card" style="margin-bottom: 1.2rem;">
                    <div style="display:flex; justify-content:space-between; align-items:flex-start; flex-wrap:wrap;">
                        <div>
                            <h4 style="margin:0; color:#F8FAFC;">{job['title']}</h4>
                            <div style="font-size:0.95rem; color:#A5B4FC; font-weight:600; margin-top:0.2rem;">{job['company']} — {job['location']}</div>
                        </div>
                        <div style="margin-top:0.4rem;">
                            <span class="badge badge-success">{source}</span>
                            {apply_badge}
                            {score_html}
                        </div>
                    </div>
                    <div style="font-size:0.85rem; color:#64748B; margin-top:0.3rem;">Salary: <b>{job['salary']}</b> | Posted: {job['posted_date']}</div>
                    <hr style="border-color:rgba(255,255,255,0.05); margin:0.8rem 0;">
                    <details style="font-size:0.9rem; color:#CBD5E1; cursor:pointer;">
                        <summary>View Details and Job Description</summary>
                        <p style="white-space:pre-wrap; font-size:0.85rem; color:#94A3B8; margin-top:0.5rem; max-height:250px; overflow-y:auto;">{job['description']}</p>
                    </details>
                </div>
                """, unsafe_allow_html=True)
                
                # Action buttons columns
                col_btn1, col_btn2, col_btn3 = st.columns([1, 1.2, 2.5])
                
                with col_btn1:
                    # Match score button
                    if st.button("Rank Fit score", key=f"score_{idx}"):
                        if not st.session_state.user_gemini_key:
                            st.error("API Key missing.")
                        else:
                            with st.spinner("AI Matcher..."):
                                match_analysis = evaluate_match(st.session_state.resume_profile, job["description"], st.session_state.user_gemini_key)
                                st.session_state.match_scores[job_id] = match_analysis.get("score", 50)
                                # Show details in an alert box
                                st.info(f"**Fit score: {match_analysis.get('score')}%**\n\n"
                                        f"**Fit Summary:** {match_analysis.get('summary')}\n\n"
                                        f"**Matched Skills:** {', '.join(match_analysis.get('matched_skills', []))}\n\n"
                                        f"**Missing Skills:** {', '.join(match_analysis.get('missing_skills', []))}\n\n"
                                        f"**ATS Optimization Tips:**\n" + "\n".join([f"- {tip}" for tip in match_analysis.get("actionable_tips", [])]))
                                
                with col_btn2:
                    if is_supported_ats:
                        # Auto apply button
                        if st.button("Apply with Bot", key=f"apply_{idx}", type="primary"):
                            st.session_state.pipeline_logs[idx] = "Starting browser automation..."
                            
                            with st.spinner("Launching browser automation..."):
                                # Calculate target local resume path
                                resume_pdf_path = get_user_resume_path(st.session_state.current_user)
                                
                                # Call auto_applier
                                res = apply_to_job(
                                    profile=st.session_state.resume_profile,
                                    resume_path=resume_pdf_path,
                                    job_url=url,
                                    mode=playwright_mode,
                                    headless=playwright_headless,
                                    logger=lambda text: st.session_state.pipeline_logs.update({idx: text})
                                )
                                
                                if res.get("success"):
                                    st.success(res.get("message", "Application completed."))
                                    log_transaction(
                                        username=st.session_state.current_user,
                                        type_str="Auto Application",
                                        company=job["company"],
                                        target=url,
                                        status="Success" if res.get("submitted") else "Completed (Manual Click)",
                                        details=f"Automation Mode: {playwright_mode}"
                                    )
                                else:
                                    st.error(res.get("message", "Automation failed."))
                                    log_transaction(
                                        username=st.session_state.current_user,
                                        type_str="Auto Application",
                                        company=job["company"],
                                        target=url,
                                        status="Failed",
                                        details=res.get("message")
                                    )
                    else:
                        st.markdown(f"<a href='{url}' target='_blank'><button data-testid='stBaseButton-primary' style='width:100%; border-radius:12px; border:none; padding:0.6rem 1rem; cursor:pointer;'>Apply Manually 🔗</button></a>", unsafe_allow_html=True)
                        
                with col_btn3:
                    # Live Automation Logging Output
                    if idx in st.session_state.pipeline_logs:
                        st.code(st.session_state.pipeline_logs[idx])

# --- TAB 3: RECRUITER OUTREACH ---
with tab3:
    st.markdown("### Recruiter Finder and Cold Mailer")
    st.markdown("Lookup recruiter LinkedIn profiles at target companies, resolve their corporate email addresses, and send AI-customized emails with attached resumes.")
    
    if not st.session_state.resume_text:
        st.info("Please upload your PDF resume in the 'Resume & Profile' tab to access the Outreach workspace.")
    else:
        # Check system setup warnings
        if not st.session_state.user_gemini_key:
            st.warning("Please configure your Gemini API Key in the sidebar to generate outreach messages.")
        if not st.session_state.user_sender_email or not st.session_state.user_app_password:
            st.warning("Configure your Gmail address and App Password in the sidebar to enable email delivery.")
            
        c_search, c_manual = st.columns([1.2, 0.8], gap="large")
        
        with c_search:
            st.markdown("""
            <div class="glass-card">
                <h5 style="color:#818CF8; margin-top:0;">Search Target Recruiter Profiles</h5>
            </div>
            """, unsafe_allow_html=True)
            
            sc1, sc2 = st.columns(2)
            with sc1:
                company_name_input = st.text_input("Target Company", placeholder="e.g. Stripe", key="outreach_company")
            with sc2:
                role_kw_input = st.text_input("Role Keywords", value="Recruiter, Talent Acquisition, Hiring Manager", key="outreach_kws")
                
            limit_search = st.slider("Max Search Leads", min_value=1, max_value=8, value=3, key="outreach_limit")
            search_triggered = st.button("Launch Search and Resolve", type="primary", use_container_width=True, key="outreach_search_btn")
            
        with c_manual:
            st.markdown("""
            <div class="glass-card">
                <h5 style="color:#818CF8; margin-top:0;">Manual LinkedIn Profile Entry</h5>
            </div>
            """, unsafe_allow_html=True)
            
            manual_urls = st.text_area(
                "Profile links (comma or newline separated):",
                height=110,
                placeholder="https://www.linkedin.com/in/recruiter-profile-slug",
                key="outreach_manual_links"
            )
            manual_company = st.text_input("Company Name for Manual Profiles", placeholder="e.g. Retool", key="outreach_manual_co")
            manual_triggered = st.button("Process Manual Profiles", use_container_width=True, key="outreach_manual_btn")
            
        # Process Search
        if search_triggered:
            if not company_name_input.strip():
                st.error("Target Company is required.")
            else:
                with st.spinner("Searching recruiter profiles..."):
                    kws = [k.strip() for k in role_kw_input.split(",")]
                    scraped_leads = search_recruiters(company_name_input.strip(), kws, limit=limit_search)
                    
                if not scraped_leads:
                    st.warning("No matches found.")
                else:
                    with st.spinner("Resolving emails and domain patterns..."):
                        for lead in scraped_leads:
                            resolved = resolve_email(
                                lead["name"],
                                lead["name"],
                                lead["company"],
                                hunter_api_key=st.session_state.user_hunter_key
                            )
                            lead["email"] = resolved["email"]
                            lead["method"] = resolved["method"]
                            lead["all_guesses"] = resolved["all_guesses"]
                        st.session_state.leads = scraped_leads
                        st.session_state.drafts = {}
                    st.success(f"Loaded {len(st.session_state.leads)} targets.")
                    
        # Process Manual Entry
        if manual_triggered:
            if not manual_urls.strip():
                st.error("Insert at least one LinkedIn URL.")
            else:
                with st.spinner("Parsing profile URLs..."):
                    parsed_leads = parse_manual_linkedin_urls(manual_urls, manual_company)
                    
                if not parsed_leads:
                    st.warning("No valid profile links found.")
                else:
                    with st.spinner("Resolving emails..."):
                        for lead in parsed_leads:
                            resolved = resolve_email(
                                lead["name"],
                                lead["name"],
                                lead["company"] if lead["company"] else manual_company,
                                hunter_api_key=st.session_state.user_hunter_key
                            )
                            lead["email"] = resolved["email"]
                            lead["method"] = resolved["method"]
                            lead["all_guesses"] = resolved["all_guesses"]
                        st.session_state.leads = parsed_leads
                        st.session_state.drafts = {}
                    st.success(f"Imported {len(st.session_state.leads)} leads.")
                    
        # Leads Workspace
        if st.session_state.leads:
            st.write("---")
            st.markdown("#### Discovered Recruiter Leads")
            
            for idx, lead in enumerate(st.session_state.leads):
                st.markdown(f"""
                <div class="glass-card" style="margin-bottom:0.8rem;">
                    <div style="font-weight:700; font-size:1.05rem; color:#F8FAFC;">{lead['name']}</div>
                    <div style="font-size:0.9rem; color:#94A3B8;">{lead['title']} at <b>{lead['company']}</b></div>
                    <div style="font-size:0.85rem; color:#64748B; margin-top:0.4rem;">
                        LinkedIn: <a href="{lead['linkedin_url']}" target="_blank" style="color:#60A5FA;">View Profile</a> | 
                        Contact: <code>{lead['email']}</code> <span class="badge badge-success">{lead['method']}</span>
                    </div>
                </div>
                """, unsafe_allow_html=True)
                
                if st.button(f"Generate Cold Outreach Email for {lead['name']}", key=f"gen_outreach_{idx}"):
                    if not st.session_state.user_gemini_key:
                        st.error("Please configure your Gemini API Key in the sidebar.")
                    else:
                        with st.spinner(f"AI is drafting outreach email..."):
                            try:
                                draft = generate_outreach_email(
                                    st.session_state.resume_text,
                                    lead["name"],
                                    lead["title"],
                                    lead["company"],
                                    job_desc="Hiring opportunities matching my skill profile",
                                    api_key=st.session_state.user_gemini_key
                                )
                                st.session_state.drafts[idx] = draft
                            except Exception as e:
                                st.error(f"Draft failed: {str(e)}")
                                
            # Draft Composer Editor
            if st.session_state.drafts:
                st.write("---")
                st.markdown("#### Cold Outreach Composer & Sender")
                
                draft_options = {idx: f"{st.session_state.leads[idx]['name']} ({st.session_state.leads[idx]['company']})" for idx in st.session_state.drafts.keys()}
                selected_draft_idx = st.selectbox("Select Recruiter Draft:", options=list(draft_options.keys()), format_func=lambda x: draft_options[x])
                
                selected_lead = st.session_state.leads[selected_draft_idx]
                selected_draft = st.session_state.drafts[selected_draft_idx]
                
                # Input boxes
                edit_subject = st.text_input("Subject", value=selected_draft.get("subject", ""))
                edit_body = st.text_area("Body", value=selected_draft.get("body", ""), height=250)
                
                if "all_guesses" in selected_lead and len(selected_lead["all_guesses"]) > 1:
                    alt_email = st.selectbox(
                        "Review Email Pattern Guesses:",
                        options=selected_lead["all_guesses"],
                        index=selected_lead["all_guesses"].index(selected_lead["email"]) if selected_lead["email"] in selected_lead["all_guesses"] else 0
                    )
                    selected_lead["email"] = alt_email
                    
                recipient_email_input = st.text_input("Send To:", value=selected_lead["email"])
                
                col_snd1, col_snd2 = st.columns([1.5, 3.5])
                with col_snd1:
                    send_btn = st.button("Send Outreach Mail Now", type="primary", use_container_width=True)
                with col_snd2:
                    st.write(f"Attaching PDF Resume: **{st.session_state.resume_filename}**")
                    
                if send_btn:
                    if not st.session_state.user_sender_email or not st.session_state.user_app_password:
                        st.error("SMTP details missing in sidebar.")
                    elif not recipient_email_input.strip():
                        st.error("Recipient address missing.")
                    else:
                        with st.spinner("Delivering email via SMTP..."):
                            try:
                                success = send_outreach_email(
                                    sender_email=st.session_state.user_sender_email,
                                    sender_password=st.session_state.user_app_password,
                                    recipient_email=recipient_email_input.strip(),
                                    subject=edit_subject,
                                    body=edit_body,
                                    resume_bytes=st.session_state.resume_bytes,
                                    resume_filename=st.session_state.resume_filename
                                )
                                if success:
                                    st.success(f"Email successfully dispatched to {selected_lead['name']} ({recipient_email_input}).")
                                    log_transaction(
                                        username=st.session_state.current_user,
                                        type_str="Outreach Email",
                                        company=selected_lead["company"],
                                        target=recipient_email_input.strip(),
                                        status="Success"
                                    )
                            except Exception as e:
                                st.error(f"Transmission failed: {str(e)}")
                                log_transaction(
                                    username=st.session_state.current_user,
                                    type_str="Outreach Email",
                                    company=selected_lead["company"],
                                    target=recipient_email_input.strip(),
                                    status="Failed",
                                    details=str(e)
                                )

# --- TAB 4: SYSTEM AUDIT LOGS (ADMIN ONLY OR SHOWN IN ADMIN TAB) ---
if is_admin:
    with tab4:
        st.markdown("### System Audit Logs")
        st.markdown("Monitor application submissions and recruiter outreach history across the platform.")
        
        logs = load_audit_logs()
        
        if not logs:
            st.info("No transaction history recorded yet.")
        else:
            col_clear1, col_clear2 = st.columns([8, 2])
            with col_clear2:
                if st.button("Clear Audit History", type="secondary", use_container_width=True):
                    try:
                        os.remove(AUDIT_LOG_FILE)
                        st.success("Audit history cleared.")
                        time.sleep(0.5)
                        st.rerun()
                    except Exception as e:
                        st.error(f"Failed to clear history: {str(e)}")
                        
            # Render logs DataFrame
            st.dataframe(
                logs,
                column_config={
                    "timestamp": "Timestamp",
                    "user": "User Profile",
                    "type": "Action Type",
                    "company": "Company",
                    "target": "Target",
                    "status": "Status",
                    "details": "Details"
                },
                use_container_width=True
            )
