import os

class ScriptManager:
    def __init__(self):
        self.current_file = None

    def save_script(self, file_path, script):
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(script)
        self.current_file = file_path

    def load_script(self, file_path):
        with open(file_path, 'r', encoding='utf-8') as f:
            script = f.read()
        self.current_file = file_path
        return script