import os
import json
import time
import shutil
import random
import threading
import tkinter as tk
from pynput import keyboard
from mss import mss
from PIL import Image, ImageTk

try:
    import ctypes
    ctypes.windll.shcore.SetProcessDpiAwareness(1)
except Exception:
    pass

SETTINGS_FILE = "settings.json"
CAPTURES_DIR = "captures"
VISUAL_ZOOM = 4 

# Background thread management
bg_scanner_thread = None
scanner_stop_event = threading.Event()

def clear_screen():
    os.system('cls' if os.name == 'nt' else 'clear')

class AreaSelector(tk.Toplevel):
    def __init__(self):
        super().__init__()
        self.attributes('-alpha', 0.3)
        self.attributes('-fullscreen', True)
        self.config(cursor="cross")
        self.canvas = tk.Canvas(self, bg="black")
        self.canvas.pack(fill="both", expand=True)
        self.rect = None
        self.start_x = None
        self.start_y = None
        self.coords = None
        
        self.canvas.bind("<ButtonPress-1>", self.on_press)
        self.canvas.bind("<B1-Motion>", self.on_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_release)
        self.bind("<Escape>", lambda e: self.destroy())

    def on_press(self, event):
        self.start_x, self.start_y = event.x, event.y
        self.rect = self.canvas.create_rectangle(self.start_x, self.start_y, self.start_x, self.start_y, outline='red', width=3)

    def on_drag(self, event):
        self.canvas.coords(self.rect, self.start_x, self.start_y, event.x, event.y)

    def on_release(self, event):
        x1 = min(self.start_x, event.x)
        y1 = min(self.start_y, event.y)
        x2 = max(self.start_x, event.x)
        y2 = max(self.start_y, event.y)
        self.coords = {"left": x1, "top": y1, "width": x2 - x1, "height": y2 - y1}
        self.destroy()

def capture_learning_round(zone):
    print("\n[Learning Round] Press keys (a-z, 0-9) to capture. Press Escape to finish.")
    
    if not os.path.exists(CAPTURES_DIR):
        os.makedirs(CAPTURES_DIR)
        
    captures = []
    captured_chars = set()
    sct = mss()
    
    def on_press(key):
        try:
            if hasattr(key, 'char') and key.char:
                char = key.char.lower()
                if char.isalnum() and char not in captured_chars:
                    captured_chars.add(char)
                    img_data = sct.grab(zone)
                    img = Image.frombytes("RGB", img_data.size, img_data.bgra, "raw", "BGRX")
                    img_path = os.path.join(CAPTURES_DIR, f"{char}.png")
                    img.save(img_path)
                    
                    captures.append((char, img))
                    print(f"Captured screen for key: '{char}'")
        except Exception:
            pass
            
        if key == keyboard.Key.esc:
            return False

    with keyboard.Listener(on_press=on_press) as listener:
        listener.join()
        
    return captures

