

from datetime import datetime
from urllib.parse import urlparse
import subprocess, platform, re, time, random, sys


TIMEOUT_MS = 800
LATENCY_THRESHOLD_MS = 250.0
OFFLINE_MSG = "LAG DETECTED ! "
DEFAULT_INTERVAL = 0.25
MIN_INTERVAL_REMOTE = 0.15
MIN_INTERVAL_LOCAL = 0.02
PACKET_SIZE = None

RESET = "\x1b[0m"
BOLD = "\x1b[1m"

def fg_rgb(r,g,b): return f"\x1b[38;2;{r};{g};{b}m"

def rand_dark_color():
    
    dark_colors = [
        (50, 0, 50),    
        (30, 30, 30),   
        (20, 20, 50),   
        (40, 0, 40),   
        (60, 0, 30),    
        (10, 10, 10),   
        (35, 0, 60),   
    ]
    return random.choice(dark_colors)

def color_text(txt, online=True):
    """If online=True, pick random dark color. If online=False, red."""
    if online:
        r,g,b = rand_dark_color()
    else:
        r,g,b = 255,0,0
    return f"{fg_rgb(r,g,b)}{txt}{RESET}"

HEADER = r"""
              ____ ___ _   _  ____ 
__  __      |  _ \_ _| \ | |/ ___|
\ \/ /____  | |_) | ||  \| | |  _ 
 >  <_____| |  __/| || |\  | |_| |
/_/\_\      |_|  |___|_| \_|\____| 
"""

TIME_RE = re.compile(r"time[=<]?\s*([\d\.]+)\s*ms", re.IGNORECASE)
SYSTEM = platform.system().lower()

def is_localhost(target):
    t = target.strip().lower()
    return t in ("localhost", "127.0.0.1", "::1")

def extract_host(maybe_url):
    if "://" in maybe_url:
        try:
            return urlparse(maybe_url).hostname or maybe_url
        except Exception:
            return maybe_url
    return maybe_url

def build_ping_cmd_single(target, payload_size=None):
    if SYSTEM.startswith("win"):
        cmd = ["ping", "-n", "1", target]
        if payload_size is not None:
            cmd += ["-l", str(int(payload_size))]
        return cmd
    else:
        cmd = ["ping", "-c", "1", target]
        if payload_size is not None:
            cmd += ["-s", str(int(payload_size))]
        return cmd

def run_ping_once(target, timeout_ms=TIMEOUT_MS, payload_size=None):
    cmd = build_ping_cmd_single(target, payload_size=payload_size)
    try:
        completed = subprocess.run(cmd, capture_output=True, text=True, timeout=(timeout_ms/1000.0 + 0.6))
        out = (completed.stdout or "") + (completed.stderr or "")
        m = TIME_RE.search(out)
        if m:
            try:
                return True, float(m.group(1)), out
            except ValueError:
                return True, None, out
        if completed.returncode == 0:
            return True, None, out
        return False, None, out
    except subprocess.TimeoutExpired:
        return False, None, "timeout"
    except FileNotFoundError:
        return False, None, "ping command not found"
    except Exception as e:
        return False, None, f"error: {e}"

def print_status(target, success, rtt, latency_threshold, offline_msg):
    timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
    label = f"[{timestamp}]"
    name = color_text(target)  
    if not success:
        print(f"{label} {name} - {color_text('OFFLINE', online=False)}")
        return
    if rtt is None:
        print(f"{label} {name} - {color_text('ONLINE', online=True)}")
        return
    if rtt <= latency_threshold:
        print(f"{label} {name} - {color_text('ONLINE', online=True)} ({rtt:.1f} ms)")
    else:
        print(f"{label} {name} - {color_text(offline_msg, online=False)}")

def continuous_ping(target, duration_s, timeout_ms, latency_threshold, offline_msg, interval_s=None, payload_size=None):
    end_time = time.time() + max(0.0, float(duration_s))
    while time.time() < end_time:
        success, rtt, raw = run_ping_once(target, timeout_ms=timeout_ms, payload_size=payload_size)
        print_status(target, success, rtt, latency_threshold, offline_msg)
        try:
            time.sleep(DEFAULT_INTERVAL)
        except KeyboardInterrupt:
            raise

