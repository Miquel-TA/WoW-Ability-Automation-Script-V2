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

PROFILES_DIR = "profiles"
CAPTURES_DIR_BASE = "captures"
VISUAL_ZOOM = 4 

# Background thread management
bg_scanner_thread = None
scanner_stop_event = threading.Event()

def clear_screen():
    os.system('cls' if os.name == 'nt' else 'clear')

def get_profile_file(profile_name):
    return os.path.join(PROFILES_DIR, f"{profile_name}.json")

def get_captures_dir(profile_name):
    return os.path.join(CAPTURES_DIR_BASE, profile_name)

class AreaSelector(tk.Toplevel):
    def __init__(self):
        super().__init__()
        self.attributes('-alpha', 0.4)
        self.attributes('-fullscreen', True)
        self.config(cursor="cross")
        
        self.canvas = tk.Canvas(self, bg="black")
        self.canvas.pack(fill="both", expand=True)
        self.rect = None
        self.start_x = None
        self.start_y = None
        self.coords = None
        
        # Display instructions on screen
        self.canvas.create_text(
            self.winfo_screenwidth() // 2, self.winfo_screenheight() // 2,
            text="Click and drag to select the OCR zone.\nPress ESC to cancel.",
            fill="white", font=("Arial", 24, "bold"), justify="center"
        )
        
        self.canvas.bind("<ButtonPress-1>", self.on_press)
        self.canvas.bind("<B1-Motion>", self.on_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_release)
        self.bind("<Escape>", lambda e: self.destroy())

    def on_press(self, event):
        self.start_x = event.x
        self.start_y = event.y
        self.rect = self.canvas.create_rectangle(
            self.start_x, self.start_y, self.start_x, self.start_y, outline='red', width=3
        )

    def on_drag(self, event):
        x1 = min(self.start_x, event.x)
        y1 = min(self.start_y, event.y)
        x2 = max(self.start_x, event.x)
        y2 = max(self.start_y, event.y)
        self.canvas.coords(self.rect, x1, y1, x2, y2)

    def on_release(self, event):
        x1 = min(self.start_x, event.x)
        y1 = min(self.start_y, event.y)
        x2 = max(self.start_x, event.x)
        y2 = max(self.start_y, event.y)
        self.coords = {"left": x1, "top": y1, "width": x2 - x1, "height": y2 - y1}
        self.destroy()

def capture_learning_round(zone, profile_name):
    clear_screen()
    print("=========================================")
    print("           LEARNING ROUND")
    print("=========================================")
    print("\n[Instructions]")
    print("1. Press keys (a-z, 0-9) to capture the screen at your selected zone.")
    print("2. The captured image will be tied to the key you pressed.")
    print("3. Press [Escape] when you are finished to open the Dot Editor.")
    print("\nWaiting for keystrokes...")
    
    captures_dir = get_captures_dir(profile_name)
    if not os.path.exists(captures_dir):
        os.makedirs(captures_dir)
        
    captures = []
    captured_chars = set()
    
    def on_press(key):
        if key == keyboard.Key.esc:
            return False

        try:
            if hasattr(key, 'char') and key.char:
                char = key.char.lower()
                if char.isalnum() and char not in captured_chars:
                    captured_chars.add(char)
                    with mss() as sct:
                        img_data = sct.grab(zone)
                    img = Image.frombytes("RGB", img_data.size, img_data.bgra, "raw", "BGRX")
                    img_path = os.path.join(captures_dir, f"{char}.png")
                    img.save(img_path)
                    
                    captures.append((char, img))
                    print(f"[+] Captured image for key: '{char}'")
        except Exception:
            pass

    with keyboard.Listener(on_press=on_press) as listener:
        listener.join()
        
    return captures

