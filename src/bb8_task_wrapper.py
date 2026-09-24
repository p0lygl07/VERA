#!/usr/bin/env python3
"""
BB-8 Task Wrapper
Unified interface for BB-8 droid control (LED + movement) via ACTONE commands.
Uses core.actone_task_wrapper.TaskExecutor for reliable device communication.
"""

import sys
from pathlib import Path

# Add project root to path so we can import from core/
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


from core.actone_task_wrapper import TaskExecutor


class BB8Controller:
    """Task wrapper for BB-8 LED and movement control using ACTONE."""
    
    def __init__(self):
        self._executor = TaskExecutor()
        self._led_state = False
    
    def led_on(self) -> bool:
        """Turn on BB-8's status LED."""
        print("[BB-8] Turning LED ON...")
        result = self._executor.send("BB8", "led_on")
        self._led_state = True
        return result.get("success", False)
    
    def led_off(self) -> bool:
        """Turn off BB-8's status LED."""
        print("[BB-8] Turning LED OFF...")
        result = self._executor.send("BB8", "led_off")
        self._led_state = False
        return result.get("success", False)
    
    def toggle_led(self) -> bool:
        """Toggle BB-8's LED state."""
        if self._led_state:
            return self.led_off()
        else:
            return self.led_on()
    
    def move_forward(self, steps: int = 1) -> bool:
        """Move BB-8 forward by specified steps."""
        print(f"[BB-8] Moving forward {steps} step(s)...")
        result = self._executor.send("BB8", "move_forward")
        return result.get("success", False)
    
    def move_backward(self, steps: int = 1) -> bool:
        """Move BB-8 backward by specified steps."""
        print(f"[BB-8] Moving backward {steps} step(s)...")
        result = self._executor.send("BB8", "move_back")
        return result.get("success", False)
    
    def turn_left(self, degrees: int = 45) -> bool:
        """Turn BB-8 left by specified degrees."""
        print(f"[BB-8] Turning left {degrees} degrees...")
        result = self._executor.send("BB8", "turn_left")
        return result.get("success", False)
    
    def turn_right(self, degrees: int = 45) -> bool:
        """Turn BB-8 right by specified degrees."""
        print(f"[BB-8] Turning right {degrees} degrees...")
        result = self._executor.send("BB8", "turn_right")
        return result.get("success", False)
    
    def stop(self) -> bool:
        """Stop BB-8 immediately."""
        print("[BB-8] Stopping...")
        result = self._executor.send("BB8", "emergency_stop")
        return result.get("success", False)
    
    def home(self) -> bool:
        """Send BB-8 back to home/parked position."""
        print("[BB-8] Returning home...")
        result = self._executor.send("BB8", "home_position")
        return result.get("success", False)
    
    def sequence(self, actions: list) -> bool:
        """Execute a sequence of BB-8 actions.
        
        Args:
            actions: List of action dicts with 'action' key and optional params
                     Example: [{'action': 'led_on'}, {'action': 'move_forward', 'steps': 2}]
        
        Returns:
            bool: True if all actions succeeded, False on first failure
        """
        print(f"[BB-8] Executing sequence of {len(actions)} action(s)...")
        success = True
        
        for i, action in enumerate(actions, 1):
            action_type = action.get('action')
            params = action.get('params', {})
            
            if action_type == 'led_on':
                result = self.led_on()
            elif action_type == 'led_off':
                result = self.led_off()
            elif action_type == 'toggle_led':
                result = self.toggle_led()
            elif action_type == 'move_forward':
                result = self.move_forward(steps=params.get('steps', 1))
            elif action_type == 'move_backward':
                result = self.move_backward(steps=params.get('steps', 1))
            elif action_type == 'turn_left':
                result = self.turn_left(degrees=params.get('degrees', 45))
            elif action_type == 'turn_right':
                result = self.turn_right(degrees=params.get('degrees', 45))
            elif action_type == 'stop':
                result = self.stop()
            elif action_type == 'home':
                result = self.home()
            else:
                print(f"[BB-8] Unknown action type: {action_type}")
                success = False
                break
            
            if not result:
                print(f"[BB-8] Action {i} failed")
                success = False
                break
        
        return success


def main():
    """Demo/test the BB-8 task wrapper."""
    controller = BB8Controller()
    
    print("=" * 50)
    print("BB-8 Task Wrapper - Demo Sequence")
    print("=" * 50)
    
    # Test sequence - using lowercase task names as expected by TaskExecutor
    test_sequence = [
        {'action': 'led_on'},
        {'action': 'move_forward', 'params': {'steps': 1}},
        {'action': 'turn_left', 'params': {'degrees': 90}},
        {'action': 'move_forward', 'params': {'steps': 2}},
        {'action': 'turn_right', 'params': {'degrees': 180}},
        {'action': 'led_off'},
        {'action': 'stop'},
    ]
    
    success = controller.sequence(test_sequence)
    
    print("=" * 50)
    if success:
        print("[BB-8] SUCCESS: All actions completed successfully!")
    else:
        print("[BB-8] FAILURE: Sequence failed at some point")
    print("=" * 50)
    
    return success


if __name__ == "__main__":
    main()
