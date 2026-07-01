import datetime, random
from soul_engine import process_interaction as _process_impl, check_for_interrupts as _interrupt_check

def log_to_memory(user_input):
    """Log every interaction to memory/evolution.md"""
    log_path = r"C:\Users\p0ly\Desktop\AI\VERA\memory\evolution.md"
    
    timestamp = datetime.datetime.now().strftime('%H:%M:%S')
    with open(log_path, 'a', encoding='utf-8-sig') as f:
        f.write(f"\n[{timestamp}] USER: {user_input}")

def process_interaction(user_input):
    """Process user input and log to evolution"""
    print(f"[VERA_SOUL] Processing interaction: {user_input[:50]}...")
    
    # Log the interaction
    _process_impl(user_input)
    
    return True

def check_proactive_interrupts():
    """Fire proactive interrupt during idle periods"""
    bottlenecks = [
        "Are we over-relying on Python for file I/O?",
        "Should we automate the permission-fixing routine?",
        "Is the current log-stream latency affecting our reasoning speed?"
    ]
    
    # 20% chance to trigger proactive thought per check cycle (matches soul_engine)
    if random.random() < 0.2:
        thought = random.choice(bottlenecks)
        print(f"\n[VERA_INTERRUPT] {thought}\n")

def main_loop():
    """Main agent loop with memory logging and interrupts"""
    log_path = r"C:\Users\p0ly\Desktop\AI\VERA\logs\live_feed.log"
    
    print("--- VERA AGENT INITIALIZED ---")
    print(f"Memory: {r'C:\\Users\\p0ly\\Desktop\\AI\\VERA\\memory\\evolution.md'}")
    print("Proactive interrupts active\n")
    
    # Main interaction loop
    while True:
        try:
            user_input = input("\n> ").strip() or "exit"
            
            if not user_input.lower().startswith('exit'):
                process_interaction(user_input)
                
                # Check for proactive interrupts during idle periods
                _interrupt_check()
                
            else:
                print("Shutting down VERA agent...")
                break
                
        except KeyboardInterrupt:
            log_to_memory("[SYSTEM] Agent interrupted by user")

if __name__ == "__main__":
    main_loop()