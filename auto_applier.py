import time
import os
import urllib.parse
from playwright.sync_api import sync_playwright

def log(logger, msg):
    """Helper to output messages to a provided logging function or print."""
    if logger:
        logger(msg)
    else:
        print(msg)

def fill_field_by_labels(page, label_texts, value):
    """
    Finds an input field by scanning labels for specific matching texts
    and fills it with the provided value.
    """
    for text in label_texts:
        try:
            # Look for a label matching the text, then find the nearest input or textarea in its parent tree
            loc = page.locator(f'label:has-text("{text}")')
            if loc.count() > 0:
                # Find sibling or child input
                input_loc = loc.locator('xpath=..//input | ..//textarea')
                if input_loc.count() > 0 and input_loc.first.is_visible() and input_loc.first.is_editable():
                    input_loc.first.fill(value)
                    return True
        except Exception:
            continue
            
        # Try placeholders
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
    
    # Lever inputs are standard but can be inside custom labels
    # 1. Fill Name
    full_name = profile.get("name", "")
    if full_name:
        try:
            page.locator('input[name="name"]').fill(full_name)
            log(logger, "Filled Name.")
        except Exception:
            fill_field_by_labels(page, ["Full Name", "Name", "First and Last Name"], full_name)
            
    # 2. Fill Email
    email = profile.get("email", "")
    if email:
        try:
            page.locator('input[name="email"]').fill(email)
            log(logger, "Filled Email.")
        except Exception:
            fill_field_by_labels(page, ["Email", "Email Address"], email)
            
    # 3. Fill Phone
    phone = profile.get("phone", "")
    if phone:
        try:
            page.locator('input[name="phone"]').fill(phone)
            log(logger, "Filled Phone.")
        except Exception:
            fill_field_by_labels(page, ["Phone", "Phone Number", "Mobile"], phone)
            
    # 4. Current Company
    experience = profile.get("summary", "")
    # Find any company reference or default
    current_company = ""
    projects = profile.get("projects", [])
    if projects:
        current_company = "Self-Employed / Developer"
    try:
        page.locator('input[name="org"]').fill(current_company)
        log(logger, f"Filled Current Company: {current_company}")
    except Exception:
        fill_field_by_labels(page, ["Company", "Current Employer", "Organization"], current_company)

    # 5. Social & Portfolio Links
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
            
    # 6. Upload Resume
    if resume_path and os.path.exists(resume_path):
        try:
            log(logger, "Uploading PDF resume...")
            # Lever standard resume input selector
            file_input = page.locator('input[type="file"][name="resume"]')
            if file_input.count() > 0:
                file_input.set_input_files(resume_path)
                log(logger, "Resume uploaded successfully.")
            else:
                # Fallback to general file input
                page.locator('input[type="file"]').first.set_input_files(resume_path)
                log(logger, "Resume uploaded (fallback input).")
        except Exception as e:
            log(logger, f"Failed to upload resume: {str(e)}")
            
    # 7. Action Submission Check
    if mode == "Auto Apply":
        log(logger, "Attempting to auto-submit Lever application...")
        try:
            # Check if there's any captcha on the page
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
    
    # 1. First Name
    name_parts = profile.get("name", "Applicant").split()
    first_name = name_parts[0] if name_parts else "Applicant"
    last_name = " ".join(name_parts[1:]) if len(name_parts) > 1 else "Singh"
    
    try:
        page.locator('input[id="first_name"]').fill(first_name)
        log(logger, f"Filled First Name: {first_name}")
    except Exception:
        fill_field_by_labels(page, ["First Name"], first_name)
        
    # 2. Last Name
    try:
        page.locator('input[id="last_name"]').fill(last_name)
        log(logger, f"Filled Last Name: {last_name}")
    except Exception:
        fill_field_by_labels(page, ["Last Name"], last_name)
        
    # 3. Email
    email = profile.get("email", "")
    if email:
        try:
            page.locator('input[id="email"]').fill(email)
            log(logger, "Filled Email.")
        except Exception:
            fill_field_by_labels(page, ["Email", "Email Address"], email)
            
    # 4. Phone
    phone = profile.get("phone", "")
    if phone:
        try:
            page.locator('input[id="phone"]').fill(phone)
            log(logger, "Filled Phone.")
        except Exception:
            fill_field_by_labels(page, ["Phone", "Phone Number"], phone)
            
    # 5. Social & Portfolio Links (Greenhouse answers are inside generic question boxes)
    linkedin = profile.get("linkedin", "")
    if linkedin:
        fill_field_by_labels(page, ["LinkedIn Profile", "LinkedIn URL", "LinkedIn"], linkedin)
        
    github = profile.get("github", "")
    if github:
        fill_field_by_labels(page, ["GitHub Profile", "GitHub URL", "GitHub"], github)
        
    portfolio = profile.get("portfolio", "")
    if portfolio:
        fill_field_by_labels(page, ["Portfolio URL", "Website", "Portfolio", "Personal website"], portfolio)

    # 6. Upload Resume
    if resume_path and os.path.exists(resume_path):
        try:
            log(logger, "Uploading PDF resume...")
            # Greenhouse upload is often trigger by clicking button then selecting file, or directly on file input
            file_input = page.locator('input[type="file"][id="resume_file"]')
            if file_input.count() > 0:
                file_input.set_input_files(resume_path)
                log(logger, "Resume uploaded successfully.")
            else:
                page.locator('input[type="file"]').first.set_input_files(resume_path)
                log(logger, "Resume uploaded (fallback input).")
        except Exception as e:
            log(logger, f"Failed to upload resume: {str(e)}")
            
    # 7. Action Submission Check
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

