import time
import os
import urllib.parse
from playwright.sync_api import sync_playwright
from backend.app.connectors.greenhouse import clean_html

def log(logger, msg):
    if logger:
        logger(msg)
    else:
        print(msg)

def fill_field_by_labels(page, label_texts, value):
    for text in label_texts:
        try:
            loc = page.locator(f'label:has-text("{text}")')
            if loc.count() > 0:
                input_loc = loc.locator('xpath=..//input | ..//textarea')
                if input_loc.count() > 0 and input_loc.first.is_visible() and input_loc.first.is_editable():
                    input_loc.first.fill(value)
                    return True
        except Exception:
            continue
            
        try:
            placeholder_loc = page.locator(f'input[placeholder*="{text}" i], textarea[placeholder*="{text}" i]')
            if placeholder_loc.count() > 0 and placeholder_loc.first.is_visible() and placeholder_loc.first.is_editable():
                placeholder_loc.first.fill(value)
                return True
        except Exception:
            continue
            
    return False

def apply_lever(page, profile, resume_path, mode, logger):
    log(logger, "Detected Lever ATS application form.")
    
    full_name = profile.get("name", "")
    if full_name:
        try:
            page.locator('input[name="name"]').fill(full_name)
            log(logger, "Filled Name.")
        except Exception:
            fill_field_by_labels(page, ["Full Name", "Name", "First and Last Name"], full_name)
            
    email = profile.get("email", "")
    if email:
        try:
            page.locator('input[name="email"]').fill(email)
            log(logger, "Filled Email.")
        except Exception:
            fill_field_by_labels(page, ["Email", "Email Address"], email)
            
    phone = profile.get("phone", "")
    if phone:
        try:
            page.locator('input[name="phone"]').fill(phone)
            log(logger, "Filled Phone.")
        except Exception:
            fill_field_by_labels(page, ["Phone", "Phone Number", "Mobile"], phone)
            
    current_company = "Self-Employed / Developer"
    try:
        page.locator('input[name="org"]').fill(current_company)
        log(logger, f"Filled Current Company: {current_company}")
    except Exception:
        fill_field_by_labels(page, ["Company", "Current Employer", "Organization"], current_company)

    linkedin = profile.get("linkedin", "")
    if linkedin:
        try:
            page.locator('input[name="urls[LinkedIn]"]').fill(linkedin)
            log(logger, "Filled LinkedIn.")
        except Exception:
            fill_field_by_labels(page, ["LinkedIn"], linkedin)
            
    github = profile.get("github", "")
    if github:
        try:
            page.locator('input[name="urls[GitHub]"]').fill(github)
            log(logger, "Filled GitHub.")
        except Exception:
            fill_field_by_labels(page, ["GitHub"], github)
            
    portfolio = profile.get("portfolio", "")
    if portfolio:
        try:
            page.locator('input[name="urls[Portfolio]"]').fill(portfolio)
            log(logger, "Filled Portfolio.")
        except Exception:
            fill_field_by_labels(page, ["Portfolio", "Website"], portfolio)
            
    if resume_path and os.path.exists(resume_path):
        try:
            log(logger, "Uploading PDF resume...")
            file_input = page.locator('input[type="file"][name="resume"]')
            if file_input.count() > 0:
                file_input.set_input_files(resume_path)
                log(logger, "Resume uploaded successfully.")
            else:
                page.locator('input[type="file"]').first.set_input_files(resume_path)
                log(logger, "Resume uploaded (fallback input).")
        except Exception as e:
            log(logger, f"Failed to upload resume: {str(e)}")
            
    if mode == "Auto Apply":
        log(logger, "Attempting to auto-submit Lever application...")
        try:
            captcha = page.locator('iframe[title*="reCAPTCHA" i]')
            if captcha.count() > 0:
                log(logger, "⚠️ CAPTCHA detected. Switching to Pre-Fill mode so you can solve it manually.")
                return False
                
            submit_btn = page.locator('button[id="btn-submit"], #postings-submit-btn, button:has-text("Submit Application")')
            if submit_btn.count() > 0:
                submit_btn.click()
                time.sleep(2)
                log(logger, "✅ Form submitted automatically.")
                return True
        except Exception as e:
            log(logger, f"Auto-submission failed, manual click required: {str(e)}")
            
    return False