def settings_menu():
    global TIMEOUT_MS, LATENCY_THRESHOLD_MS
    print(color_text("\n--- Settings ---"))
    try:
        new_t = input(color_text(f"Timeout ms per ping (current {TIMEOUT_MS}) > ")).strip()
        if new_t:
            TIMEOUT_MS = int(new_t)
        new_thresh = input(color_text(f"Latency threshold ms (current {LATENCY_THRESHOLD_MS}) > ")).strip()
        if new_thresh:
            LATENCY_THRESHOLD_MS = float(new_thresh)
        print(color_text("Settings updated."))
    except Exception as e:
        print(color_text(f"Invalid input: {e}"))

def change_offline_message():
    global OFFLINE_MSG
    print(color_text(f"\nCurrent offline message: '{OFFLINE_MSG}'"))
    new_msg = input(color_text("Enter new offline message (leave blank to keep) > ")).strip()
    if new_msg:
        OFFLINE_MSG = new_msg
        print(color_text(f"Offline message updated to: '{OFFLINE_MSG}'"))
    else:
        print(color_text("Offline message unchanged."))

def set_packet_size():
    global PACKET_SIZE
    try:
        val = input(color_text(f"Enter packet size in bytes (blank for default) > ")).strip()
        if val:
            PACKET_SIZE = int(val)
            print(color_text(f"Packet size set to {PACKET_SIZE} bytes."))
        else:
            PACKET_SIZE = None
            print(color_text("Packet size reset to default."))
    except Exception:
        print(color_text("Invalid input, packet size unchanged."))

def main_menu():
    print(color_text(HEADER))
    while True:
        print()
        print(color_text("1) URL ping"))
        print(color_text("2) IP ping"))
        print(color_text("3) Settings"))
        print(color_text("4) Set ping packet size"))
        print(color_text("5) Change offline message"))
        print(color_text("6) Exit"))
        choice = input(color_text("\nSelect an option > ")).strip()
        if choice == "1":
            raw = input(color_text("Enter URL or hostname > ")).strip()
            if not raw:
                print(color_text("No target entered."))
                continue
            target = extract_host(raw)
            try:
                dur = float(input(color_text("Duration in seconds > ")).strip())
                if dur <= 0:
                    print(color_text("Duration must be > 0."))
                    continue
            except Exception:
                print(color_text("Invalid duration; using 10s."))
                dur = 10.0
            print(color_text(f"\nPinging {target} for {dur} seconds (Ctrl+C to stop early)\n"))
            try:
                continuous_ping(target, dur, TIMEOUT_MS, LATENCY_THRESHOLD_MS, OFFLINE_MSG, payload_size=PACKET_SIZE)
            except KeyboardInterrupt:
                print(color_text("\nStopped early — returning to menu."))
        elif choice == "2":
            ip = input(color_text("Enter IP address > ")).strip()
            if not ip:
                print(color_text("No IP entered."))
                continue
            try:
                dur = float(input(color_text("Duration in seconds > ")).strip())
                if dur <= 0:
                    print(color_text("Duration must be > 0."))
                    continue
            except Exception:
                print(color_text("Invalid duration; using 10s."))
                dur = 10.0
            print(color_text(f"\nPinging {ip} for {dur} seconds (Ctrl+C to stop early)\n"))
            try:
                continuous_ping(ip, dur, TIMEOUT_MS, LATENCY_THRESHOLD_MS, OFFLINE_MSG, payload_size=PACKET_SIZE)
            except KeyboardInterrupt:
                print(color_text("\nStopped early — returning to menu."))
        elif choice == "3":
            settings_menu()
        elif choice == "4":
            set_packet_size()
        elif choice == "5":
            change_offline_message()
        elif choice == "6" or choice.lower() in ("q","quit","exit"):
            print(color_text("Goodbye."))
            break
        else:
            print(color_text("Invalid option — try again."))

if __name__ == "__main__":
    try:
        main_menu()
    except KeyboardInterrupt:
        print("\nExiting. Bye.")
        sys.exit(0)
