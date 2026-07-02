import streamlit as st
import io
import time
import json
import os
from datetime import datetime
from ats_analyzer import extract_text_from_pdf, analyze_ats_compatibility
from scraper import search_recruiters, parse_manual_linkedin_urls
from email_finder import resolve_email
from generator import generate_outreach_email
from sender import send_outreach_email

# Set page configuration
st.set_page_config(
    page_title="CareerFlow AI | Premium Recruiter Outreach & ATS",
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
    """
    Loads historical email audit logs.
    """
    if os.path.exists(AUDIT_LOG_FILE):
        try:
            with open(AUDIT_LOG_FILE, "r") as f:
                return json.load(f)
        except Exception:
            return []
    return []

def log_email_transaction(username: str, recruiter: str, company: str, recipient: str, status: str):
    """
    Logs an email transaction to the shared audit log file.
    """
    logs = load_audit_logs()
    log_entry = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "user": username,
        "recruiter": recruiter,
        "company": company,
        "recipient": recipient,
        "status": status
    }
    logs.append(log_entry)
    try:
        with open(AUDIT_LOG_FILE, "w") as f:
            json.dump(logs, f, indent=4)
    except Exception as e:
        print(f"Failed to write to audit log: {str(e)}")

def load_user_configs() -> dict:
    """
    Loads persistent user configurations from the JSON storage file.
    """
    if os.path.exists(USER_CONFIG_FILE):
        try:
            with open(USER_CONFIG_FILE, "r") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def save_user_config(username: str, user_data: dict) -> bool:
    """
    Saves or updates a user's persistent keys in the storage file.
    """
    configs = load_user_configs()
    # Merge existing config to not lose other properties like resume_filename
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
    """
    Calculates the target path for a user's saved PDF resume.
    """
    os.makedirs(RESUME_DIR, exist_ok=True)
    return os.path.join(RESUME_DIR, f"{username}_resume.pdf")

def load_user_resume(username: str) -> tuple:
    """
    Loads saved resume bytes and filename for a specific user if it exists.
    Returns (bytes, filename, text) or (None, "", "")
    """
    path = get_user_resume_path(username)
    if os.path.exists(path):
        try:
            with open(path, "rb") as f:
                pdf_bytes = f.read()
            configs = load_user_configs()
            filename = configs.get(username, {}).get("resume_filename", "resume.pdf")
            text = extract_text_from_pdf(io.BytesIO(pdf_bytes))
            return pdf_bytes, filename, text
        except Exception:
            return None, "", ""
    return None, "", ""

def save_user_resume(username: str, pdf_bytes: bytes, filename: str) -> bool:
    """
    Saves a user's resume file to disk and updates their config.
    """
    path = get_user_resume_path(username)
    try:
        with open(path, "wb") as f:
            f.write(pdf_bytes)
        configs = load_user_configs()
        if username not in configs:
            configs[username] = {}
        configs[username]["resume_filename"] = filename
        try:
            with open(USER_CONFIG_FILE, "w") as f:
                json.dump(configs, f, indent=4)
            return True
        except Exception:
            return False
    except Exception:
        return False

def delete_user_resume(username: str) -> bool:
    """
    Deletes the user's resume PDF from disk and updates their config.
    """
    path = get_user_resume_path(username)
    try:
        if os.path.exists(path):
            os.remove(path)
        configs = load_user_configs()
        if username in configs and "resume_filename" in configs[username]:
            del configs[username]["resume_filename"]
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
if 'ats_results' not in st.session_state:
    st.session_state.ats_results = None
if 'leads' not in st.session_state:
    st.session_state.leads = []
if 'drafts' not in st.session_state:
    st.session_state.drafts = {}
if 'discovered_jobs' not in st.session_state:
    st.session_state.discovered_jobs = []
if 'pipeline_logs' not in st.session_state:
    st.session_state.pipeline_logs = {}

# Session state keys for the current session run
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
    """
    Resets all user-specific data from the Streamlit session state.
    """
    st.session_state.resume_text = ""
    st.session_state.resume_bytes = None
    st.session_state.resume_filename = ""
    st.session_state.ats_results = None
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

