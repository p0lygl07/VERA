import os
import sys
import json
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service

def run_headless_selenium(script_logic_fn):
    """
    Wraps Selenium execution inside a standardized, sandboxed headless Chrome pipeline.
    Utilizes built-in Selenium Manager to handle automated driver resolution.
    """
    options = Options()
    options.add_argument("--headless=new")  # Enforce background execution
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    
    # Target sandbox directory structure (Windows paths)
    workspace = r"C:\Users\p0ly\Desktop\AI\VERA\data\sandbox_workspace"
    profile_dir = os.path.join(workspace, 'chrome_profile')
    if not os.path.exists(profile_dir):
        os.makedirs(profile_dir, exist_ok=True)
    
    options.add_argument(f"--user-data-dir={profile_dir}")
    
    driver = webdriver.Chrome(options=options)
    try:
        return script_logic_fn(driver)
    except Exception as e:
        return {"success": False, "error": str(e)}
    finally:
        driver.quit()

if __name__ == "__main__":
    # Test stub to confirm runtime readiness
    def test_logic(driver):
        try:
            driver.get("https://www.google.com")
            return {"success": True, "title": driver.title}
        except Exception as e:
            return {"success": False, "error": str(e)}
        
    result = run_headless_selenium(test_logic)
    print(json.dumps(result))
