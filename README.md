# Lightweight Dot-Based OCR Keypress Automation

This project is a lightweight, coordinate-based optical character recognition (OCR) system. It monitors a specified screen area, analyzes pixel brightness at predefined coordinates, and simulates keyboard events when the visual data matches known coordinate patterns.

## Architecture and Components

* **Screen Capture Engine**: Uses `mss` to perform high-speed, low-latency screen grabbing of the target bounding box.
* **Input Management**: Uses `pynput` to listen for hardware trigger keys and to simulate software output keypresses.
* **User Interface**: Uses `tkinter` to create a transparent overlay for bounding-box selection and a scaled visual interface to plot coordinate dots on captured images.
* **Scanner Thread**: Operates continuously as a daemon thread. It compares current screen pixels against stored coordinate arrays. The pattern matching logic uses an early-exit condition (stopping evaluation upon the first pixel mismatch) to reduce CPU load.

## Operation Logic

1. **Learning Phase**:
* The user defines a target screen area.
* The system records the screen area when the user presses an alphanumeric key.
* The user plots visual reference points (dots) on the captured image. These points must represent the brightest (mostly white) pixels of the character.


2. **Detection Phase**:
* The background thread captures the target area at a configured interval.
* It checks the RGB values of the pixels at the saved coordinate points.
* If the RGB values of all points for a character exceed the configured threshold, the system simulates a keypress for that character.



## Configuration Structure

The script stores operational parameters in `settings.json`.

* `zone`: The target screen area coordinates (`left`, `top`, `width`, `height`).
* `char_data`: A dictionary that maps target characters to lists of `[x, y]` relative pixel coordinates.
* `threshold`: An integer (`0-255`) that defines the minimum value for all three RGB channels to classify a pixel as active. The auto-detect function calculates this based on the darkest pixel among the selected coordinate points.
* `scan_delay`: The base delay between screen captures, in milliseconds.
* `scan_random_delay`: The maximum random time added to the base delay, in milliseconds. Use this to prevent rate-limiting or mimic human input.
* `toggle_key`: The keyboard key used to start or stop the scanning process.
* `trigger_mode`: Defines the trigger logic. Valid values are `toggle` (press to start, press to stop) or `hold` (scan only while the key is pressed).
