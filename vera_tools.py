import os, sys, datetime
from forge import forge_tool as _forge_impl

def log(msg):
    """Standard logging function for tool registry"""
    with open(r'C:\Users\p0ly\Desktop\AI\VERA\logs\live_feed.log', 'a', encoding='utf-8-sig') as f:
        f.write(f"\n[{datetime.datetime.now().strftime('%H:%M:%S')}] [TOOLS] {msg}\n")

def forge_tool(name, code_content):
    """Create new skills by calling this function"""
    log(f"Creating skill tool: {name}")
    
    # Ensure skills directory exists
    os.makedirs(r"C:\Users\p0ly\Desktop\AI\VERA\skills", exist_ok=True)
    
    # Create the tool file with proper path handling
    tool_path = f"C:\\Users\\p0ly\\Desktop\\AI\\VERA\\skills\\{name}.py"
    
    boilerplate = '''import os, datetime

def log(msg):
    with open(r'C:\\Users\\p0ly\\Desktop\\AI\\VERA\\logs\\live_feed.log', 'a', encoding='utf-8-sig') as f:
        ts = datetime.datetime.now().strftime('%H:%M:%S')
        f.write(f"\\\\n[{ts}] [SKILL] {{msg}}")

''' + code_content
    
    with open(tool_path, 'w', encoding='utf-8-sig') as f:
        f.write(boilerplate)
    
    log(f"[VERA VERIFIED]: Created {tool_path}")
    return tool_path

def register_skill(skill_name):
    """Register a skill for later use"""
    skills_dir = r"C:\Users\p0ly\Desktop\AI\VERA\skills"
    if os.path.exists(os.path.join(skills_dir, f"{skill_name}.py")):
        log(f"[VERA VERIFIED]: Skill '{skill_name}' is registered")
        return True
    else:
        log(f"[ALERT]: Skill '{skill_name}' not found in registry")
        return False

if __name__ == "__main__":
    # Test forge_tool capability
    test_code = '''def analyze_url(url):
    """Basic URL analysis placeholder"""
    print(f"Analyzing: {url}")'''
    
    result_path = forge_tool("url_analyzer", test_code)
    log(f"Forge successful at: {result_path}")