# Inject Global Premium Theme CSS
theme = st.session_state.theme
if theme == "light":
    st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@300;400;500;600;700;800&display=swap');
    
    /* Set global font and light mode canvas */
    html, body, [class*="css"], .stMarkdown {
        font-family: 'Plus Jakarta Sans', sans-serif;
        color: #334155;
    }
    
    /* Root main container background */
    .stApp {
        background-color: #F8FAFC;
        background-image: 
            radial-gradient(at 0% 0%, rgba(99, 102, 241, 0.08) 0px, transparent 50%),
            radial-gradient(at 50% 0%, rgba(59, 130, 246, 0.06) 0px, transparent 50%),
            radial-gradient(at 100% 100%, rgba(147, 51, 234, 0.05) 0px, transparent 50%);
        background-attachment: fixed;
    }
    
    /* Hide default Streamlit decoration line */
    header[data-testid="stHeader"] {
        background: transparent;
    }
    
    /* Premium Glassmorphic Login Container */
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
    
    /* Sleek Dashboard Header */
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
    
    /* Custom glassmorphic cards */
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
    
    /* ATS Score Layout */
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
    
    /* Badge styling */
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
    
    /* Custom style for primary and secondary Streamlit buttons */
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
    
    button[data-testid="stBaseButton-primary"]:active {
        transform: translateY(0px) !important;
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
    
    button[data-testid="stBaseButton-secondary"]:active {
        transform: translateY(0px) !important;
    }
    
    /* Style the tabs widget for premium Segmented Controls look */
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
        box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.5) !important;
        border-bottom: none !important;
    }
    
    button[data-baseweb="tab"]:hover {
        color: #334155 !important;
        background-color: rgba(0, 0, 0, 0.02) !important;
    }
    
    /* Input adjustments for Streamlit components */
    div[data-baseweb="input"], div[data-baseweb="textarea"], div[data-baseweb="select"] {
        background-color: #FFFFFF !important;
        border: 1px solid rgba(0, 0, 0, 0.1) !important;
        border-radius: 12px !important;
        transition: all 0.2s ease !important;
    }
    
    div[data-baseweb="input"]:focus-within, div[data-baseweb="textarea"]:focus-within, div[data-baseweb="select"]:focus-within {
        border-color: #6366F1 !important;
        box-shadow: 0 0 0 2px rgba(99, 102, 241, 0.1) !important;
    }
    
    div[data-baseweb="input"] input, div[data-baseweb="textarea"] textarea {
        color: #0F172A !important;
    }
    
    /* File Uploader Box customization */
    div[data-testid="stFileUploader"] section {
        background-color: rgba(241, 245, 249, 0.5) !important;
        border: 2px dashed rgba(99, 102, 241, 0.2) !important;
        border-radius: 16px !important;
        padding: 2rem !important;
        transition: all 0.2s ease !important;
        color: #64748B !important;
    }
    
    div[data-testid="stFileUploader"] section:hover {
        border-color: #6366F1 !important;
        background-color: rgba(99, 102, 241, 0.02) !important;
    }
    
    /* Sidebar adjustments */
    section[data-testid="stSidebar"] {
        background-color: #FFFFFF !important;
        border-right: 1px solid rgba(0, 0, 0, 0.06) !important;
    }
    
    section[data-testid="stSidebar"] div[class*="stVerticalBlock"] {
        padding: 2rem 1.5rem !important;
    }
    
    /* Sleek Custom Alert styling */
    div[data-testid="stAlert"] {
        background-color: rgba(255, 255, 255, 0.6) !important;
        backdrop-filter: blur(8px) !important;
        border-radius: 16px !important;
        border: 1px solid rgba(0, 0, 0, 0.05) !important;
        padding: 1rem 1.5rem !important;
        color: #334155 !important;
    }
    
    div[data-testid="stAlert"] div[role="alert"] {
        color: #334155 !important;
    }
    
    /* Transition animation on theme toggle */
    html, body, [class*="css"], .stMarkdown, .stApp, .login-container, .dash-header, .glass-card, 
    .radial-score, .radial-score::before, .radial-score-value, button, div[data-baseweb="tab-list"], 
    button[data-baseweb="tab"], div[data-baseweb="input"], div[data-baseweb="textarea"], 
    div[data-baseweb="select"], div[data-testid="stFileUploader"] section, section[data-testid="stSidebar"],
    div[data-testid="stAlert"] {
        transition: background-color 0.8s cubic-bezier(0.4, 0, 0.2, 1), 
                    background-image 0.8s cubic-bezier(0.4, 0, 0.2, 1), 
                    color 0.8s cubic-bezier(0.4, 0, 0.2, 1), 
                    border-color 0.8s cubic-bezier(0.4, 0, 0.2, 1), 
                    box-shadow 0.8s cubic-bezier(0.4, 0, 0.2, 1) !important;
    }
