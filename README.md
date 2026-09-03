# Lightweight Coordinate-Based OCR Macro

A highly efficient, multithreaded Python script that monitors a defined screen region, analyzes pixel brightness at user-configured coordinates, and simulates keyboard events when the visual data matches known patterns. 

Rather than relying on heavy AI/ML libraries like Tesseract or OpenCV, this tool uses a lightweight **pixel-coordinate sampling** method (essentially placing "dots" on an image and checking their RGB values against an automatically calculated threshold). This results in extremely low latency and low CPU overhead.

## Use Case & Addon Integration
This tool is specifically designed to work in conjunction with UI-based rotation assistants in MMORPGs (such as World of Warcraft). 

By pairing this script with addons like **Hekili**, **Simple Assistent Combat Icon (SACI)**, or other equivalents:
1. The in-game addon calculates the optimal combat rotation and displays an icon or color block on the screen.
2. This script continuously monitors that specific screen coordinate.
3. When the tool detects the visual pattern matching a configured ability, it automatically executes the corresponding keystroke.

## How It Works

1. **Zone Selection**: Using a transparent `tkinter` overlay, the user defines a bounding box on their screen (the OCR zone).
2. **Learning Phase**: The user presses alphanumeric keys to capture screenshots of the OCR zone at that exact moment.
3. **Dot Mapping (The "OCR")**: Using the built-in GUI, the user places arbitrary "dots" (pixel coordinates) on the captured images. 
4. **Auto-Thresholding**: The script calculates the optimal RGB brightness threshold based on the darkest pixel selected during the mapping phase (minus a safety margin).
5. **Background Thread Execution**: 
   - A daemon thread uses `mss` to continuously grab the defined screen zone.
   - It checks the real-time pixel data against the mapped coordinates for each profile.
   - If a captured state matches all the mapped "dots" for a specific key (based on the auto-calculated threshold), `pynput` simulates that keypress.

## Key Features

* **Multi-Profile Management**: Configurations are saved as JSON files in a `profiles/` directory. Users can create, switch, and edit distinct configurations on the fly without restarting the script.
* **Dynamic GUI Editor**: An interactive Tkinter-based canvas that scales up captures (4x Zoom) for precise, pixel-perfect coordinate mapping. Allows for dynamic addition/deletion of keys within an active profile.
* **Smart Auto-Thresholding**: Eliminates the need for manual color calibration. The script automatically adjusts its detection sensitivity every time a profile is updated.
* **Safe Input Handling**: 
  - Toggle keys are restricted to single alphanumeric characters to prevent hooking loops or broken state machines.
  - Supports both `Hold` and `Toggle` trigger modes.
  - Configurable base and randomized scan delays to prevent input flooding and handle GCD (Global Cooldown) pacing.
* **Memory Safe**: Screen capturing relies on properly managed `mss` context managers, preventing GDI handle/memory leaks during extended background monitoring sessions.

## Technical Details

* **Language**: Python 3.x
* **Core Dependencies**: 
  * `mss`: Handles ultra-fast, cross-platform screen captures.
  * `pynput`: Manages asynchronous keyboard hooks and simulated keystrokes.
  * `Pillow (PIL)`: Processes image data for Tkinter rendering and pixel-value extraction.
  * `tkinter`: Standard GUI library used for the transparent overlay and the dot configurator.
* **Thread Safety**: The background scanner runs as a daemon thread and is cleanly managed using `threading.Event()` flags. Input listeners run in their own respective threads provided by `pynput`.
* **DPI Awareness**: Includes a `ctypes` call to enable Windows DPI awareness, ensuring the Tkinter overlay accurately maps to native screen coordinates on scaled displays.