class DotPlacer(tk.Toplevel):
    def __init__(self, captures, existing_data=None):
        super().__init__()
        self.captures = captures
        self.index = 0
        self.results = {i: existing_data.get(captures[i][0], []) for i in range(len(captures))} if existing_data else {}
        self.current_dots = [] 
        
        self.title("Dot Configurator (Zoomed)")
        
        self.tk_img = None 
        self.orig_w = 0
        self.orig_h = 0
        self.scaled_w = 0
        self.scaled_h = 0
        
        char, img = self.captures[self.index]
        self.orig_w, self.orig_h = img.size
        self.scaled_w, self.scaled_h = self.orig_w * VISUAL_ZOOM, self.orig_h * VISUAL_ZOOM
        
        btn_frame_w = 200
        min_win_h = 140 
        win_w = self.scaled_w + btn_frame_w
        win_h = max(self.scaled_h, min_win_h)
        self.geometry(f"{win_w}x{win_h}")
        self.resizable(False, False)
        
        self.left_frame = tk.Frame(self)
        self.left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        self.canvas = tk.Canvas(self.left_frame, bg="black", width=self.scaled_w, height=self.scaled_h)
        self.canvas.pack(fill="both", expand=True)
        self.canvas.bind("<Button-1>", self.add_dot)
        
        self.right_frame = tk.Frame(self, width=btn_frame_w)
        self.right_frame.pack(side=tk.RIGHT, fill=tk.Y)
        self.right_frame.pack_propagate(False)
        
        self.lbl_char = tk.Label(self.right_frame, text="Key: ", font=("Arial", 18, "bold"))
        self.lbl_char.pack(pady=5)
        
        self.btn_frame = tk.Frame(self.right_frame)
        self.btn_frame.pack(fill=tk.BOTH, expand=True, padx=5)
        
        tk.Button(self.btn_frame, text="Clear Dots", command=self.clear_dots).grid(row=0, column=0, sticky="ew", padx=2, pady=2)
        tk.Button(self.btn_frame, text="Finish Setup", command=self.finish).grid(row=0, column=1, sticky="ew", padx=2, pady=2)
        tk.Button(self.btn_frame, text="Last Image", command=self.prev_img).grid(row=1, column=0, sticky="ew", padx=2, pady=2)
        tk.Button(self.btn_frame, text="Next Image", command=self.next_img).grid(row=1, column=1, sticky="ew", padx=2, pady=2)
        
        self.btn_frame.columnconfigure(0, weight=1)
        self.btn_frame.columnconfigure(1, weight=1)
        
        self.show_image()
        
    def show_image(self):
        if self.index >= len(self.captures):
            self.finish()
            return
            
        char, img = self.captures[self.index]
        self.orig_w, self.orig_h = img.size
        self.scaled_w, self.scaled_h = self.orig_w * VISUAL_ZOOM, self.orig_h * VISUAL_ZOOM
        
        btn_frame_w = 200
        min_win_h = 140
        win_w = self.scaled_w + btn_frame_w
        win_h = max(self.scaled_h, min_win_h)
        self.geometry(f"{win_w}x{win_h}")
        self.canvas.config(width=self.scaled_w, height=self.scaled_h)

        self.canvas.delete("all")
        self.current_dots = self.results.get(self.index, []).copy()
        
        self.lbl_char.config(text=f"Key: {char.upper()}")
        
        visual_img = img.resize((self.scaled_w, self.scaled_h), Image.NEAREST)
        self.tk_img = ImageTk.PhotoImage(visual_img)
        self.canvas.create_image(0, 0, anchor=tk.NW, image=self.tk_img)
        
        dot_radius = max(1, VISUAL_ZOOM // 2)
        for (x_orig, y_orig) in self.current_dots:
            x_vis = x_orig * VISUAL_ZOOM
            y_vis = y_orig * VISUAL_ZOOM
            self.canvas.create_oval(x_vis-dot_radius, y_vis-dot_radius, x_vis+dot_radius, y_vis+dot_radius, fill="red", outline="white", width=1)
            
    def add_dot(self, event):
        if event.x >= self.scaled_w or event.y >= self.scaled_h:
            return
            
        x_orig = event.x // VISUAL_ZOOM
        y_orig = event.y // VISUAL_ZOOM
            
        self.current_dots.append((x_orig, y_orig))
        self.results[self.index] = self.current_dots
        
        dot_radius = max(1, VISUAL_ZOOM // 2)
        x_vis = x_orig * VISUAL_ZOOM
        y_vis = y_orig * VISUAL_ZOOM
        self.canvas.create_oval(x_vis-dot_radius, y_vis-dot_radius, x_vis+dot_radius, y_vis+dot_radius, fill="red", outline="white", width=1)
        
    def clear_dots(self):
        self.current_dots = []
        self.results[self.index] = []
        self.show_image()

    def next_img(self):
        self.index += 1
        self.show_image()
        
    def prev_img(self):
        if self.index > 0:
            self.index -= 1
            self.show_image()
            
    def finish(self):
        self.destroy()

def auto_detect_threshold(char_data):
    min_val = 255
    valid_dots_found = False
    
    for char, dots in char_data.items():
        if not dots:
            continue
            
        img_path = os.path.join(CAPTURES_DIR, f"{char}.png")
        if not os.path.exists(img_path):
            continue
            
        try:
            img = Image.open(img_path)
            for (x, y) in dots:
                if x >= img.width or y >= img.height:
                    continue
                
                r, g, b = img.getpixel((x, y))[:3]
                pixel_min = min(r, g, b)
                
                if pixel_min < min_val:
                    min_val = pixel_min
                    
                valid_dots_found = True
        except Exception:
            pass

    if not valid_dots_found:
        return 200 
        
    safe_margin = 30
    return max(0, min_val - safe_margin)

def is_mostly_white(color, threshold):
    return color[0] >= threshold and color[1] >= threshold and color[2] >= threshold

def scanner_worker(settings, stop_event):
    zone = settings["zone"]
    char_data = settings["char_data"]
    threshold = settings.get("threshold", 200)
    scan_delay = settings.get("scan_delay", 150) / 1000.0
    scan_random_delay = settings.get("scan_random_delay", 100) / 1000.0
    toggle_key_str = settings.get("toggle_key", "space").lower()
    trigger_mode = settings.get("trigger_mode", "toggle")

    pressing_enabled = [False]
    key_pressed = [False]
    
    def on_press(key):
        try:
            k_name = getattr(key, 'char', None) or getattr(key, 'name', None)
            if k_name and k_name.lower() == toggle_key_str:
                if trigger_mode == "toggle":
                    if not key_pressed[0]:
                        pressing_enabled[0] = not pressing_enabled[0]
                        key_pressed[0] = True
                elif trigger_mode == "hold":
                    pressing_enabled[0] = True
        except Exception:
            pass

    def on_release(key):
        try:
            k_name = getattr(key, 'char', None) or getattr(key, 'name', None)
            if k_name and k_name.lower() == toggle_key_str:
                if trigger_mode == "toggle":
                    key_pressed[0] = False
                elif trigger_mode == "hold":
                    pressing_enabled[0] = False
        except Exception:
            pass

    listener = keyboard.Listener(on_press=on_press, on_release=on_release)
    listener.start()
    
    sct = mss()
    controller = keyboard.Controller()
    
    while not stop_event.is_set():
        if not pressing_enabled[0]:
            time.sleep(0.1)
            continue
            
        img_data = sct.grab(zone)
        best_char = None
        best_pct = -1.0
        best_dot_count = 0
        
        for char, dots in char_data.items():
            if not dots:
                continue
                
            matched_dots = 0
            valid_dots = 0
            
            for (x, y) in dots:
                if x >= zone['width'] or y >= zone['height']:
                    continue
                valid_dots += 1
                current_pixel = img_data.pixel(x, y)
                if is_mostly_white(current_pixel, threshold):
                    matched_dots += 1
                    
            if valid_dots > 0:
                pct = (matched_dots / valid_dots) * 100
                if pct > best_pct or (pct == best_pct and valid_dots > best_dot_count):
                    best_pct = pct
                    best_char = char
                    best_dot_count = valid_dots
                
        if best_pct == 100.0 and best_char:
            controller.press(best_char)
            controller.release(best_char)
            
        time.sleep(scan_delay + random.uniform(0, scan_random_delay))
        
    listener.stop()

def manage_background_scanner(settings):
    global bg_scanner_thread, scanner_stop_event
    
    scanner_stop_event.set()
    if bg_scanner_thread and bg_scanner_thread.is_alive():
        bg_scanner_thread.join(timeout=1.0)
        
    if not settings or not settings.get("zone") or not settings.get("char_data"):
        return False
        
    current_threshold = settings.get("threshold", "auto")
    if current_threshold == "auto":
        current_threshold = auto_detect_threshold(settings["char_data"])
        settings["threshold"] = current_threshold
        
    scanner_stop_event.clear()
    bg_scanner_thread = threading.Thread(
        target=scanner_worker, 
        args=(settings, scanner_stop_event), 
        daemon=True
    )
    bg_scanner_thread.start()
    return True

def load_settings():
    if os.path.exists(SETTINGS_FILE):
        with open(SETTINGS_FILE, "r") as f:
            data = json.load(f)
            if "threshold" not in data: data["threshold"] = "auto"
            if "scan_delay" not in data: data["scan_delay"] = 150
            if "scan_random_delay" not in data: data["scan_random_delay"] = 100
            if "toggle_key" not in data: data["toggle_key"] = "space"
            if "trigger_mode" not in data: data["trigger_mode"] = "toggle"
            return data
    return None

def delete_settings():
    if os.path.exists(SETTINGS_FILE):
        os.remove(SETTINGS_FILE)
    if os.path.exists(CAPTURES_DIR):
        shutil.rmtree(CAPTURES_DIR)

def create_new_settings():
    selector = AreaSelector()
    selector.wait_window()
    
    if not selector.coords or selector.coords['width'] == 0 or selector.coords['height'] == 0:
        return False

    captures = capture_learning_round(selector.coords)
    if not captures:
        return False
        
    placer = DotPlacer(captures)
    placer.wait_window()
    
    char_data = {}
    for idx, dots in placer.results.items():
        if dots:
            char_data[captures[idx][0]] = dots
            
    settings = {
        "zone": selector.coords, 
        "char_data": char_data, 
        "threshold": "auto",
        "scan_delay": 150,
        "scan_random_delay": 100,
        "toggle_key": "space",
        "trigger_mode": "toggle"
    }
    with open(SETTINGS_FILE, "w") as f:
        json.dump(settings, f)
    return True

def edit_settings(settings):
    configured_chars = settings.get("char_data", {})
    available_images = [f[:-4] for f in os.listdir(CAPTURES_DIR) if f.endswith('.png')]
    
    captures = []
    char_data = {}

    for char in available_images:
        img_path = os.path.join(CAPTURES_DIR, f"{char}.png")
        try:
            img = Image.open(img_path)
            captures.append((char, img))
            char_data[char] = configured_chars.get(char, [])
        except Exception:
            continue
            
    if not captures:
        return False
        
    placer = DotPlacer(captures, existing_data=char_data)
    placer.wait_window()
    
    new_char_data = {}
    for idx, dots in placer.results.items():
        new_char_data[captures[idx][0]] = dots
        
    settings["char_data"] = new_char_data
    with open(SETTINGS_FILE, "w") as f:
        json.dump(settings, f)
    return True

def main():
    root = tk.Tk()
    root.withdraw()
    
    menu_message = ""
    settings_changed = True 
    settings = None
    
    while True:
        if settings_changed:
            settings = load_settings()
            manage_background_scanner(settings)
            settings_changed = False
            
        clear_screen()
        if menu_message:
            print(f"{menu_message}\n")
            menu_message = ""
            
        is_ready = bool(settings and settings.get("zone") and settings.get("char_data"))
        
        if settings:
            config_count = len(settings.get('char_data', {}))
            threshold = settings.get('threshold', 'auto')
            s_delay = settings.get('scan_delay', 150)
            s_rand = settings.get('scan_random_delay', 100)
            t_key = settings.get('toggle_key', 'space')
            t_mode = settings.get('trigger_mode', 'toggle')
            
            if is_ready:
                status_text = f"Ready (Listening in background) - Press '{t_key.upper()}' to toggle"
            else:
                status_text = "Scanner Disabled (Missing learning data or zone config)"
                
            print(f"Status: {status_text} | {config_count} keys set")
        else:
            threshold = 'auto'
            s_delay = 150
            s_rand = 100
            t_key = 'space'
            t_mode = 'toggle'
            print("Status: Scanner Disabled (No Settings Found)")
            
        print("\n0. Exit")
        print("1. Create New Settings (Wipes current data)")
        print("2. View / Edit Configured Pictures")
        print(f"3. Change Detection Threshold (Current: {threshold})")
        print(f"4. Change Scan Delays (Base: {s_delay}ms, Rand: {s_rand}ms)")
        print(f"5. Change Toggle Key (Current: {t_key})")
        print(f"6. Change Trigger Mode (Current: {t_mode})")
        
        choice = input("\nSelect an option: ").strip()
        
        if choice == '0':
            scanner_stop_event.set()
            print("Exiting tool...")
            break
            
        elif choice == '1':
            delete_settings()
            if create_new_settings():
                menu_message = "[Info] New settings created successfully."
            else:
                menu_message = "[Error] Setup cancelled or failed."
            settings_changed = True
                
        elif choice == '2':
            if not settings or not os.path.exists(CAPTURES_DIR):
                menu_message = "[Error] No settings or captures found."
            else:
                if edit_settings(settings):
                    menu_message = "[Info] Configurations updated successfully."
                else:
                    menu_message = "[Error] Failed to edit captures."
            settings_changed = True
                    
        elif choice == '3':
            if settings:
                print("\n1. Auto-detect from saved images\n2. Enter manual value (0-255)")
                t_choice = input("Select option (1-2): ").strip()
                if t_choice == '1':
                    new_val = auto_detect_threshold(settings["char_data"])
                    settings["threshold"] = new_val
                    with open(SETTINGS_FILE, "w") as f:
                        json.dump(settings, f)
                    menu_message = f"[Info] Threshold auto-detected and updated to: {new_val}"
                elif t_choice == '2':
                    try:
                        new_val = int(input("Enter new threshold (0-255): ").strip())
                        if 0 <= new_val <= 255:
                            settings["threshold"] = new_val
                            with open(SETTINGS_FILE, "w") as f:
                                json.dump(settings, f)
                            menu_message = "[Info] Threshold updated manually."
                        else:
                            menu_message = "[Error] Value must be between 0 and 255."
                    except ValueError:
                        menu_message = "[Error] Invalid input. Must be an integer."
                else:
                    menu_message = "[Error] Invalid choice."
                settings_changed = True
            else:
                menu_message = "[Error] Cannot change threshold. Create settings first."
                
        elif choice == '4':
            if settings:
                try:
                    new_base = int(input("Enter base scan delay in ms: ").strip())
                    new_rand = int(input("Enter max random delay to add in ms: ").strip())
                    if new_base >= 0 and new_rand >= 0:
                        settings["scan_delay"] = new_base
                        settings["scan_random_delay"] = new_rand
                        with open(SETTINGS_FILE, "w") as f:
                            json.dump(settings, f)
                        menu_message = "[Info] Scan delays updated."
                    else:
                        menu_message = "[Error] Delays cannot be negative."
                except ValueError:
                    menu_message = "[Error] Invalid input. Must be an integer."
                settings_changed = True
            else:
                menu_message = "[Error] Cannot change delays. Create settings first."
                
        elif choice == '5':
            if settings:
                new_key = input("Enter new toggle key (e.g., space, f9, insert, p): ").strip().lower()
                if new_key:
                    settings["toggle_key"] = new_key
                    with open(SETTINGS_FILE, "w") as f:
                        json.dump(settings, f)
                    menu_message = f"[Info] Toggle key set to '{new_key}'."
                else:
                    menu_message = "[Error] Invalid key input."
                settings_changed = True
            else:
                menu_message = "[Error] Cannot change toggle key. Create settings first."

        elif choice == '6':
            if settings:
                new_mode = "hold" if t_mode == "toggle" else "toggle"
                settings["trigger_mode"] = new_mode
                with open(SETTINGS_FILE, "w") as f:
                    json.dump(settings, f)
                menu_message = f"[Info] Trigger mode is now '{new_mode}'."
                settings_changed = True
            else:
                menu_message = "[Error] Cannot change trigger mode. Create settings first."
                
        else:
            menu_message = "[Error] Invalid selection. Try again."

if __name__ == "__main__":
    main()