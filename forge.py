import os, datetime, sys

def forge_tool(name, code_content):
    os.makedirs(r"C:\Users\p0ly\Desktop\AI\VERA\skills", exist_ok=True)
    tool_path = f"C:\\Users\\p0ly\\Desktop\\AI\\VERA\\skills\\{name}.py"
    boilerplate = f"""import os, datetime
def log(msg):
    with open(r'C:\\Users\\p0ly\\Desktop\\AI\\VERA\\logs\\live_feed.log', 'a', encoding='utf-8-sig') as f:
        f.write(f"\\n[{{datetime.datetime.now().strftime('%H:%M:%S')}}] [{name.upper()}] {{msg}}")
"""
    with open(tool_path, 'w', encoding='utf-8-sig') as f:
        f.write(boilerplate + "\n" + code_content)
    print(f"FORGE_SUCCESS: {tool_path}")

if __name__ == "__main__":
    # Allows: python forge.py tool_name "code_here"
    name = sys.argv[1]
    content = sys.argv[2]
    forge_tool(name, content)