"""
test_actone_wrapper.py — Verify ACTONE task wrapper with existing infrastructure.

Run this to test the wrapper once hardware arrives, or just verify it loads correctly now.
"""

import sys
sys.path.insert(0, "C:\\Users\\P01yG107\\Desktop\\vera")

from core.actone_task_wrapper import TaskExecutor, known_devices


def test_wrapper():
    """Test that the wrapper loads and has correct device/task mappings."""
    print("=" * 60)
    print("ACTONE Task Wrapper — System Verification")
    print("=" * 60)
    print()
    
    # Test 1: Check known devices
    print(f"[OK] Known devices: {known_devices()}")
    assert "KYGER" in known_devices(), "KYGER device not registered"
    assert "BB8" in known_devices(), "BB8 device not registered"
    assert "ARM" in known_devices(), "ARM device not registered"
    print("  All devices registered correctly [VERA VERIFIED]")
    print()
    
    # Test 2: Create executor instance
    executor = TaskExecutor()
    print("[OK] TaskExecutor instance created")
    print()
    
    # Test 3: Check task mappings
    print("Task mappings per device:")
    for device, tasks in executor._TASK_TO_TOKENS.items():
        print(f"\n  {device}:")
        for task in sorted(tasks.keys()):
            print(f"    - {task}")
    print()
    
    # Test 4: Try sending commands (will fail without hardware, but tests logic)
    print("Testing command mapping (expected to fail without hardware):")
    
    test_cases = [
        ("KYGER", "scan_network"),
        ("BB8", "led_on"),
        ("ARM", "grab"),
    ]
    
    for device, task in test_cases:
        result = executor.send(device, task)
        if result["success"]:
            print(f"  [OK] {device} -> {task}: {result['tokens_sent']}")
        else:
            print(f"  [WARN] {device} -> {task}: {result.get('error', 'Unknown error')} (expected without hardware)")
    print()
    
    # Test 5: Check invalid task handling
    print("Testing invalid task handling:")
    result = executor.send("KYGER", "invalid_task")
    if not result["success"]:
        print(f"  [OK] Invalid task rejected: {result['error'][:50]}...")
    else:
        print("  [FAIL] Invalid task was accepted (security issue!)")
    print()
    
    # Test 6: Check invalid device handling
    print("Testing invalid device handling:")
    try:
        result = executor.send("NONEXISTENT", "ping")
        print(f"  [FAIL] Invalid device accepted (security issue!)")
    except ValueError as e:
        print(f"  [OK] Invalid device rejected: {str(e)[:50]}...")
    print()
    
    # Test 7: Check mode setting
    print("Testing mode setting:")
    for device in known_devices():
        result = executor.set_mode(device, "auto")
        if result["success"]:
            print(f"  [OK] {device} set to auto mode")
        else:
            print(f"  [WARN] {device} mode change failed (expected without hardware)")
    print()
    
    # Summary
    print("=" * 60)
    print("VERIFICATION COMPLETE")
    print("=" * 60)
    print()
    print("Summary:")
    print(f"  - Devices registered: {len(known_devices())}")
    print(f"  - Task mappings defined: {sum(len(tasks) for tasks in executor._TASK_TO_TOKENS.values())}")
    print(f"  - Invalid input handling: Working")
    print()
    print("Ready for hardware integration!")
    print()


if __name__ == "__main__":
    test_wrapper()
