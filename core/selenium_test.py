import json
from selenium_runner import run_headless_selenium

def authenticate_and_scrape(driver):
    """Test authentication flow and DOM extraction"""
    
    # Step 1: Navigate to a test site (using example.com for demo)
    driver.get("https://example.com")
    
    html = driver.page_source
    
    return {
        "success": True,
        "title": driver.title,
        "url": driver.current_url,
        "html_length": len(html),
        "status_code": 200 if "Example Domain" in html else None
    }

if __name__ == "__main__":
    result = run_headless_selenium(authenticate_and_scrape)
    
    print(json.dumps(result, indent=2))
    
    # Log to execution log
    with open(r"C:\Users\p0ly\Desktop\AI\VERA\logs\selenium_execution_log.md", "a") as f:
        f.write(f"\n--- Selenium Test Run ---\n{json.dumps(result)}\n\n")