</style>
""", unsafe_allow_html=True)
else:
    st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@300;400;500;600;700;800&display=swap');
    
    /* Set global font and dark mode canvas */
    html, body, [class*="css"], .stMarkdown {
        font-family: 'Plus Jakarta Sans', sans-serif;
        color: #E2E8F0;
    }
    
    /* Root main container background */
    .stApp {
        background-color: #030712;
        background-image: 
            radial-gradient(at 0% 0%, rgba(99, 102, 241, 0.15) 0px, transparent 50%),
            radial-gradient(at 50% 0%, rgba(59, 130, 246, 0.1) 0px, transparent 50%),
            radial-gradient(at 100% 100%, rgba(147, 51, 234, 0.08) 0px, transparent 50%),
            radial-gradient(at 10% 80%, rgba(244, 63, 94, 0.05) 0px, transparent 40%);
        background-attachment: fixed;
    }
    
    /* Hide default Streamlit decoration line */
    header[data-testid="stHeader"] {
        background: transparent;
    }
    
    /* Premium Glassmorphic Login Container */
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
    
    /* Sleek Dashboard Header */
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
    
    /* Custom glassmorphic cards */
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
    
    /* ATS Score Layout */
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
    
    /* Badge styling */
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
    
    /* Custom style for primary and secondary Streamlit buttons */
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
    
    button[data-testid="stBaseButton-primary"]:active {
        transform: translateY(0px) !important;
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
    
    button[data-testid="stBaseButton-secondary"]:active {
        transform: translateY(0px) !important;
    }
    
    /* Style the tabs widget for premium Segmented Controls look */
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
        box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.05) !important;
        border-bottom: none !important;
    }
    
    button[data-baseweb="tab"]:hover {
        color: #E2E8F0 !important;
        background-color: rgba(255, 255, 255, 0.03) !important;
    }
    
    /* Input adjustments for Streamlit components to match dark mode */
    div[data-baseweb="input"], div[data-baseweb="textarea"], div[data-baseweb="select"] {
        background-color: rgba(15, 23, 42, 0.6) !important;
        border: 1px solid rgba(255, 255, 255, 0.08) !important;
        border-radius: 12px !important;
        transition: all 0.2s ease !important;
    }
    
    div[data-baseweb="input"]:focus-within, div[data-baseweb="textarea"]:focus-within, div[data-baseweb="select"]:focus-within {
        border-color: #6366F1 !important;
        box-shadow: 0 0 0 2px rgba(99, 102, 241, 0.2) !important;
    }
    
    div[data-baseweb="input"] input, div[data-baseweb="textarea"] textarea {
        color: #F8FAFC !important;
    }
    
    /* File Uploader Box customization */
    div[data-testid="stFileUploader"] section {
        background-color: rgba(15, 23, 42, 0.5) !important;
        border: 2px dashed rgba(99, 102, 241, 0.2) !important;
        border-radius: 16px !important;
        padding: 2rem !important;
        transition: all 0.2s ease !important;
        color: #94A3B8 !important;
    }
    
    div[data-testid="stFileUploader"] section:hover {
        border-color: #6366F1 !important;
        background-color: rgba(99, 102, 241, 0.03) !important;
    }
    
    /* Sidebar adjustments */
    section[data-testid="stSidebar"] {
        background-color: #030712 !important;
        border-right: 1px solid rgba(255, 255, 255, 0.05) !important;
    }
    
    section[data-testid="stSidebar"] div[class*="stVerticalBlock"] {
        padding: 2rem 1.5rem !important;
    }
    
    /* Sleek Custom Alert styling */
    div[data-testid="stAlert"] {
        background-color: rgba(30, 41, 59, 0.4) !important;
        backdrop-filter: blur(8px) !important;
        border-radius: 16px !important;
        border: 1px solid rgba(255, 255, 255, 0.05) !important;
        padding: 1rem 1.5rem !important;
        color: #E2E8F0 !important;
    }
    
    div[data-testid="stAlert"] div[role="alert"] {
        color: #E2E8F0 !important;
    }
    
    /* Transition animation on theme toggle */
    html, body, [class*="css"], .stMarkdown, .stApp, .login-container, .dash-header, .glass-card, 
    .radial-score, .radial-score::before, .radial-score-value, button, div[data-baseweb="tab-list"], 
    button[data-baseweb="tab"], div[data-baseweb="input"], div[data-baseweb="textarea"], 
    div[data-baseweb="select"], div[data-testid="stFileUploader"] section, section[data-testid="stSidebar"],
    div[data-testid="stAlert"] {
        transition: background-color 0.8s cubic-bezier(0.4, 0, 0.2, 1), 
                    background-image 0.8s cubic-bezier(0.4, 0, 0.2, 1), 
                    color 0.8s cubic-bezier(0.4, 0, 0.2, 1), 
                    border-color 0.8s cubic-bezier(0.4, 0, 0.2, 1), 
                    box-shadow 0.8s cubic-bezier(0.4, 0, 0.2, 1) !important;
    }
</style>
""", unsafe_allow_html=True)