def apply_to_job(profile, resume_path, job_url, mode="Pre-Fill", headless=False, logger=None) -> dict:
    """
    Launches Playwright Chromium browser to pre-fill or automatically apply to a job.
    Returns: {"success": True/False, "submitted": True/False, "message": "..."}
    """
    if not job_url:
        return {"success": False, "submitted": False, "message": "Invalid Job URL."}
        
    log(logger, f"Initializing browser automation for {job_url}...")
    
    parsed_url = urllib.parse.urlparse(job_url)
    domain = parsed_url.netloc.lower()
    
    # Classify board type
    is_lever = "lever.co" in domain
    is_greenhouse = "greenhouse.io" in domain
    
    if not is_lever and not is_greenhouse:
        # Fallback to manual apply warning
        return {
            "success": False,
            "submitted": False,
            "message": f"Unsupported job board '{domain}'. Direct link opened in Manual Mode."
        }
        
    success = False
    submitted = False
    err_msg = ""
    
    # Run Playwright
    try:
        with sync_playwright() as p:
            log(logger, f"Launching Chromium (Headless: {headless})...")
            browser = p.chromium.launch(headless=headless)
            
            # Setup context with normal window dimensions
            context = browser.new_context(viewport={"width": 1280, "height": 800})
            page = context.new_page()
            
            log(logger, f"Navigating to {job_url}...")
            page.goto(job_url, wait_until="domcontentloaded", timeout=15000)
            page.wait_for_timeout(1000)
            
            # Fill form depending on site
            if is_lever:
                if "apply" not in page.url:
                    try:
                        apply_link = page.locator('a:has-text("Apply for this job" i), a:has-text("Apply" i)').first
                        if apply_link.count() > 0 and apply_link.is_visible():
                            log(logger, "Clicking 'Apply' button to open application form...")
                            apply_link.click()
                            page.wait_for_timeout(1000)
                    except Exception:
                        pass
                submitted = apply_lever(page, profile, resume_path, mode, logger)
                success = True
            elif is_greenhouse:
                submitted = apply_greenhouse(page, profile, resume_path, mode, logger)
                success = True
            else:
                log(logger, "Pre-filled application form.")
                success = True
                submitted = False
                
            if mode == "Pre-Fill":
                log(logger, "Form pre-filled successfully.")
                # Non-blocking delay to leave visible browser open for user review
                if not headless:
                    time.sleep(5)
                browser.close()
            else:
                browser.close()
            
    except Exception as e:
        err_msg = str(e)
        log(logger, f"❌ Playwright Automation Error: {err_msg}")
        success = False
        submitted = False
        
    return {
        "success": success,
        "submitted": submitted,
        "message": "Application processed." if success else f"Failed: {err_msg}"
    }
