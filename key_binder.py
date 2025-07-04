from pynput import keyboard

class KeyBinder:
    def __init__(self, start_callback, stop_callback):
        self.start_callback = start_callback
        self.stop_callback = stop_callback
        self.listener = keyboard.Listener(on_press=self.on_press)
        self.listener.start()

    def on_press(self, key):
        try:
            if key == keyboard.Key.f5:
                self.start_callback()
            elif key == keyboard.Key.f6:
                self.stop_callback()
        except Exception as e:
            print(f"Error in key binding: {e}")