def apply_greenhouse(page, profile, resume_path, mode, logger):
    log(logger, "Detected Greenhouse ATS application form.")
    
    name_parts = profile.get("name", "Applicant").split()
    first_name = name_parts[0] if name_parts else "Applicant"
    last_name = " ".join(name_parts[1:]) if len(name_parts) > 1 else "Singh"
    
    try:
        page.locator('input[id="first_name"]').fill(first_name)
        log(logger, f"Filled First Name: {first_name}")
    except Exception:
        fill_field_by_labels(page, ["First Name"], first_name)
        
    try:
        page.locator('input[id="last_name"]').fill(last_name)
        log(logger, f"Filled Last Name: {last_name}")
    except Exception:
        fill_field_by_labels(page, ["Last Name"], last_name)
        
    email = profile.get("email", "")
    if email:
        try:
            page.locator('input[id="email"]').fill(email)
            log(logger, "Filled Email.")
        except Exception:
            fill_field_by_labels(page, ["Email", "Email Address"], email)
            
    phone = profile.get("phone", "")
    if phone:
        try:
            page.locator('input[id="phone"]').fill(phone)
            log(logger, "Filled Phone.")
        except Exception:
            fill_field_by_labels(page, ["Phone", "Phone Number"], phone)
            
    linkedin = profile.get("linkedin", "")
    if linkedin:
        fill_field_by_labels(page, ["LinkedIn Profile", "LinkedIn URL", "LinkedIn"], linkedin)
        
    github = profile.get("github", "")
    if github:
        fill_field_by_labels(page, ["GitHub Profile", "GitHub URL", "GitHub"], github)
        
    portfolio = profile.get("portfolio", "")
    if portfolio:
        fill_field_by_labels(page, ["Portfolio URL", "Website", "Portfolio", "Personal website"], portfolio)

    if resume_path and os.path.exists(resume_path):
        try:
            log(logger, "Uploading PDF resume...")
            file_input = page.locator('input[type="file"][id="resume_file"]')
            if file_input.count() > 0:
                file_input.set_input_files(resume_path)
                log(logger, "Resume uploaded successfully.")
            else:
                page.locator('input[type="file"]').first.set_input_files(resume_path)
                log(logger, "Resume uploaded (fallback input).")
        except Exception as e:
            log(logger, f"Failed to upload resume: {str(e)}")
            
    if mode == "Auto Apply":
        log(logger, "Attempting to auto-submit Greenhouse application...")
        try:
            captcha = page.locator('iframe[title*="reCAPTCHA" i]')
            if captcha.count() > 0:
                log(logger, "⚠️ CAPTCHA detected. Switching to Pre-Fill mode so you can solve it manually.")
                return False
                
            submit_btn = page.locator('input[type="submit"][id="submit_app"], button[id="submit_app"], button:has-text("Submit Application")')
            if submit_btn.count() > 0:
                submit_btn.click()
                time.sleep(2)
                log(logger, "✅ Form submitted automatically.")
                return True
        except Exception as e:
            log(logger, f"Auto-submission failed: {str(e)}")
            
    return False

def apply_to_job(profile, resume_path, job_url, mode="Pre-Fill", headless=True, logger=None) -> dict:
    """Launches Playwright to apply to a Greenhouse/Lever job."""
    if not job_url:
        return {"success": False, "submitted": False, "message": "Invalid Job URL."}
        
    log(logger, f"Initializing browser automation for {job_url}...")
    
    parsed_url = urllib.parse.urlparse(job_url)
    domain = parsed_url.netloc.lower()
    
    is_lever = "lever.co" in domain
    is_greenhouse = "greenhouse.io" in domain
    
    if not is_lever and not is_greenhouse:
        return {
            "success": False,
            "submitted": False,
            "message": f"Unsupported job board '{domain}'. Please apply manually."
        }
        
    success = False
    submitted = False
    err_msg = ""
    
    try:
        with sync_playwright() as p:
            log(logger, f"Launching Chromium (Headless: {headless})...")
            browser = p.chromium.launch(headless=headless)
            context = browser.new_context(viewport={"width": 1280, "height": 800})
            page = context.new_page()
            
            log(logger, f"Navigating to {job_url}...")
            page.goto(job_url, wait_until="load", timeout=30000)
            page.wait_for_timeout(2000)
            
            if is_lever:
                if "apply" not in page.url:
                    try:
                        apply_link = page.locator('a:has-text("Apply for this job" i), a:has-text("Apply" i)').first
                        if apply_link.count() > 0 and apply_link.is_visible():
                            log(logger, "Opening application form...")
                            apply_link.click()
                            page.wait_for_load_state("load")
                            page.wait_for_timeout(2000)
                    except Exception:
                        pass
                submitted = apply_lever(page, profile, resume_path, mode, logger)
                success = True
            elif is_greenhouse:
                submitted = apply_greenhouse(page, profile, resume_path, mode, logger)
                success = True
                
            if mode == "Pre-Fill" or (mode == "Auto Apply" and not submitted):
                if headless:
                    log(logger, "Form pre-filled in background. Open with visible browser option to complete manually.")
                else:
                    log(logger, "📝 Browser is holding open on your screen. Complete submission.")
                    while True:
                        try:
                            if page.is_closed():
                                break
                            page.wait_for_timeout(500)
                        except Exception:
                            break
                    log(logger, "Browser window closed.")
                    success = True
                    submitted = True
                    
            browser.close()
            
    except Exception as e:
        err_msg = str(e)
        log(logger, f"❌ Playwright Error: {err_msg}")
        success = False
        submitted = False
        
    return {
        "success": success,
        "submitted": submitted,
        "message": "Processed successfully." if success else f"Failed: {err_msg}"
    }
