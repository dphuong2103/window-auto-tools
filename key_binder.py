import json
import tkinter as tk
from pynput import keyboard

class KeyBinder:
    def __init__(self):
        self.listener = None; self.keybinds = {}; self.callbacks = {}

    def load_keybinds(self, filepath='config.json'):
        try:
            with open(filepath, 'r') as f: config = json.load(f)
            self.keybinds = config.get('keybinds', {})
        except FileNotFoundError:
            self.keybinds = {} # Will be populated with defaults
        
        # Ensure defaults exist
        self.keybinds.setdefault('start_script', '<f5>')
        self.keybinds.setdefault('stop_script', '<f6>')
        self.keybinds.setdefault('stop_macro', '<ctrl>+<shift>+<f12>')
        self.save_keybinds(filepath)
        return self.keybinds

    def save_keybinds(self, filepath='config.json'):
        try:
            with open(filepath, 'r') as f: config = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError): config = {}
        config['keybinds'] = self.keybinds
        with open(filepath, 'w') as f: json.dump(config, f, indent=4)

    def set_callbacks(self, start_callback, stop_callback, stop_macro_callback):
        self.callbacks['start_script'] = start_callback
        self.callbacks['stop_script'] = stop_callback
        self.callbacks['stop_macro'] = stop_macro_callback

    def start(self):
        if self.listener and self.listener.is_alive(): return
        self.hotkeys = {v.lower(): k for k, v in self.keybinds.items()}
        self.current_modifiers = set()
        
        def on_press(key):
            # Normalize key representation
            key_name = self.format_key(key)
            if not key_name: return

            is_modifier = key_name in {'ctrl', 'alt', 'shift'}
            if is_modifier:
                self.current_modifiers.add(key_name)
                return

            # Construct hotkey string
            if self.current_modifiers:
                hotkey_str = '+'.join(sorted(list(self.current_modifiers))) + '+' + key_name
            else:
                hotkey_str = key_name
            
            hotkey_str = hotkey_str.lower()
            
            if hotkey_str in self.hotkeys:
                action_name = self.hotkeys[hotkey_str]
                action = self.callbacks.get(action_name)
                if action: action()

        def on_release(key):
            key_name = self.format_key(key)
            if key_name in self.current_modifiers:
                self.current_modifiers.remove(key_name)

        self.listener = keyboard.Listener(on_press=on_press, on_release=on_release, suppress=False)
        self.listener.start()

    def stop(self):
        if self.listener: self.listener.stop(); self.listener = None

    def format_key(self, key):
        if key in [keyboard.Key.ctrl_l, keyboard.Key.ctrl_r]: return 'ctrl'
        if key in [keyboard.Key.alt_l, keyboard.Key.alt_r]: return 'alt'
        if key in [keyboard.Key.shift_l, keyboard.Key.shift_r]: return 'shift'
        if isinstance(key, keyboard.Key): return f'<{key.name}>'
        if isinstance(key, keyboard.KeyCode) and key.char: return key.char
        return None

    @staticmethod
    def capture_key(window):
        captured_key_str = None; dialog = tk.Toplevel(window)
        dialog.title("Capture Key"); dialog.geometry("300x150"); dialog.transient(window); dialog.grab_set()
        x = window.winfo_x() + (window.winfo_width()//2) - 150; y = window.winfo_y() + (window.winfo_height()//2) - 75
        dialog.geometry(f"+{x}+{y}")
        key_var = tk.StringVar(value="Press a key combination...")
        tk.Label(dialog, text="Press any key or key combination\n(e.g., F5, Ctrl+Shift+S)", font=("Segoe UI", 10)).pack(pady=10)
        tk.Label(dialog, textvariable=key_var, font=("Segoe UI", 12, "bold"), relief="solid", bd=1, width=25).pack(pady=10)
        
        current_modifiers = set()
        
        def on_press_capture(key):
            nonlocal captured_key_str
            key_name = KeyBinder.format_key(None, key)
            if not key_name: return
            if key_name in {'ctrl', 'alt', 'shift'}:
                current_modifiers.add(key_name.capitalize())
                key_var.set('+'.join(sorted(list(current_modifiers))))
                return
            final_key_name = key_name
            if current_modifiers:
                sorted_mods = '+'.join(sorted(list(current_modifiers)))
                captured_key_str = f"{sorted_mods}+{final_key_name}"
            else: captured_key_str = final_key_name
            key_var.set(captured_key_str)
            dialog.after(250, dialog.destroy)
            return False

        listener = keyboard.Listener(on_press=on_press_capture)
        listener.start(); dialog.wait_window(); listener.stop()
        return captured_key_str.lower() if captured_key_str else None