class DotPlacer(tk.Toplevel):
    def __init__(self, captures, profile_name, zone, existing_data=None):
        super().__init__()
        self.captures = captures
        self.profile_name = profile_name
        self.captures_dir = get_captures_dir(profile_name)
        self.zone = zone
        self.index = 0
        self.results = {i: existing_data.get(captures[i][0], []) for i in range(len(captures))} if existing_data else {}
        self.current_dots = [] 
        
        self.title("Dot Configurator (Zoomed)")
        self.protocol("WM_DELETE_WINDOW", self.finish)
        
        self.tk_img = None 
        self.orig_w = 0
        self.orig_h = 0
        self.scaled_w = 0
        self.scaled_h = 0
        
        self.setup_ui()
        self.show_image()

    def setup_ui(self):
        if not self.captures:
            self.orig_w, self.orig_h = (50, 50)
        else:
            self.orig_w, self.orig_h = self.captures[0][1].size
            
        self.scaled_w = max(200, self.orig_w * VISUAL_ZOOM)
        self.scaled_h = max(200, self.orig_h * VISUAL_ZOOM)
        
        btn_frame_w = 260
        min_win_h = 240 
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
        
        # Action Buttons
        self.btn_frame = tk.Frame(self.right_frame)
        self.btn_frame.pack(fill=tk.BOTH, expand=True, padx=5)
        
        tk.Button(self.btn_frame, text="Clear Dots", command=self.clear_dots).grid(row=0, column=0, sticky="ew", padx=2, pady=5)
        tk.Button(self.btn_frame, text="Finish Setup", command=self.finish, bg="lightgreen").grid(row=0, column=1, sticky="ew", padx=2, pady=5)
        
        tk.Button(self.btn_frame, text="Last Image", command=self.prev_img).grid(row=1, column=0, sticky="ew", padx=2, pady=5)
        tk.Button(self.btn_frame, text="Next Image", command=self.next_img).grid(row=1, column=1, sticky="ew", padx=2, pady=5)
        
        tk.Button(self.btn_frame, text="Add New Key", command=self.add_new_key, bg="lightblue").grid(row=2, column=0, sticky="ew", padx=2, pady=15)
        tk.Button(self.btn_frame, text="Delete Key", command=self.delete_key, bg="lightcoral").grid(row=2, column=1, sticky="ew", padx=2, pady=15)
        
        self.btn_frame.columnconfigure(0, weight=1)
        self.btn_frame.columnconfigure(1, weight=1)

    def show_image(self):
        if not self.captures:
            self.lbl_char.config(text="No Images")
            self.canvas.delete("all")
            return

        if self.index >= len(self.captures):
            self.index = len(self.captures) - 1
            
        char, img = self.captures[self.index]
        self.orig_w, self.orig_h = img.size
        self.scaled_w = self.orig_w * VISUAL_ZOOM
        self.scaled_h = self.orig_h * VISUAL_ZOOM
        
        self.canvas.config(width=self.scaled_w, height=self.scaled_h)
        self.canvas.delete("all")
        
        self.current_dots = self.results.get(self.index, []).copy()
        self.lbl_char.config(text=f"Key: {char.upper()} ({self.index+1}/{len(self.captures)})")
        
        visual_img = img.resize((self.scaled_w, self.scaled_h), Image.NEAREST)
        self.tk_img = ImageTk.PhotoImage(visual_img)
        self.canvas.create_image(0, 0, anchor=tk.NW, image=self.tk_img)
        
        dot_radius = max(1, VISUAL_ZOOM // 2)
        for (x_orig, y_orig) in self.current_dots:
            x_vis = x_orig * VISUAL_ZOOM
            y_vis = y_orig * VISUAL_ZOOM
            self.canvas.create_oval(x_vis-dot_radius, y_vis-dot_radius, x_vis+dot_radius, y_vis+dot_radius, fill="red", outline="white", width=1)
            
    def add_dot(self, event):
        if not self.captures or event.x >= self.scaled_w or event.y >= self.scaled_h:
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
        if self.index < len(self.captures) - 1:
            self.index += 1
            self.show_image()
        
    def prev_img(self):
        if self.index > 0:
            self.index -= 1
            self.show_image()

    def add_new_key(self):
        print("\n[Info] Waiting for a new single alphanumeric key press (a-z, 0-9) to capture... (Press ESC to cancel)")
        self.withdraw()
        self.update() 
        
        captured_char = None
        captured_img = None
        
        def on_press(key):
            if key == keyboard.Key.esc:
                return False
            try:
                if hasattr(key, 'char') and key.char:
                    char = key.char.lower()
                    if char.isalnum():
                        nonlocal captured_char, captured_img
                        captured_char = char
                        with mss() as sct:
                            img_data = sct.grab(self.zone)
                        captured_img = Image.frombytes("RGB", img_data.size, img_data.bgra, "raw", "BGRX")
                        return False 
            except Exception:
                pass

        with keyboard.Listener(on_press=on_press) as listener:
            listener.join()
            
        if captured_char and captured_img:
            if not os.path.exists(self.captures_dir):
                os.makedirs(self.captures_dir)
            img_path = os.path.join(self.captures_dir, f"{captured_char}.png")
            captured_img.save(img_path)
            
            # Check if replacing or appending
            existing_idx = next((i for i, (c, _) in enumerate(self.captures) if c == captured_char), None)
            if existing_idx is not None:
                self.captures[existing_idx] = (captured_char, captured_img)
                self.results[existing_idx] = []
                self.index = existing_idx
            else:
                self.captures.append((captured_char, captured_img))
                new_idx = len(self.captures) - 1
                self.results[new_idx] = []
                self.index = new_idx
            print(f"[Info] Captured '{captured_char}' successfully.")
        else:
            print("[Info] Capture cancelled.")
            
        self.deiconify()
        self.show_image()

    def delete_key(self):
        if not self.captures: 
            return
            
        char, _ = self.captures[self.index]
        img_path = os.path.join(self.captures_dir, f"{char}.png")
        if os.path.exists(img_path):
            os.remove(img_path)
            
        self.captures.pop(self.index)
        
        # Shift results indices down
        new_results = {}
        for i in range(len(self.captures)):
            old_idx = i if i < self.index else i + 1
            new_results[i] = self.results.get(old_idx, [])
        self.results = new_results
        
        if not self.captures:
            self.index = 0
            print("[Info] All images deleted.")
        elif self.index >= len(self.captures):
            self.index = len(self.captures) - 1
            
        self.show_image()

    def finish(self):
        self.destroy()

def auto_detect_threshold(char_data, profile_name):
    min_val = 255
    valid_dots_found = False
    captures_dir = get_captures_dir(profile_name)
    
    for char, dots in char_data.items():
        if not dots:
            continue
            
        img_path = os.path.join(captures_dir, f"{char}.png")
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
    scan_delay = settings.get("scan_delay", 100) / 1000.0
    scan_random_delay = settings.get("scan_random_delay", 100) / 1000.0
    toggle_key_str = settings.get("toggle_key", "r").lower()
    trigger_mode = settings.get("trigger_mode", "hold")

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
    controller = keyboard.Controller()
    
    with mss() as sct:
        while not stop_event.is_set():
            if not pressing_enabled[0]:
                time.sleep(0.1)
                continue
                
            img_data = sct.grab(zone)
            best_char = None
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
                    else:
                        break 
                        
                if valid_dots > 0 and matched_dots == valid_dots:
                    if valid_dots > best_dot_count:
                        best_char = char
                        best_dot_count = valid_dots
                    
            if best_char:
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
        
    scanner_stop_event.clear()
    bg_scanner_thread = threading.Thread(
        target=scanner_worker, 
        args=(settings, scanner_stop_event), 
        daemon=True
    )
    bg_scanner_thread.start()
    return True

def load_settings(profile_name):
    filepath = get_profile_file(profile_name)
    if os.path.exists(filepath):
        with open(filepath, "r") as f:
            data = json.load(f)
            # Apply Request 4: New Defaults
            if "scan_delay" not in data: data["scan_delay"] = 100
            if "scan_random_delay" not in data: data["scan_random_delay"] = 100
            if "toggle_key" not in data: data["toggle_key"] = "r"
            if "trigger_mode" not in data: data["trigger_mode"] = "hold"
            return data
    return None

def delete_settings(profile_name):
    filepath = get_profile_file(profile_name)
    captures_dir = get_captures_dir(profile_name)
    if os.path.exists(filepath):
        os.remove(filepath)
    if os.path.exists(captures_dir):
        shutil.rmtree(captures_dir)

def create_new_settings(profile_name):
    selector = AreaSelector()
    selector.wait_window()
    
    if not selector.coords or selector.coords['width'] == 0 or selector.coords['height'] == 0:
        return False

    captures = capture_learning_round(selector.coords, profile_name)
    
    placer = DotPlacer(captures, profile_name, selector.coords)
    placer.wait_window()
    
    char_data = {}
    for idx, dots in placer.results.items():
        if idx < len(placer.captures) and dots:
            char_data[placer.captures[idx][0]] = dots
            
    settings = {
        "zone": selector.coords, 
        "char_data": char_data, 
        "scan_delay": 100,
        "scan_random_delay": 100,
        "toggle_key": "r",
        "trigger_mode": "hold"
    }
    
    # Request 5: Auto detect threshold automatically
    settings["threshold"] = auto_detect_threshold(char_data, profile_name)

    with open(get_profile_file(profile_name), "w") as f:
        json.dump(settings, f)
    return True

def edit_settings(settings, profile_name):
    configured_chars = settings.get("char_data", {})
    captures_dir = get_captures_dir(profile_name)
    
    available_images = [f[:-4] for f in os.listdir(captures_dir) if f.endswith('.png')] if os.path.exists(captures_dir) else []
    captures = []
    char_data = {}

    for char in available_images:
        img_path = os.path.join(captures_dir, f"{char}.png")
        try:
            img = Image.open(img_path)
            captures.append((char, img))
            char_data[char] = configured_chars.get(char, [])
        except Exception:
            continue
            
    placer = DotPlacer(captures, profile_name, settings["zone"], existing_data=char_data)
    placer.wait_window()
    
    new_char_data = {}
    for idx, dots in placer.results.items():
        if idx < len(placer.captures):
            new_char_data[placer.captures[idx][0]] = dots
        
    settings["char_data"] = new_char_data
    
    # Request 5: Update Auto Threshold after editing
    settings["threshold"] = auto_detect_threshold(new_char_data, profile_name)

    with open(get_profile_file(profile_name), "w") as f:
        json.dump(settings, f)
    return True

def switch_profile_menu(current_profile):
    clear_screen()
    print("=========================================")
    print("           PROFILE MANAGER")
    print("=========================================")
    profiles = [f[:-5] for f in os.listdir(PROFILES_DIR) if f.endswith('.json')]
    
    print("\nAvailable Profiles:")
    if not profiles:
        print("  (None found)")
    else:
        for i, p in enumerate(profiles):
            indicator = "-> " if p == current_profile else "   "
            print(f"{indicator}{i+1}. {p}")
            
    print("\nOptions:")
    print(" - Enter the NUMBER of an existing profile to load it.")
    print(" - Type a NEW NAME to create and switch to a new profile.")
    print(" - Press ENTER to cancel and return.")
    
    choice = input("\nSelection: ").strip()
    if not choice:
        return current_profile
        
    if choice.isdigit():
        idx = int(choice) - 1
        if 0 <= idx < len(profiles):
            return profiles[idx]
    
    # Validation for new profile names
    safe_name = "".join(c for c in choice if c.isalnum() or c in " _-")
    return safe_name if safe_name else current_profile

def initialize_directories():
    if not os.path.exists(PROFILES_DIR):
        os.makedirs(PROFILES_DIR)
    if not os.path.exists(CAPTURES_DIR_BASE):
        os.makedirs(CAPTURES_DIR_BASE)

def main():
    root = tk.Tk()
    root.withdraw()
    initialize_directories()
    
    profiles = [f[:-5] for f in os.listdir(PROFILES_DIR) if f.endswith('.json')]
    current_profile = profiles[0] if profiles else "default"
    
    menu_message = ""
    settings_changed = True 
    settings = None
    
    while True:
        if settings_changed:
            settings = load_settings(current_profile)
            manage_background_scanner(settings)
            settings_changed = False
            
        clear_screen()
        print("=========================================")
        print("         OCR MACRO - MAIN MENU")
        print("=========================================")
        print(f"Active Profile: [ {current_profile} ]")
        
        if menu_message:
            print(f"\n{menu_message}")
            menu_message = ""
            
        is_ready = bool(settings and settings.get("zone") and settings.get("char_data"))
        
        if settings:
            config_count = len(settings.get('char_data', {}))
            threshold = settings.get('threshold', 'Auto')
            s_delay = settings.get('scan_delay', 100)
            s_rand = settings.get('scan_random_delay', 100)
            t_key = settings.get('toggle_key', 'r')
            t_mode = settings.get('trigger_mode', 'hold')
            
            if is_ready:
                status_text = f"Ready (Listening in background) - Press '{t_key.upper()}' to {t_mode}"
            else:
                status_text = "Disabled (Missing dot data or zone config)"
                
            print(f"Status: {status_text}")
            print(f"Keys Configured: {config_count} | Threshold: {threshold} (Auto)")
        else:
            s_delay = 100
            s_rand = 100
            t_key = 'r'
            t_mode = 'hold'
            print("Status: Disabled (No Settings Found for this profile)")
            
        print("\n---------------- Options ----------------")
        print("1. Switch / Create Profile")
        print("2. Create New Settings (Wipes current profile data)")
        print("3. View / Edit Configured Pictures (Add/Delete keys)")
        print(f"4. Change Scan Delays (Base: {s_delay}ms, Rand: {s_rand}ms)")
        print(f"5. Change Toggle Key (Current: {t_key})")
        print(f"6. Change Trigger Mode (Current: {t_mode})")
        print("0. Exit")
        print("-----------------------------------------")
        
        choice = input("Select an option: ").strip()
        
        if choice == '0':
            scanner_stop_event.set()
            print("Exiting tool...")
            break
            
        elif choice == '1':
            new_profile = switch_profile_menu(current_profile)
            if new_profile != current_profile:
                current_profile = new_profile
                menu_message = f"[Info] Switched to profile '{current_profile}'."
                settings_changed = True
                
        elif choice == '2':
            delete_settings(current_profile)
            if create_new_settings(current_profile):
                menu_message = "[Info] New settings and threshold automatically calculated/created."
            else:
                menu_message = "[Error] Setup cancelled or failed."
            settings_changed = True
                
        elif choice == '3':
            if not settings or not os.path.exists(get_captures_dir(current_profile)):
                menu_message = "[Error] No setup found for this profile. Please create new settings first."
            else:
                if edit_settings(settings, current_profile):
                    menu_message = "[Info] Configurations updated successfully."
                else:
                    menu_message = "[Error] Failed to edit captures."
            settings_changed = True
                
        elif choice == '4':
            if settings:
                try:
                    new_base = int(input("\nEnter base scan delay in ms (e.g. 100): ").strip())
                    new_rand = int(input("Enter max random delay to add in ms (e.g. 100): ").strip())
                    if new_base >= 0 and new_rand >= 0:
                        settings["scan_delay"] = new_base
                        settings["scan_random_delay"] = new_rand
                        with open(get_profile_file(current_profile), "w") as f:
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
                # Request 6: Limit to 1 Alphanumeric character 
                new_key = input("\nEnter new toggle key (Only letters a-z or numbers 0-9): ").strip().lower()
                if len(new_key) == 1 and new_key.isalnum():
                    settings["toggle_key"] = new_key
                    with open(get_profile_file(current_profile), "w") as f:
                        json.dump(settings, f)
                    menu_message = f"[Info] Toggle key set to '{new_key}'."
                else:
                    menu_message = "[Error] Invalid key. You must enter exactly one alphanumeric character."
                settings_changed = True
            else:
                menu_message = "[Error] Cannot change toggle key. Create settings first."

        elif choice == '6':
            if settings:
                new_mode = "hold" if t_mode == "toggle" else "toggle"
                settings["trigger_mode"] = new_mode
                with open(get_profile_file(current_profile), "w") as f:
                    json.dump(settings, f)
                menu_message = f"[Info] Trigger mode is now '{new_mode}'."
                settings_changed = True
            else:
                menu_message = "[Error] Cannot change trigger mode. Create settings first."
                
        else:
            menu_message = "[Error] Invalid selection. Try again."

if __name__ == "__main__":
    main()