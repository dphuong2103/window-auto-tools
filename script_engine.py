import pyautogui
import pytesseract
import cv2
import time
import re
import os
import sys
import numpy as np
import json
from fuzzywuzzy import fuzz
from playsound import playsound

# Tesseract path setup
def resource_path(relative_path):
    try: base_path = sys._MEIPASS
    except Exception: base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)
TESSERACT_DIR = 'tesseract'
TESSERACT_EXE_PATH = resource_path(os.path.join(TESSERACT_DIR, 'tesseract.exe'))

class ScriptExitException(Exception):
    """Custom exception to signal a script exit command."""
    pass

class ScriptEngine:
    def __init__(self, update_output, update_status, popup_callback):
        self.update_output = update_output; self.update_status = update_status
        self.popup_callback = popup_callback
        self.running = False; self.variables = {}
        if os.path.exists(TESSERACT_EXE_PATH):
            pytesseract.pytesseract.tesseract_cmd = TESSERACT_EXE_PATH
        else: self.update_output(f"WARNING: Tesseract not found at {TESSERACT_EXE_PATH}")

    def _evaluate_expression(self, expression_str):
        if not expression_str.strip(): self.update_output("Error: Expression cannot be empty."); self.running = False; return None
        def replace_var(match):
            var_name = match.group(1)
            if var_name in self.variables: return str(self.variables[var_name])
            raise KeyError(f"Variable '${var_name}' not found.")
        processed_expr = re.sub(r'\$(\w+)', replace_var, expression_str)
        try:
            result = eval(processed_expr, {"__builtins__": {}}, {}); return result
        except Exception as e: self.update_output(f"Error evaluating '{processed_expr}': {e}"); self.running = False; return None

    def find_image_location(self, image_path):
        if not self.running: return None
        try:
            location = pyautogui.locateCenterOnScreen(image_path, confidence=0.8)
            if not location: self.update_output(f"Image '{os.path.basename(image_path)}' not found.")
            return location
        except Exception as e: self.update_output(f"Error locating image {image_path}: {e}"); return None
    def find_text_location(self, text_to_find):
        if not self.running: return None
        data = pytesseract.image_to_data(pyautogui.screenshot(), output_type=pytesseract.Output.DICT)
        best_match = {'ratio': 0, 'location': None}
        for i in range(len(data['text'])):
            word = data['text'][i].strip()
            if int(data['conf'][i]) > 50 and word:
                ratio = fuzz.partial_ratio(text_to_find.lower(), word.lower())
                if ratio > best_match['ratio']:
                    x, y, w, h = data['left'][i], data['top'][i], data['width'][i], data['height'][i]
                    best_match.update({'ratio': ratio, 'location': (x + w / 2, y + h / 2)})
        if best_match['ratio'] > 80: return best_match['location']
        self.update_output(f"Text '{text_to_find}' not found."); return None

    def run_script(self, script):
        self.running = True; self.update_status("Running... (F6 to stop)")
        lines = script.split('\n'); i = 0; loop_stack = []
        current_line_num = 0
        try:
            while i < len(lines) and self.running:
                line = lines[i].strip()
                current_line_num = i
                i += 1 
                if not line or line.startswith('#'): continue
                
                parts = line.split(' ', 1); command = parts[0]; args = parts[1] if len(parts) > 1 else ""
                if command.startswith('if_'):
                    condition_met = self.handle_if(command, args)
                    if not condition_met: i = self.find_matching_block_end(lines, i, ('if_', 'else'), ('else', 'endif'))
                elif command == 'else':
                    i = self.find_matching_block_end(lines, i, ('if_', 'else'), ('endif',))
                elif command == 'loop':
                    if not args.strip(): self.update_output("Error: loop command requires a count."); self.running = False; continue
                    loop_stack.append({'index': i, 'count': self._evaluate_expression(args)})
                elif command == 'endloop':
                    if loop_stack:
                        loop = loop_stack[-1]; loop['count'] -= 1
                        if loop['count'] > 0: i = loop['index']
                        else: loop_stack.pop()
                    else: self.update_output(f"Error: 'endloop' without 'loop' on line {current_line_num + 1}.")
                elif command == 'break':
                    if loop_stack: i = self.find_matching_block_end(lines, loop_stack.pop()['index'], ('loop',), ('endloop',))
                    else: self.update_output("Error: 'break' outside of a loop.")
                elif command == 'endif': pass
                else:
                    handler = getattr(self, f"handle_{command}", None)
                    if handler:
                        if not self.running: break
                        handler(args)
                    else: self.update_output(f"Unknown command: '{command}'")

        except ScriptExitException:
            self.update_output("Script execution terminated by 'exit' command.")
            self.running = False
        except Exception as e:
            self.update_output(f"ERROR on line {current_line_num + 1}: {lines[current_line_num].strip()}\n -> {e}"); self.running = False
        
        is_finished_normally = self.running 
        status = "Finished" if is_finished_normally else "Stopped"
        self.update_status(status); self.running = False
        return is_finished_normally

    def stop_script(self):
        if self.running: self.running = False; self.update_output("Stop signal received...")

    def perform_mouse_action(self, action_func, location, action_name):
        if not self.running: return
        if not location: self.update_output(f"Action '{action_name}' failed: target not found."); return
        if action_func == pyautogui.click: action_func(location, interval=0.1)
        else: action_func(location)
        self.update_output(f"Performed {action_name} at {location}")

    def handle_click_location(self, args): x, y = map(int, args.split()); self.perform_mouse_action(pyautogui.click, (x, y), 'click_location')
    def handle_click_text(self, args): self.perform_mouse_action(pyautogui.click, self.find_text_location(args.strip('"')), 'click_text')
    def handle_click_image(self, args): self.perform_mouse_action(pyautogui.click, self.find_image_location(args.strip('"')), 'click_image')
    def handle_double_click_location(self, args): x, y = map(int, args.split()); self.perform_mouse_action(pyautogui.doubleClick, (x, y), 'double_click_location')
    def handle_double_click_text(self, args): self.perform_mouse_action(pyautogui.doubleClick, self.find_text_location(args.strip('"')), 'double_click_text')
    def handle_double_click_image(self, args): self.perform_mouse_action(pyautogui.doubleClick, self.find_image_location(args.strip('"')), 'double_click_image')
    def handle_right_click_location(self, args): x, y = map(int, args.split()); self.perform_mouse_action(pyautogui.rightClick, (x, y), 'right_click_location')
    def handle_move_to(self, args): x, y = map(int, args.split()); pyautogui.moveTo(x, y); self.update_output(f"Moved mouse to ({x},{y})")
    def handle_click_and_drag(self, args): x1, y1, x2, y2, duration = args.split(); pyautogui.moveTo(int(x1), int(y1)); pyautogui.dragTo(int(x2), int(y2), duration=float(duration)); self.update_output(f"Dragged from ({x1},{y1}) to ({x2},{y2})")
    def handle_scroll(self, args): pyautogui.scroll(int(args)); self.update_output(f"Scrolled {args} units")
    def handle_wait(self, args):
        seconds = float(self._evaluate_expression(args)); end_time = time.time() + seconds
        while time.time() < end_time:
            if not self.running: break
            time.sleep(0.1)
        if self.running: self.update_output(f"Waited for {seconds}s.")
    handle_delay = handle_wait
    def handle_select_window(self, args):
        title = args.strip('"')
        try: window = pyautogui.getWindowsWithTitle(title)[0]; window.activate(); self.update_output(f"Activated window: {title}")
        except IndexError: self.update_output(f"Window '{title}' not found.")
    def handle_key(self, args): pyautogui.press(args); self.update_output(f"Pressed key: {args}")
    def handle_type(self, args): text = args.strip('"'); pyautogui.write(text, interval=0.05); self.update_output(f"Typed: {text}")
    def handle_var(self, args):
        name, value_str = args.split(' ', 1)
        if '$' in value_str or (value_str.strip().replace('.', '', 1).isdigit()): self.variables[name] = self._evaluate_expression(value_str)
        else: self.variables[name] = value_str.strip('"')
        self.update_output(f"Set var {name} = {self.variables[name]}")
    def handle_eval(self, args): var_name, expression = [p.strip() for p in args.split('=', 1)]; self.variables[var_name] = self._evaluate_expression(expression)
    def handle_popup(self, args): message = args.strip('"'); self.update_output(f"Showing popup: {message}"); self.popup_callback(message)
    def handle_get_text_region(self, args):
        parts = args.split(); var_name = parts[0]; x1, y1, x2, y2 = map(int, parts[1:])
        region = (x1, y1, x2 - x1, y2 - y1)
        text = pytesseract.image_to_string(pyautogui.screenshot(region=region)).strip()
        self.variables[var_name] = text
        self.update_output(f"Got text '{text}' from region and stored in var {var_name}")
    def handle_playback(self, args):
        path = args.strip('"')
        if not os.path.exists(path): self.update_output(f"Macro file not found: {path}"); return
        with open(path, 'r') as f: events = json.load(f)
        self.update_output(f"--- Playing back macro: {os.path.basename(path)} ---")
        for event in events:
            if not self.running: break
            cmd, e_args = event['type'], {k:v for k,v in event.items() if k != 'type'}
            handler = getattr(self, f"handle_{cmd}", None)
            if handler: handler(" ".join(map(str, e_args.values())))
        self.update_output(f"--- Finished macro playback ---")
    
    def handle_script(self, args):
        path = args.strip('"')
        if not os.path.exists(path): self.update_output(f"Sub-script not found: {path}"); return
        try:
            with open(path, 'r', encoding='utf-8') as f: script_content = f.read()
            self.update_output(f"--- Starting sub-script: {os.path.basename(path)} ---")
            sub_engine = ScriptEngine(self.update_output, self.update_status, self.popup_callback)
            sub_engine.variables = self.variables.copy()
            sub_script_finished_normally = sub_engine.run_script(script_content)
            if not sub_script_finished_normally:
                self.running = False
            else: # parent script inherits variables from child
                self.variables.update(sub_engine.variables)
            self.update_output(f"--- Finished sub-script: {os.path.basename(path)} ---")
        except ScriptExitException:
            # Propagate exit command to stop this script as well
            raise ScriptExitException()
        except Exception as e: self.update_output(f"Error in sub-script {path}: {e}")

    def handle_log(self, args): self.update_output(f"LOG: {args.strip('"')}")

    def handle_sound(self, args):
        path = args.strip('"')
        if not os.path.exists(path): self.update_output(f"Sound file not found: {path}"); return
        try:
            playsound(path, block=False)
            self.update_output(f"Played sound: {os.path.basename(path)}")
        except Exception as e:
            self.update_output(f"Could not play sound {path}: {e}")

    def handle_screenshot(self, args):
        parts = args.split()
        path = parts[0].strip('"')
        region = None
        if len(parts) == 5:
            x1, y1, x2, y2 = map(int, parts[1:])
            region = (x1, y1, x2 - x1, y2 - y1)
        
        try:
            pyautogui.screenshot(path, region=region)
            self.update_output(f"Screenshot saved to {path}")
        except Exception as e:
            self.update_output(f"Failed to take screenshot: {e}")

    def handle_exit(self, args):
        raise ScriptExitException()

    def handle_mouse_pos(self, args):
        parts = args.split()
        if len(parts) != 2: self.update_output("Error: mouse_pos requires two variable names."); return
        var_x, var_y = parts
        x, y = pyautogui.position()
        self.variables[var_x] = x
        self.variables[var_y] = y
        self.update_output(f"Stored mouse position ({x}, {y}) in ${var_x} and ${var_y}")

    def handle_if(self, command, args):
        if not self.running: return False
        should_be_true = not command.startswith('if_not_')
        check_command = command.replace('if_not_', 'if_')
        result = False
        if check_command == "if_eval": result = self._evaluate_expression(args)
        elif check_command == "if_image_screen": result = self.find_image_location(args.strip('"')) is not None
        elif check_command == "if_text_screen": result = self.find_text_location(args.strip('"')) is not None
        elif check_command == "if_text_region":
            match = re.match(r'"([^"]+)"\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)', args)
            if not match: return False
            text, x1, y1, x2, y2 = match.groups(); region = (int(x1), int(y1), int(x2)-int(x1), int(y2)-int(y1))
            found_text = pytesseract.image_to_string(pyautogui.screenshot(region=region))
            is_match = fuzz.partial_ratio(text.lower(), found_text.lower()) > 80
            self.update_output(f"IF: Check for '{text}' in {region}. Match: {is_match}"); result = is_match
        elif check_command == "if_pixel_matches":
            parts = args.split(); x, y, r, g, b = map(int, parts[:5]); tolerance = int(parts[5]) if len(parts) > 5 else 0
            match = pyautogui.pixelMatchesColor(x, y, (r, g, b), tolerance=tolerance)
            self.update_output(f"IF: Pixel at ({x},{y}) matches ({r},{g},{b}) with tolerance {tolerance}. Match: {match}"); result = match

        return result if should_be_true else not result
        
    def find_matching_block_end(self, lines, start_index, start_cmds, end_cmds):
        level = 1; i = start_index
        while i < len(lines):
            line = lines[i].strip()
            command = line.split(' ', 1)[0]
            if any(command.startswith(s) for s in start_cmds): level += 1
            elif command in end_cmds: level -= 1
            if level == 0: return i + 1
            i += 1
        self.update_output(f"Error: Missing block end for block starting near line {start_index}."); self.running = False; return len(lines)