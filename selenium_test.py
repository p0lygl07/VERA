import selenium
print(f"Selenium installed: {selenium.__version__}")

try:
    from webdriver_manager.chrome import ChromeDriverManager
    print("webdriver-manager available")
except ImportError as e:
    print(f"Missing dependency: {e}")
