"""
actone_task_wrapper.py — High-level task-to-ACTONE mapping layer.

This module provides a simple interface for common hardware tasks,
mapping human-readable commands to ACTONE token sequences.

Usage:
    from core.actone_task_wrapper import TaskExecutor
    executor = TaskExecutor()
    
    # Send "scan network" command to KYGER
    result = executor.send("KYGER", "scan_network")
    
    # Move robot arm to grab object
    result = executor.move_arm("ARM", "GRAB")
"""

import time
from vera_actone_devices import get_outbound_channel, known_devices
from vera_actone_secure import SecureChannel


class TaskExecutor:
    """
    High-level interface for hardware tasks.
    
    Maps semantic task names to ACTONE token sequences.
    Each device has its own command mappings defined in _TASK_TO_TOKENS.
    """
    
    # Semantic task -> ACTONE token mapping per device type
    _TASK_TO_TOKENS = {
        "KYGER": {
            "scan_network": ["MODE_AUTO", "RECORD_START"],
            "stop_scan": ["RECORD_STOP", "MODE_MANUAL"],
            "ping_device": ["PING"],
            "acknowledge": ["ACK"],
            "home_position": ["HOME"],
            "emergency_stop": ["STOP"],
            "status_check": ["ACK"],  # Listen for inbound status
        },
        "BB8": {
            "led_on": ["LED_ON"],
            "led_off": ["LED_OFF"],
            "turn_left": ["TURN_LEFT"],
            "turn_right": ["TURN_RIGHT"],
            "move_forward": ["MOVE_FWD"],
            "move_back": ["MOVE_BACK"],
            "grab_object": ["GRAB"],
            "release_object": ["RELEASE"],
            "home_position": ["HOME"],
            "emergency_stop": ["STOP"],
        },
        "ARM": {
            "arm_up": ["ARM_UP"],
            "arm_down": ["ARM_DOWN"],
            "grab": ["GRAB"],
            "release": ["RELEASE"],
            "move_forward": ["MOVE_FWD"],
            "move_back": ["MOVE_BACK"],
            "turn_left": ["TURN_LEFT"],
            "turn_right": ["TURN_RIGHT"],
            "home_position": ["HOME"],
            "emergency_stop": ["STOP"],
        },
    }
    
    def __init__(self):
        self._channels = {}
    
    def _get_channel(self, target: str) -> SecureChannel | None:
        """Get or create outbound channel for a device."""
        target = target.upper()
        if target not in known_devices():
            raise ValueError(f"Unknown device: {target}. Known devices: {known_devices()}")
        
        if target not in self._channels:
            self._channels[target] = get_outbound_channel(target)
        return self._channels[target]
    
    def send(self, target: str, task: str, delay_between_tokens: float = 0.1) -> dict:
        """
        Send a semantic task to a device.
        
        Args:
            target: Device name (KYGER, BB8, ARM)
            task: Semantic task name (e.g., "scan_network", "turn_left")
            delay_between_tokens: Seconds between sending each token
            
        Returns:
            dict with result status and details
        """
        channel = self._get_channel(target)
        tokens = self._TASK_TO_TOKENS.get(target, {}).get(task.upper())
        
        if not tokens:
            return {
                "success": False,
                "error": f"Unknown task '{task}' for device '{target}'. "
                        f"Available tasks: {list(self._TASK_TO_TOKENS[target].keys())}",
            }
        
        result = {"success": True, "target": target, "task": task, "tokens_sent": []}
        
        for token in tokens:
            response = send_actone_command(target, token)
            result["tokens_sent"].append(token)
            if not response.get("verified"):
                result["success"] = False
                result["error"] = f"Token '{token}' failed verification"
                break
        
        return result
    
    def move_arm(self, target: str, action: str) -> dict:
        """Convenience method for arm movement tasks."""
        actions = {
            "grab": ("ARM", "GRAB"),
            "release": ("ARM", "RELEASE"),
            "up": ("ARM", "ARM_UP"),
            "down": ("ARM", "ARM_DOWN"),
            "forward": ("ARM", "MOVE_FWD"),
            "backward": ("ARM", "MOVE_BACK"),
        }
        
        if action in actions:
            return self.send(*actions[action])
        else:
            return self.send(target, action)
    
    def set_mode(self, target: str, mode: str) -> dict:
        """Set device to manual or auto mode."""
        modes = {"manual": ("MODE_MANUAL"), "auto": ("MODE_AUTO")}
        if mode in modes:
            return self.send(target, modes[mode][0])
        else:
            return self.send(target, mode)


def send_actone_command(target: str, command: str) -> dict:
    """
    Send a single ACTONE command to a device.
    
    This is the low-level interface that calls the actual send_actone_command tool.
    """
    # In production, this would call the actual tool
    # For now, we'll simulate by checking if the target and command are valid
    target = target.upper()
    valid_commands = [
        "PING", "ACK", "NACK", "STOP", "HOME", 
        "MOVE_FWD", "MOVE_BACK", "TURN_LEFT", "TURN_RIGHT", 
        "GRAB", "RELEASE", "LED_ON", "LED_OFF", 
        "ARM_UP", "ARM_DOWN", "LAUNCH", "LAND", 
        "RECORD_START", "RECORD_STOP", "MODE_MANUAL", "MODE_AUTO"
    ]
    
    if target not in known_devices() or command not in valid_commands:
        return {
            "success": False,
            "verified": False,
            "error": f"Invalid target '{target}' or command '{command}'",
        }
    
    # Simulate tool call result (in production this would actually call the tool)
    return {
        "success": True,
        "verified": True,
        "target": target,
        "command": command,
        "timestamp": time.time(),
    }


# Example usage and documentation
if __name__ == "__main__":
    print("=" * 60)
    print("ACTONE Task Wrapper — High-Level Hardware Control")
    print("=" * 60)
    print()
    print("Available devices:")
    for device in known_devices():
        print(f"  - {device}")
    print()
    print("Example tasks per device:")
    for device, tasks in _TASK_TO_TOKENS.items():
        print(f"\n{device}:")
        for task in tasks.keys():
            print(f"  • {task}")
    print()
    print("Usage:")
    print("  from core.actone_task_wrapper import TaskExecutor")
    print("  executor = TaskExecutor()")
    print("  result = executor.send('KYGER', 'scan_network')")
    print("  result = executor.move_arm('ARM', 'grab')")
    print("  result = executor.set_mode('BB8', 'auto')")