# --- LOGIN SCREEN WORKFLOW ---
if not st.session_state.authenticated:
    st.markdown("""
    <div class="login-container">
        <div class="login-logo">CareerFlow AI</div>
        <div class="login-subtitle">Partner Hub and Recruiter Outreach Platform</div>
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
                        st.success("Access Authorized. Initializing...")
                        time.sleep(0.5)
                        st.rerun()
                    else:
                        st.error("Invalid username or credentials. Please try again or register.")
                        
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
                        st.error("Username must contain only letters and numbers (alphanumeric).")
                    elif len(username_clean) < 3:
                        st.error("Username must be at least 3 characters long.")
                    elif not password_clean:
                        st.error("Password cannot be empty.")
                    elif len(password_clean) < 6:
                        st.error("Password must be at least 6 characters long.")
                    elif password_clean != confirm_clean:
                        st.error("Passwords do not match.")
                    elif username_clean in USER_CREDENTIALS or username_clean in configs:
                        st.error("Username is already taken. Please choose another name.")
                    else:
                        reg_data = {"password": password_clean}
                        if save_user_config(username_clean, reg_data):
                            st.success("Account successfully created! Please switch to the 'Log In' tab to access your workspace.")
                        else:
                            st.error("Failed to create account. Please contact your system administrator.")
                            
        st.write("")
        render_theme_toggle("login_")
        st.markdown("""
        <div style="text-align: center; color: #64748B; font-size: 0.8rem; margin-top: 2rem;">
            Authorized users only. Powered by Gemini 1.5 Flash.
        </div>
        """, unsafe_allow_html=True)
    st.stop()

# Load persisted keys for current user on first login run
if not st.session_state.config_loaded:
    reset_user_session()
    user_configs = load_user_configs()
    current_config = user_configs.get(st.session_state.current_user, {})
    st.session_state.user_gemini_key = current_config.get("gemini_api_key", "")
    st.session_state.user_hunter_key = current_config.get("hunter_api_key", "")
    st.session_state.user_sender_email = current_config.get("sender_email", "")
    st.session_state.user_app_password = current_config.get("sender_app_password", "")
    
    # Load user's saved resume if it exists
    res_bytes, res_filename, res_text = load_user_resume(st.session_state.current_user)
    if res_bytes:
        st.session_state.resume_bytes = res_bytes
        st.session_state.resume_filename = res_filename
        st.session_state.resume_text = res_text
        
    st.session_state.config_loaded = True

# --- AUTHORIZED DASHBOARD WORKFLOW ---
col_head1, col_head2 = st.columns([8, 2])
with col_head1:
    st.markdown(f"""
    <div class="dash-header">
        <div>
            <div class="dash-logo-text">CareerFlow AI Dashboard</div>
            <div class="dash-sub-text">Welcome back, <b>{st.session_state.current_user}</b>. Role: <b>{st.session_state.current_user.capitalize()}</b>.</div>
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

# --- SIDEBAR: Configuration & Uploads (Isolated & Persisted) ---
with st.sidebar:
    st.markdown(f"### User Session: {st.session_state.current_user.capitalize()}")
    render_theme_toggle("sidebar_")
    st.markdown("---")
    st.markdown("Enter your personal API keys below. They are isolated from other users.")
    
    # Session-bound credential inputs
    user_gemini = st.text_input(
        "Your Gemini API Key",
        type="password",
        value=st.session_state.user_gemini_key,
        help="Obtain a free key from Google AI Studio."
    )
    st.markdown("[Get a free Gemini API Key](https://aistudio.google.com/)")
        
    user_hunter = st.text_input(
        "Your Hunter.io API Key (Optional)",
        type="password",
        value=st.session_state.user_hunter_key,
        help="Free key for email finder. Fallback guesser runs if empty."
    )
    st.markdown("[Get a free Hunter.io API Key](https://hunter.io/)")
    
    st.markdown("---")
    st.markdown("### Your Mail Server SMTP")
    user_email = st.text_input(
        "Your Gmail Address", 
        value=st.session_state.user_sender_email,
        placeholder="you@gmail.com"
    )
    user_app_pw = st.text_input(
        "Your Gmail App Password",
        type="password",
        value=st.session_state.user_app_password,
        help="Generate a 16-character App Password in Google Account Security."
    )
    st.markdown("[Generate a Google App Password](https://myaccount.google.com/apppasswords)")
    
    # Update temporary session states on widget change
    st.session_state.user_gemini_key = user_gemini
    st.session_state.user_hunter_key = user_hunter
    st.session_state.user_sender_email = user_email
    st.session_state.user_app_password = user_app_pw

    # Option to save keys permanently (private to user)
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
                st.success("Credentials cleared from profile.")
                st.rerun()
            except Exception:
                st.error("Failed to clear credentials.")

    st.markdown("---")
    st.markdown("### Upload Resume")
    label_text = "Upload PDF Resume"
    if st.session_state.resume_filename:
        label_text += f" (Current: {st.session_state.resume_filename})"
    uploaded_file = st.file_uploader(label_text, type=["pdf"])
    
    if st.session_state.resume_filename:
        if st.button("Delete Saved Resume", type="secondary", use_container_width=True):
            if delete_user_resume(st.session_state.current_user):
                st.session_state.resume_text = ""
                st.session_state.resume_bytes = None
                st.session_state.resume_filename = ""
                st.success("Saved resume deleted.")
                st.rerun()
            else:
                st.error("Failed to delete resume.")
    
    if uploaded_file is not None:
        if (st.session_state.resume_filename != uploaded_file.name or 
            st.session_state.resume_bytes is None):
            try:
                with st.spinner("Parsing resume PDF text..."):
                    pdf_bytes = uploaded_file.read()
                    text = extract_text_from_pdf(io.BytesIO(pdf_bytes))
                    
                    st.session_state.resume_text = text
                    st.session_state.resume_bytes = pdf_bytes
                    st.session_state.resume_filename = uploaded_file.name
                    st.session_state.ats_results = None
                    # Save PDF permanently for this user
                    save_user_resume(st.session_state.current_user, pdf_bytes, uploaded_file.name)
                st.success(f"Successfully loaded and saved: {uploaded_file.name}")
            except Exception as e:
                st.error(f"Error loading PDF: {str(e)}")

# Define navigation tabs. If admin is logged in, show the Audit Logs tab.
is_admin = st.session_state.current_user == "admin"
if is_admin:
    tab1, tab2, tab3, tab4 = st.tabs(["ATS Compliance and Scoring", "Recruiter Outreach Workspace", "Automated Application Pipeline", "System Audit Logs"])
else:
    tab1, tab2, tab3 = st.tabs(["ATS Compliance and Scoring", "Recruiter Outreach Workspace", "Automated Application Pipeline"])

# --- TAB 1: ATS COMPLIANCE ---
with tab1:
    st.markdown("### Resume Optimization and ATS Evaluator")
    st.markdown("Paste the target job description to compute your match score and discover critical keywords missing from your resume.")
    
    if not st.session_state.resume_text:
        st.info("Please upload your PDF resume in the sidebar to run the ATS Analyzer.")
    else:
        col1, col2 = st.columns([1, 1], gap="large")
        
        with col1:
            st.markdown("##### Job Description Details")
            job_desc_input = st.text_area(
                "Copy/Paste requirements here:",
                height=300,
                placeholder="Seeking a professional proficient in..."
            )
            
            run_ats = st.button("Evaluate ATS Alignment", type="primary", use_container_width=True)
            
        with col2:
            st.markdown("##### Evaluation Summary")
            
            if run_ats:
                if not st.session_state.user_gemini_key:
                    st.error("Error: Please provide your Gemini API Key in the sidebar.")
                elif not job_desc_input.strip():
                    st.error("Error: Please paste a job description first.")
                else:
                    with st.spinner("Running verification..."):
                        try:
                            analysis = analyze_ats_compatibility(
                                st.session_state.resume_text,
                                job_desc_input,
                                st.session_state.user_gemini_key
                            )
                            st.session_state.ats_results = analysis
                        except Exception as e:
                            st.error(f"Evaluation failed: {str(e)}")
            
            if st.session_state.ats_results:
                analysis = st.session_state.ats_results
                score = analysis.get("score", 0)
                angle = int(score * 3.6)
                
                st.markdown(f"""
                <div class="score-circle-container">
                    <div class="radial-score" style="--score-angle: {angle}deg;">
                        <div class="radial-score-value">{score}%</div>
                    </div>
                    <div style="font-weight: 700; font-size: 1.1rem; margin-top: 1rem; color: #CBD5E1;">Compatibility Match</div>
                </div>
                """, unsafe_allow_html=True)
                
                st.markdown(f"""
                <div class="glass-card">
                    <div style="font-weight:600; color:#818CF8; margin-bottom:0.4rem;">Assessment:</div>
                    <p style="font-size:0.95rem; line-height:1.5; color:#94A3B8; margin:0;">{analysis.get('summary', '')}</p>
                </div>
                """, unsafe_allow_html=True)
                
                sub_col1, sub_col2 = st.columns(2)
                with sub_col1:
                    st.markdown("<span class='badge badge-success'>Matched Keywords</span>", unsafe_allow_html=True)
                    matched = analysis.get("matched_skills", [])
                    if matched:
                        st.markdown("<div style='margin-top:0.5rem;'></div>", unsafe_allow_html=True)
                        for m in matched:
                            st.markdown(f"✓ `{m}`")
                    else:
                        st.markdown("<p style='color:#64748B; font-style:italic;'>No matches identified.</p>", unsafe_allow_html=True)
                        
                with sub_col2:
                    st.markdown("<span class='badge badge-error'>Missing Keywords</span>", unsafe_allow_html=True)
                    missing = analysis.get("missing_skills", [])
                    if missing:
                        st.markdown("<div style='margin-top:0.5rem;'></div>", unsafe_allow_html=True)
                        for ms in missing:
                            st.markdown(f"✗ **{ms}**")
                    else:
                        st.markdown("<p style='color:#64748B; font-style:italic;'>No critical skill gaps.</p>", unsafe_allow_html=True)
                
                st.markdown("<div style='margin-top:1.5rem;'></div>", unsafe_allow_html=True)
                st.markdown("##### Actionable Improvement Tips")
                tips = analysis.get("actionable_tips", [])
                for tip in tips:
                    st.info(tip)
            else:
                st.info("Awaiting input. Paste a target job description and run the analyzer to get started.")

# --- TAB 2: RECRUITER OUTREACH ---
with tab2:
    st.markdown("### Recruiter Finder and Automatic Mailer")
    st.markdown("Locate recruiter contacts at target companies, personalize custom outreach drafts using Gemini, and submit applications.")
    
    if not st.session_state.resume_text:
        st.info("Please upload your PDF resume in the sidebar to access the Outreach workspace.")
    else:
        # Check system setup
        if not st.session_state.user_gemini_key:
            st.warning("Please configure your Gemini API Key in the sidebar to generate outreach drafts.")
        if not st.session_state.user_sender_email or not st.session_state.user_app_password:
            st.warning("Enter your Gmail details and App Password in the sidebar to enable sending.")
            
        c_search, c_manual = st.columns([1.2, 0.8], gap="large")
        
        with c_search:
            st.markdown("""
            <div class="glass-card">
                <h5 style="color:#818CF8; margin-top:0;">Search Target Recruiter Profiles</h5>
            </div>
            """, unsafe_allow_html=True)
            
            sc1, sc2 = st.columns(2)
            with sc1:
                company_name_input = st.text_input("Target Company", placeholder="e.g. Coinbase")
            with sc2:
                role_kw_input = st.text_input("Role Keywords", value="Recruiter, Talent Acquisition, Hiring Manager")
                
            limit_search = st.slider("Max Search Leads", min_value=1, max_value=8, value=3)
            search_triggered = st.button("Launch Auto Search and Resolve", type="primary", use_container_width=True)
            
        with c_manual:
            st.markdown("""
            <div class="glass-card">
                <h5 style="color:#818CF8; margin-top:0;">Manual LinkedIn Entry</h5>
            </div>
            """, unsafe_allow_html=True)
            
            manual_urls = st.text_area(
                "Profile links (comma or newline separated):",
                height=110,
                placeholder="https://www.linkedin.com/in/recruiter-profile-slug"
            )
            manual_company = st.text_input("Company Target for Manual Profiles", placeholder="e.g. Stripe")
            manual_triggered = st.button("Process Manual Profiles", use_container_width=True)
            
        # Process Auto Search
        if search_triggered:
            if not company_name_input.strip():
                st.error("Target Company is required.")
            else:
                with st.spinner("Retrieving recruiter profiles via search..."):
                    kws = [k.strip() for k in role_kw_input.split(",")]
                    scraped_leads = search_recruiters(company_name_input.strip(), kws, limit=limit_search)
                    
                if not scraped_leads:
                    st.warning("No matches found. Try modifying role keywords.")
                else:
                    with st.spinner("Resolving emails and corporate domain formats..."):
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
                    
        # Process Manual Input
        if manual_triggered:
            if not manual_urls.strip():
                st.error("Please insert at least one LinkedIn URL.")
            else:
                with st.spinner("Parsing profile references..."):
                    parsed_leads = parse_manual_linkedin_urls(manual_urls, manual_company)
                    
                if not parsed_leads:
                    st.warning("No valid profile paths found.")
                else:
                    with st.spinner("Resolving corporate addresses..."):
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
                    st.success(f"Imported {len(st.session_state.leads)} manual leads.")
                    
        # --- Leads Workspace ---
        if st.session_state.leads:
            st.write("---")
            st.markdown("#### Discovered Outreach Leads")
            
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
                
                if st.button(f"Configure Outreach Draft for {lead['name']}", key=f"gen_{idx}"):
                    if not st.session_state.user_gemini_key:
                        st.error("Please configure your Gemini API Key in the sidebar to proceed.")
                    else:
                        with st.spinner(f"Drafting email for {lead['name']}..."):
                            try:
                                draft = generate_outreach_email(
                                    st.session_state.resume_text,
                                    lead["name"],
                                    lead["title"],
                                    lead["company"],
                                    job_desc="Hiring opportunities matching my resume background",
                                    api_key=st.session_state.user_gemini_key
                                )
                                st.session_state.drafts[idx] = draft
                            except Exception as e:
                                st.error(f"Draft failed: {str(e)}")
                                
            # Draft Composer
            if st.session_state.drafts:
                st.write("---")
                st.markdown("#### Personalized Draft Workspace")
                
                draft_options = {idx: f"{st.session_state.leads[idx]['name']} ({st.session_state.leads[idx]['company']})" for idx in st.session_state.drafts.keys()}
                selected_draft_idx = st.selectbox("Choose draft to manage:", options=list(draft_options.keys()), format_func=lambda x: draft_options[x])
                
                selected_lead = st.session_state.leads[selected_draft_idx]
                selected_draft = st.session_state.drafts[selected_draft_idx]
                
                # Edit Area
                edit_subject = st.text_input("Email Subject Line", value=selected_draft.get("subject", ""))
                edit_body = st.text_area("Personalized Message Body", value=selected_draft.get("body", ""), height=250)
                
                # Handle email selector if fallback guesses were made
                if "all_guesses" in selected_lead and len(selected_lead["all_guesses"]) > 1:
                    alt_email = st.selectbox(
                        "Verify recipient address pattern:",
                        options=selected_lead["all_guesses"],
                        index=selected_lead["all_guesses"].index(selected_lead["email"]) if selected_lead["email"] in selected_lead["all_guesses"] else 0
                    )
                    selected_lead["email"] = alt_email
                    
                recipient_email_input = st.text_input("Send To Contact:", value=selected_lead["email"])
                
                col_snd1, col_snd2 = st.columns([1.5, 3.5])
                with col_snd1:
                    send_btn = st.button("Deliver Resume Now", type="primary", use_container_width=True)
                with col_snd2:
                    st.write(f"Will transmit PDF resume: **{st.session_state.resume_filename}** as attachment.")
                    
                if send_btn:
                    if not st.session_state.user_sender_email or not st.session_state.user_app_password:
                        st.error("Error: Please provide your Gmail and App Password in the sidebar.")
                    elif not recipient_email_input.strip():
                        st.error("Error: Recipient email address is missing.")
                    else:
                        with st.spinner("Transmitting message and resume PDF..."):
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
                                    # Log this transaction to the audit file
                                    log_email_transaction(
                                        username=st.session_state.current_user,
                                        recruiter=selected_lead["name"],
                                        company=selected_lead["company"],
                                        recipient=recipient_email_input.strip(),
                                        status="Success"
                                    )
                            except Exception as e:
                                st.error(f"Transmission failed: {str(e)}")
                                # Log failure
                                log_email_transaction(
                                    username=st.session_state.current_user,
                                    recruiter=selected_lead["name"],
                                    company=selected_lead["company"],
                                    recipient=recipient_email_input.strip(),
                                    status=f"Failed: {str(e)}"
                                )

# --- TAB 3: AUTOMATED APPLICATION PIPELINE ---
with tab3:
    st.markdown("### Automated Search and Apply Pipeline")
    st.markdown("Scan public Greenhouse and Lever listings to discover hiring companies, resolve their recruiter contacts, draft custom cover letters, and send applications.")
    
    if not st.session_state.resume_text:
        st.info("Please upload your PDF resume in the sidebar to access the Pipeline workspace.")
    else:
        # Check system setup
        if not st.session_state.user_gemini_key:
            st.error("Please configure your Gemini API Key in the sidebar to run the pipeline.")
        if not st.session_state.user_sender_email or not st.session_state.user_app_password:
            st.warning("Enter your Gmail details and App Password in the sidebar to enable automatic sending.")
            
        col_pipe1, col_pipe2 = st.columns([1.2, 0.8], gap="large")
        with col_pipe1:
            st.markdown("""
            <div class="glass-card">
                <h5 style="color:#818CF8; margin-top:0;">Discover Hiring Companies</h5>
            </div>
            """, unsafe_allow_html=True)
            
            pc1, pc2 = st.columns(2)
            with pc1:
                pipe_job_title = st.text_input("Target Job Title", value="Software Developer", key="pipe_title")
            with pc2:
                pipe_location = st.text_input("Location Filter", value="India", key="pipe_loc")
                
            pipe_limit = st.slider("Scan limit (Max companies)", min_value=1, max_value=15, value=5, key="pipe_lim")
            scan_triggered = st.button("Scan for Hiring Companies", type="primary", use_container_width=True)
            
        with col_pipe2:
            st.markdown("""
            <div class="glass-card">
                <h5 style="color:#818CF8; margin-top:0;">Active Pipeline Console</h5>
                <p style="font-size:0.85rem; color:#94A3B8; margin:0;">Dispatched emails are logged automatically.</p>
            </div>
            """, unsafe_allow_html=True)
            
        # Process Company Scan
        if scan_triggered:
            if not pipe_job_title.strip():
                st.error("Job title keyword is required.")
            else:
                with st.spinner("Scanning Lever and Greenhouse boards..."):
                    from scraper import find_hiring_companies
                    st.session_state.discovered_jobs = find_hiring_companies(
                        pipe_job_title.strip(), 
                        pipe_location.strip(), 
                        limit=pipe_limit
                    )
                if not st.session_state.discovered_jobs:
                    st.warning("No job boards resolved for these keywords.")
                else:
                    st.success(f"Discovered {len(st.session_state.discovered_jobs)} hiring companies.")
                    st.session_state.pipeline_logs = {}
                    
        # Render Discovered Jobs & Auto-Apply Workflow
        if st.session_state.discovered_jobs:
            st.write("---")
            st.markdown("#### Discovered Hiring Opportunities")
            st.markdown("Click 'Yes, Apply Automatically' under any company to search for their recruiter, write a custom cover letter matching your resume, and send it immediately.")
            
            for idx, job in enumerate(st.session_state.discovered_jobs):
                c_info, c_action = st.columns([3, 1])
                with c_info:
                    st.markdown(f"**{job['company']}** — *{job['role']}*")
                    st.markdown(f"URL: <a href='{job['url']}' target='_blank' style='color:#60A5FA;'>View Job Board listing</a>", unsafe_allow_html=True)
                    
                    # Display logs for this specific application
                    if idx in st.session_state.pipeline_logs:
                        log_data = st.session_state.pipeline_logs[idx]
                        if log_data["status"] == "success":
                            st.success(log_data["msg"])
                        elif log_data["status"] == "error":
                            st.error(log_data["msg"])
                        else:
                            st.info(log_data["msg"])
                            
                with c_action:
                    # Action button
                    apply_btn = st.button(f"Yes, Apply to {job['company']}", key=f"pipe_apply_{idx}", use_container_width=True)
                    
                    if apply_btn:
                        if not st.session_state.user_gemini_key:
                            st.error("Gemini API key is required.")
                        elif not st.session_state.user_sender_email or not st.session_state.user_app_password:
                            st.error("Gmail configuration is required.")
                        else:
                            st.session_state.pipeline_logs[idx] = {"status": "running", "msg": "Initializing application pipeline..."}
                            # Step 1: Search Recruiter
                            with st.spinner(f"Locating recruiter at {job['company']}..."):
                                recruiter_kws = ["Recruiter", "Talent Acquisition", "Hiring Manager"]
                                recruiters = search_recruiters(job["company"], recruiter_kws, limit=1)
                                
                            recruiter_name = "Hiring Manager"
                            recruiter_title = "Recruiter"
                            
                            if recruiters:
                                recruiter_name = recruiters[0]["name"]
                                recruiter_title = recruiters[0]["title"]
                                
                            # Step 2: Resolve Email
                            with st.spinner(f"Resolving email for {recruiter_name}..."):
                                resolved = resolve_email(
                                    recruiter_name,
                                    recruiter_name,
                                    job["company"],
                                    hunter_api_key=st.session_state.user_hunter_key
                                )
                                recruiter_email = resolved["email"]
                                
                            if not recruiter_email:
                                st.session_state.pipeline_logs[idx] = {
                                    "status": "error", 
                                    "msg": f"Failed: Could not resolve email pattern for {job['company']}."
                                }
                            else:
                                # Step 3: Write personalized outreach
                                with st.spinner("Drafting cover message..."):
                                    try:
                                        draft = generate_outreach_email(
                                            resume_text=st.session_state.resume_text,
                                            recruiter_name=recruiter_name,
                                            recruiter_title=recruiter_title,
                                            company=job["company"],
                                            job_desc=job["role"],
                                            api_key=st.session_state.user_gemini_key
                                        )
                                    except Exception as e:
                                        draft = None
                                        st.session_state.pipeline_logs[idx] = {
                                            "status": "error",
                                            "msg": f"Failed to draft message: {str(e)}"
                                        }
                                        
                                if draft:
                                    # Step 4: Dispatch email
                                    with st.spinner("Dispatched outreach via SMTP..."):
                                        try:
                                            success = send_outreach_email(
                                                sender_email=st.session_state.user_sender_email,
                                                sender_password=st.session_state.user_app_password,
                                                recipient_email=recruiter_email,
                                                subject=draft.get("subject", f"Outreach: {job['role']} role at {job['company']}"),
                                                body=draft.get("body", ""),
                                                resume_bytes=st.session_state.resume_bytes,
                                                resume_filename=st.session_state.resume_filename
                                            )
                                            if success:
                                                msg = f"Dispatched cover email and resume to {recruiter_name} ({recruiter_email})"
                                                st.session_state.pipeline_logs[idx] = {
                                                    "status": "success",
                                                    "msg": msg
                                                }
                                                log_email_transaction(
                                                    username=st.session_state.current_user,
                                                    recruiter=recruiter_name,
                                                    company=job["company"],
                                                    recipient=recruiter_email,
                                                    status="Success (Auto-Pipeline)"
                                                )
                                        except Exception as e:
                                            st.session_state.pipeline_logs[idx] = {
                                                "status": "error",
                                                "msg": f"Failed to send email: {str(e)}"
                                            }
                                            log_email_transaction(
                                                username=st.session_state.current_user,
                                                recruiter=recruiter_name,
                                                company=job["company"],
                                                recipient=recruiter_email,
                                                status=f"Failed (Auto-Pipeline): {str(e)}"
                                            )
                            st.rerun()

# --- TAB 4: SYSTEM AUDIT LOGS (ADMIN ONLY) ---
if is_admin:
    with tab4:
        st.markdown("### System Audit Logs")
        st.markdown("Monitor email transaction history across all active team members using the platform.")
        
        # Load transaction logs from local audit file
        logs = load_audit_logs()
        
        if not logs:
            st.info("No transaction logs recorded yet.")
        else:
            # Action button to clear logs
            col_clear1, col_clear2 = st.columns([8, 2])
            with col_clear2:
                if st.button("Clear Audit Log History", type="secondary", use_container_width=True):
                    try:
                        os.remove(AUDIT_LOG_FILE)
                        st.success("Audit history cleared.")
                        time.sleep(0.5)
                        st.rerun()
                    except Exception as e:
                        st.error(f"Failed to clear history: {str(e)}")
                        
            # Format and display logs in a clean table
            st.dataframe(
                logs,
                column_config={
                    "timestamp": "Timestamp",
                    "user": "User Profile",
                    "recruiter": "Recipient Recruiter",
                    "company": "Company",
                    "recipient": "Email Address",
                    "status": "Delivery Status"
                },
                use_container_width=True
            )
