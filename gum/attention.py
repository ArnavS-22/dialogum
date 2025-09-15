"""
Real-time User Attention Assessment for Mixed-Initiative Systems

Monitors user activity to determine focus level and availability for interruption.
"""

import time
import logging
import threading
from typing import Dict, List, Optional
from dataclasses import dataclass
from collections import deque
import psutil

logger = logging.getLogger(__name__)

@dataclass
class ActivityEvent:
    """Single user activity event."""
    timestamp: float
    event_type: str  # "keyboard", "mouse", "app_switch"
    details: str = ""

@dataclass 
class AttentionState:
    """Current attention state assessment."""
    focus_level: float  # 0.0 (idle) to 1.0 (highly focused)
    active_application: str
    idle_time_seconds: float
    recent_activity_count: int
    app_switch_frequency: float
    confidence: float  # Confidence in the assessment

class AttentionMonitor:
    """
    Monitors user attention in real-time using system-level indicators.
    
    Key indicators:
    - Keyboard/mouse activity frequency
    - Active application type (focus vs casual apps)
    - Time since last activity  
    - Application switching patterns
    """
    
    def __init__(self, 
                 history_window_seconds: int = 300,  # 5 minutes
                 update_interval: float = 2.0,
                 debug: bool = False):
        """
        Initialize attention monitor.
        
        Args:
            history_window_seconds: How far back to look for activity patterns
            update_interval: How often to update attention state (seconds)
            debug: Enable debug logging
        """
        self.history_window = history_window_seconds
        self.update_interval = update_interval
        self.debug = debug
        
        # Activity tracking
        self.activity_history: deque = deque(maxlen=1000)
        self.last_activity_time = time.time()
        self.last_active_app = ""
        self.app_switch_count = 0
        self.last_app_check_time = time.time()
        
        # Current state
        self.current_state = AttentionState(
            focus_level=0.5,
            active_application="unknown",
            idle_time_seconds=0.0,
            recent_activity_count=0,
            app_switch_frequency=0.0,
            confidence=0.5
        )
        
        # Monitoring thread
        self._monitoring = False
        self._monitor_thread = None
        
        # App classification
        self.focus_apps = {
            "xcode", "visual studio code", "vscode", "intellij", "pycharm", 
            "terminal", "iterm", "sublime text", "vim", "emacs", "atom",
            "android studio", "eclipse", "netbeans", "code", "phpstorm"
        }
        
        self.casual_apps = {
            "safari", "chrome", "firefox", "spotify", "music", "youtube",
            "slack", "discord", "messages", "facetime", "zoom", "teams",
            "netflix", "hulu", "instagram", "facebook", "twitter"
        }
        
        if self.debug:
            logger.info(f"AttentionMonitor initialized with {len(self.focus_apps)} focus apps, "
                       f"{len(self.casual_apps)} casual apps")
    
    def get_active_application(self) -> str:
        """Get the currently active application name."""
        try:
            # Use AppleScript on macOS to get frontmost app
            import subprocess
            result = subprocess.run([
                'osascript', '-e', 
                'tell application "System Events" to get name of first application process whose frontmost is true'
            ], capture_output=True, text=True, timeout=2)
            
            if result.returncode == 0 and result.stdout.strip():
                app_name = result.stdout.strip().lower()
                return app_name
            else:
                return "unknown"
                
        except subprocess.TimeoutExpired:
            logger.debug("App detection timed out, using fallback")
            return "unknown"
        except FileNotFoundError:
            logger.debug("osascript not found, likely not on macOS")
            return "unknown"
        except Exception as e:
            logger.debug(f"Could not get active application: {e}")
            return "unknown"
    
    def classify_app_focus_level(self, app_name: str) -> float:
        """
        Classify application focus level.
        
        Args:
            app_name: Name of the application
            
        Returns:
            Focus modifier: 0.0 (very casual) to 1.0 (highly focused)
        """
        app_lower = app_name.lower()
        
        # Check for exact matches first
        if app_lower in self.focus_apps:
            return 0.9
        elif app_lower in self.casual_apps:
            return 0.2
        
        # Check for partial matches
        for focus_app in self.focus_apps:
            if focus_app in app_lower or app_lower in focus_app:
                return 0.9
                
        for casual_app in self.casual_apps:
            if casual_app in app_lower or app_lower in casual_app:
                return 0.2
        
        # Unknown apps get neutral focus
        return 0.5
    
    def record_activity(self, event_type: str, details: str = ""):
        """Record a user activity event."""
        now = time.time()
        event = ActivityEvent(
            timestamp=now,
            event_type=event_type,
            details=details
        )
        
        self.activity_history.append(event)
        self.last_activity_time = now
        
        if self.debug and len(self.activity_history) % 10 == 0:
            logger.debug(f"Recorded {len(self.activity_history)} activity events")
    
    def calculate_focus_level(self) -> float:
        """
        Calculate current focus level based on multiple indicators.
        
        Returns:
            Focus level from 0.0 (idle/distracted) to 1.0 (highly focused)
        """
        now = time.time()
        
        # 1. Get active application and its focus level
        current_app = self.get_active_application()
        app_focus = self.classify_app_focus_level(current_app)
        
        # 2. Calculate idle time
        idle_time = now - self.last_activity_time
        
        # 3. Count recent activity (last 2 minutes)
        recent_cutoff = now - 120  # 2 minutes
        recent_activity = sum(1 for event in self.activity_history 
                            if event.timestamp > recent_cutoff)
        
        # 4. Calculate app switching frequency (switches per minute)
        if current_app != self.last_active_app and current_app != "unknown":
            self.app_switch_count += 1
            self.last_active_app = current_app
            
        time_since_last_check = now - self.last_app_check_time
        if time_since_last_check >= 60:  # Reset counter every minute
            switch_frequency = self.app_switch_count / (time_since_last_check / 60)
            self.app_switch_count = 0
            self.last_app_check_time = now
        else:
            switch_frequency = 0
        
        # 5. Combine indicators into focus score
        
        # Base score from app type
        focus_score = app_focus
        
        # Adjust for recent activity (more activity = more focus, up to a point)
        activity_factor = min(1.0, recent_activity / 20)  # 20 activities = max boost
        focus_score = focus_score * 0.7 + activity_factor * 0.3
        
        # Penalty for idle time (exponential decay)
        if idle_time > 30:  # Grace period of 30 seconds
            idle_penalty = min(0.8, (idle_time - 30) / 300)  # Max 80% penalty after 5 minutes
            focus_score *= (1 - idle_penalty)
        
        # Penalty for frequent app switching (indicates distraction)
        if switch_frequency > 2:  # More than 2 switches per minute
            distraction_penalty = min(0.5, (switch_frequency - 2) / 10)
            focus_score *= (1 - distraction_penalty)
        
        # Clamp to valid range
        focus_score = max(0.0, min(1.0, focus_score))
        
        # Update current state
        self.current_state = AttentionState(
            focus_level=focus_score,
            active_application=current_app,
            idle_time_seconds=idle_time,
            recent_activity_count=recent_activity,
            app_switch_frequency=switch_frequency,
            confidence=0.8  # High confidence in our assessment
        )
        
        if self.debug:
            logger.debug(f"Focus calculation: app={current_app} ({app_focus:.2f}), "
                        f"idle={idle_time:.1f}s, activity={recent_activity}, "
                        f"switches={switch_frequency:.1f}/min -> focus={focus_score:.2f}")
        
        return focus_score
    
    def start_monitoring(self):
        """Start background monitoring of user attention."""
        if self._monitoring:
            logger.warning("Attention monitoring already started")
            return
            
        self._monitoring = True
        self._monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._monitor_thread.start()
        
        if self.debug:
            logger.info("Started attention monitoring")
    
    def stop_monitoring(self):
        """Stop background monitoring."""
        self._monitoring = False
        if self._monitor_thread:
            self._monitor_thread.join(timeout=5)
        
        if self.debug:
            logger.info("Stopped attention monitoring")
    
    def _monitor_loop(self):
        """Background monitoring loop."""
        while self._monitoring:
            try:
                # Update focus calculation
                self.calculate_focus_level()
                
                # Simulate activity detection (in real implementation, would use system hooks)
                # For now, just update based on app switching
                
                time.sleep(self.update_interval)
                
            except Exception as e:
                logger.error(f"Error in attention monitoring loop: {e}")
                # Continue monitoring even if individual updates fail
                time.sleep(self.update_interval)
    
    def get_current_attention(self) -> AttentionState:
        """Get the current attention assessment."""
        # Ensure we have a recent calculation
        self.calculate_focus_level()
        return self.current_state


