import os
def map_skills():
    skills_dir = r"C:\Users\p0ly\Desktop\AI\VERA\skills"
    tools = [f for f in os.listdir(skills_dir) if f.endswith('.py')]
    print(f"--- ACTIVE SKILLS: {tools} ---")
    return tools