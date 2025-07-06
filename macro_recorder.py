import time
from pynput import mouse, keyboard

class MacroRecorder:
    def __init__(self):
        self.events = []
        self.last_time = None
        self.mouse_listener = None
        self.keyboard_listener = None
        self.is_recording = False
        self.last_click_time = 0
        self.last_click_pos = (0, 0)

    def start_recording(self):
        if self.is_recording: return
        self.events = []; self.last_time = time.time(); self.is_recording = True

        # Use a non-blocking listener setup
        self.mouse_listener = mouse.Listener(on_click=self.on_click)
        self.keyboard_listener = keyboard.Listener(on_press=self.on_press)
        
        self.mouse_listener.start()
        self.keyboard_listener.start()

    def stop_recording(self):
        if not self.is_recording: return None
        if self.mouse_listener: self.mouse_listener.stop()
        if self.keyboard_listener: self.keyboard_listener.stop()
        self.is_recording = False
        return self.events

    def add_event(self, event_type, **kwargs):
        current_time = time.time()
        delay = current_time - self.last_time
        self.last_time = current_time
        
        if delay > 0.2: # Only record meaningful waits to avoid clutter
            self.events.append({'type': 'wait', 'duration': round(delay, 2)})
            
        event_data = {'type': event_type, **kwargs}
        self.events.append(event_data)

    def on_click(self, x, y, button, pressed):
        if not pressed or not self.is_recording: return

        click_type = 'click_location'
        if button == mouse.Button.right:
            click_type = 'right_click_location'
        
        current_click_time = time.time()
        
        # Check for double-click
        if (current_click_time - self.last_click_time) < 0.3 and self.last_click_pos == (x,y):
            # It's a double click if it's fast and at the same spot
            # Remove the previous single click and its preceding wait
            if len(self.events) >= 2 and self.events[-1]['type'] == 'click_location':
                self.events.pop() # remove click
                if self.events and self.events[-1]['type'] == 'wait':
                    self.events.pop() # remove wait
            click_type = 'double_click_location'

        self.add_event(click_type, x=x, y=y)
        self.last_click_time = current_click_time
        self.last_click_pos = (x, y)

    def on_press(self, key):
        if not self.is_recording: return
        
        try:
            if isinstance(key, keyboard.KeyCode) and key.char:
                if self.events and self.events[-1]['type'] == 'type':
                    self.events[-1]['text'] += key.char
                else:
                    self.add_event('type', text=key.char)
            elif isinstance(key, keyboard.Key):
                self.add_event('key', key_name=key.name)
        except Exception as e:
            print(f"Could not record key: {e}")