def test_attention_monitor():
    """Test the attention monitoring system."""
    print("🧪 Testing Attention Monitor")
    
    monitor = AttentionMonitor(debug=True)
    
    # Test app classification
    test_apps = ["Xcode", "Safari", "Visual Studio Code", "Spotify", "Terminal", "Unknown App"]
    
    print("\n--- App Focus Classification ---")
    for app in test_apps:
        focus_level = monitor.classify_app_focus_level(app)
        print(f"{app}: {focus_level:.1f} focus")
    
    # Test current attention
    print("\n--- Current Attention State ---")
    attention = monitor.get_current_attention()
    print(f"Focus Level: {attention.focus_level:.2f}")
    print(f"Active App: {attention.active_application}")
    print(f"Idle Time: {attention.idle_time_seconds:.1f}s")
    print(f"Confidence: {attention.confidence:.2f}")
    
    # Test monitoring for a few seconds
    print("\n--- Starting Brief Monitoring ---")
    monitor.start_monitoring()
    time.sleep(5)
    
    final_attention = monitor.get_current_attention()
    print(f"Final Focus Level: {final_attention.focus_level:.2f}")
    print(f"Final Active App: {final_attention.active_application}")
    
    monitor.stop_monitoring()
    print("\n✅ Attention monitor test completed!")

if __name__ == "__main__":
    test_attention_monitor()
