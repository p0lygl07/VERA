# ACTONE Hardware Control Tasks

## Overview

This system provides high-level task interfaces for controlling your hardware devices via ACTONE commands once the K2 printer arrives mid-September.

## Available Devices

| Device | Purpose | Key Capabilities |
|--------|---------|------------------|
| **KYGER** | Wearable suit with Jetson Orin Nano + OAK-D cam | Network scanning, recon, status reporting |
| **BB8 (GL-07)** | Tabletop droid companion | Movement, LED indicators, object manipulation |
| **ARM** | 4DOF robot arm (ESP32-C3) | Grab/release, positioning, tool mounting |

## Task Mapping

### KYGER Tasks

```python
executor.send("KYGER", "scan_network")    # MODE_AUTO + RECORD_START
executor.send("KYGER", "stop_scan")       # RECORD_STOP + MODE_MANUAL
executor.send("KYGER", "ping_device")     # PING
executor.send("KYGER", "emergency_stop")  # STOP
```

**Use Cases:**
- Remote network reconnaissance from suit
- Start/stop wireless capture sessions
- Emergency stop for safety
- Device status checks

### BB8 Tasks

```python
executor.move("BB8", "turn_left")
executor.move("BB8", "grab_object")
executor.set_mode("BB8", "auto")
```

**Use Cases:**
- Navigate tabletop environment
- Present objects to user
- LED status indicators (on/off)
- Autonomous mode for demonstrations

### ARM Tasks

```python
executor.move_arm("ARM", "grab")
executor.move_arm("ARM", "arm_up")
executor.set_mode("ARM", "manual")
```

**Use Cases:**
- Pick/place objects
- Tool mounting/removal
- Positioning for tasks
- Manual override when needed

## Usage Examples

### Basic Control

```python
from core.actone_task_wrapper import TaskExecutor

executor = TaskExecutor()

# Start KYGER network scan
result = executor.send("KYGER", "scan_network")
print(result)  # {'success': True, 'tokens_sent': ['MODE_AUTO', 'RECORD_START']}

# Move robot arm to grab object
result = executor.move_arm("ARM", "grab")
print(result)

# Set BB8 to autonomous mode
result = executor.set_mode("BB8", "auto")
```

### Sequential Operations

```python
# Complex task: scan then stop
executor.send("KYGER", "scan_network")
time.sleep(5)  # Let it run for 5 seconds
executor.send("KYGER", "stop_scan")

# Arm sequence: grab, lift, move, release
executor.move_arm("ARM", "grab")
executor.move_arm("ARM", "arm_up")
executor.move_arm("ARM", "move_forward")
executor.move_arm("ARM", "release")
```

### Safety Wrapper

```python
def safe_operation(device, task):
    """Execute with automatic emergency stop capability."""
    try:
        result = executor.send(device, task)
        if result["success"]:
            return result
    except Exception as e:
        print(f"Operation failed: {e}")
    finally:
        # Always allow emergency stop if needed
        executor.send(device, "emergency_stop")
    return None
```

## Integration with Other Systems

### Screen Copilot

The wrapper can be integrated into your Screen Copilot HUD to suggest hardware actions based on active windows:

```python
# Pseudo-code for Screen Copilot integration
def suggest_action(active_window):
    if "network_scan" in active_window.title:
        return executor.send("KYGER", "scan_network")
    elif "object_pickup" in active_window.title:
        return executor.move_arm("ARM", "grab")
```

### Dashboard Control

Connect to your dashboard (port 8765) for remote hardware control:

```python
# Dashboard API endpoint example
@app.post("/api/hardware/control")
async def hardware_control(request: HardwareControlRequest):
    executor = TaskExecutor()
    result = executor.send(request.device, request.task)
    return JSONResponse(result)
```

## Testing (Before Hardware Arrives)

Run the test script to verify the wrapper works with your existing ACTONE infrastructure:

```bash
python core\actone_task_wrapper.py
```

This will print available devices, tasks, and usage examples.

## Next Steps (Mid-September)

1. **K2 Printer arrives** — Start printing Kyger components
2. **Flash firmware** — Program each device with its ACTONE shared key
3. **Test connectivity** — Verify all devices respond to commands
4. **Integrate with agents** — Connect to your multi-agent system
5. **Build use cases** — Develop specific workflows for each device

## Security Notes

- Device keys are stored in `vera_actone_devices.py`
- Keep a backup copy outside the codebase (password manager)
- Never commit real keys to public repos
- Each device has separate inbound/outbound channels
- Lockout protection prevents brute force attacks

## Truth Layer

This documentation operates at **T3 (Contextual Truth)** — valid within the VERA system architecture and ACTONE protocol specification.
