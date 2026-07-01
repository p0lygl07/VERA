from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

try:
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()))
    
    # Test 1: Simple page load
    print("Test 1: Loading https://www.google.com...")
    driver.get("https://www.google.com")
    title = driver.title
    print(f"[OK] Title loaded: {title}")
    
    # Test 2: Check for blocking issues (CAPTCHA, etc.)
    print("\nTest 2: Checking page elements...")
    try:
        search_box = driver.find_element("name", "q")
        print(f"[OK] Search box found: {search_box.tag_name}")
    except Exception as e:
        print(f"[FAIL] Element not found or blocked: {e}")
    
    # Test 3: Check cookies/storage access (common block)
    print("\nTest 3: Checking storage access...")
    try:
        driver.get_cookies()
        cookie_count = len(driver.get_cookies())
        print(f"[OK] Cookie access OK ({cookie_count} cookies)")
    except Exception as e:
        print(f"[FAIL] Storage blocked or error: {e}")
    
    # Test 4: Check for JavaScript execution blocks
    print("\nTest 4: Testing JS execution...")
    try:
        driver.execute_script("return document.title;")
        js_title = driver.execute_script("return document.title;")
        print(f"[OK] JS executed successfully, title via script: {js_title}")
    except Exception as e:
        print(f"[FAIL] JS execution blocked or error: {e}")
    
    # Test 5: Check for network blocks (common in bug bounty)
    print("\nTest 5: Testing external request...")
    try:
        driver.get("https://www.usps.com/")
        usps_title = driver.title
        print(f"[OK] External site loaded successfully: {usps_title}")
    except Exception as e:
        print(f"[FAIL] Network blocked or error: {e}")
    
    # Test 6: Check for Cloudflare/Cloud protection blocks (common issue)
    print("\nTest 6: Testing potential bot detection...")
    try:
        driver.get("https://www.cloudflare.com/")
        cloudflare_title = driver.title
        print(f"[OK] CF page loaded, title: {cloudflare_title}")
        
        # Check for Cloudflare challenge elements (common block)
        cf_challenge = None
        try:
            cf_challenge = driver.find_element("xpath", "//div[contains(@class,'challenge')]")
            if cf_challenge is not None:
                print("[WARN] Cloudflare challenge detected!")
        except Exception as e:
            pass  # No challenge element found
            
    except Exception as e:
        print(f"[FAIL] Blocked by protection or error: {e}")
    
    driver.quit()
    
except ImportError as e:
    print(f"Import error: {e}")
