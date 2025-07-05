import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog
import os
import sys
import threading
import subprocess
import logging
import re
from script_engine import ScriptEngine
from script_manager import ScriptManager
from pynput import mouse

# --- NEW: Helper classes for Line Numbers and Syntax Highlighting ---
class TextLineNumbers(tk.Canvas):
    def __init__(self, *args, **kwargs):
        tk.Canvas.__init__(self, *args, **kwargs)
        self.textwidget = None

    def attach(self, text_widget):
        self.textwidget = text_widget

    def redraw(self, *args):
        '''Redraw line numbers'''
        self.delete("all")

        i = self.textwidget.index("@0,0")
        while True :
            dline= self.textwidget.dlineinfo(i)
            if dline is None: break
            y = dline[1]
            linenum = str(i).split(".")[0]
            self.create_text(2, y, anchor="nw", text=linenum, fill="#606366")
            i = self.textwidget.index("%s+1line" % i)

class SyntaxHighlighter:
    def __init__(self, text_widget):
        self.text = text_widget
        self.text.bind("<<Modified>>", self.on_text_modified)
        
        # Define patterns and corresponding tags
        self.patterns = {
            'command': r'\b(click|double_click|right_click|move_to|scroll|click_and_drag|wait|delay|loop|endloop|break|if|endif|eval|var|script|popup|log|select_window|key|type)\w*\b',
            'string': r'\"[^\"\n]*\"',
            'comment': r'#.*',
            'number': r'\b-?\d+(\.\d+)?\b',
            'operator': r'[\+\-\*/<>=!]=?',
        }
        
        # Configure tags with colors
        self.text.tag_configure("command", foreground="#0000ff") # Blue
        self.text.tag_configure("string", foreground="#dd1144")  # Red
        self.text.tag_configure("comment", foreground="#228B22") # Green
        self.text.tag_configure("number", foreground="#800080")  # Purple
        self.text.tag_configure("operator", foreground="#800080")# Purple
    
    def on_text_modified(self, event=None):
        # This simple flag mechanism prevents recursive modification events
        if self.text.edit_modified():
            self.highlight_all()
            self.text.edit_modified(False)

    def highlight_all(self):
        # Remove all existing tags
        for tag in self.text.tag_names():
            if tag != "sel": # Don't remove the selection tag
                self.text.tag_remove(tag, "1.0", "end")
        
        # Apply new tags based on patterns
        for tag, pattern in self.patterns.items():
            self.apply_tag(tag, pattern)

    def apply_tag(self, tag, pattern):
        text_content = self.text.get("1.0", "end")
        for match in re.finditer(pattern, text_content):
            start, end = match.span()
            start_index = self.text.index(f"1.0 + {start} chars")
            end_index = self.text.index(f"1.0 + {end} chars")
            self.text.tag_add(tag, start_index, end_index)

# --- Other Helper Classes (no changes) ---
class Tooltip: # ... (same as before) ...
    def __init__(self, widget, text):
        self.widget = widget; self.text = text; self.tip_window = None
        self.widget.bind("<Enter>", self.show_tip); self.widget.bind("<Leave>", self.hide_tip)
    def show_tip(self, event=None):
        if self.tip_window or not self.text: return
        x, y, _, _ = self.widget.bbox("insert"); x += self.widget.winfo_rootx() + 25; y += self.widget.winfo_rooty() + 25
        self.tip_window = tw = tk.Toplevel(self.widget); tw.wm_overrideredirect(True); tw.wm_geometry(f"+{x}+{y}")
        label = tk.Label(tw, text=self.text, justify='left', background="#ffffe0", relief='solid', borderwidth=1, font=("tahoma", "8", "normal"))
        label.pack(ipadx=1)
    def hide_tip(self, event=None):
        if self.tip_window: self.tip_window.destroy(); self.tip_window = None
class BaseOverlay(tk.Toplevel): # ... (same as before) ...
    def __init__(self, root, on_complete):
        super().__init__(root)
        self.on_complete = on_complete; self.root = root
        self.wm_attributes("-alpha", 0.3); self.overrideredirect(True); self.geometry(f"{self.winfo_screenwidth()}x{self.winfo_screenheight()}+0+0")
        self.focus_force(); self.grab_set(); self.bind("<Escape>", self.cancel)
    def cancel(self, event=None):
        self.destroy(); self.root.deiconify(); self.root.lift(); self.on_complete(None)
class PointSelectorOverlay(BaseOverlay): # ... (same as before) ...
    def __init__(self, root, on_complete):
        super().__init__(root, on_complete)
        self.config(cursor="crosshair"); self.bind("<ButtonRelease-1>", self.on_click)
    def on_click(self, event):
        coords = (event.x_root, event.y_root); self.destroy(); self.root.deiconify(); self.root.lift(); self.on_complete(coords)
class RegionSelectorOverlay(BaseOverlay): # ... (same as before) ...
    def __init__(self, root, on_complete):
        super().__init__(root, on_complete)
        self.start_x = 0; self.start_y = 0; self.rect = None
        self.canvas = tk.Canvas(self, cursor="crosshair", bg="black"); self.canvas.pack(fill="both", expand=True)
        self.canvas.bind("<ButtonPress-1>", self.on_press); self.canvas.bind("<B1-Motion>", self.on_drag); self.canvas.bind("<ButtonRelease-1>", self.on_release)
    def on_press(self, event):
        self.start_x = event.x_root; self.start_y = event.y_root
        self.rect = self.canvas.create_rectangle(self.start_x, self.start_y, self.start_x, self.start_y, outline='red', width=2)
    def on_drag(self, event):
        if self.rect: self.canvas.coords(self.rect, self.start_x, self.start_y, event.x_root, event.y_root)
    def on_release(self, event):
        end_x, end_y = event.x_root, event.y_root; x1, y1 = min(self.start_x, end_x), min(self.start_y, end_y); x2, y2 = max(self.start_x, end_x), max(self.start_y, end_y)
        self.destroy(); self.root.deiconify(); self.root.lift(); self.on_complete((x1, y1, x2, y2))


# --- Main Application ---
class AutomationApp:
    def __init__(self, root, file_to_open=None):
        self.root = root
        self.root.title("Automation Script Editor"); self.root.geometry("950x700")
        self.selection_mode = None; self.current_command = None; self.drag_start_pos = None; self.mouse_listener = None
        self.is_script_running = threading.Event()
        
        self.setup_gui(); self.setup_logging()
        self.script_manager = ScriptManager()
        self.engine = ScriptEngine(self.update_output, self.update_status, self.show_popup)
        
        if file_to_open: self.load_script_from_path(file_to_open)

    def setup_logging(self):
        logging.basicConfig(filename='automation.log', level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
        self.logger = logging.getLogger()
    def show_popup(self, message):
        self.root.after(0, lambda: messagebox.showinfo("Script Message", message))

    def setup_gui(self):
        style = ttk.Style(self.root); style.theme_use('clam')
        self.main_frame = ttk.Frame(self.root, padding="10"); self.main_frame.pack(fill="both", expand=True)
        self.main_frame.columnconfigure(0, weight=1); self.main_frame.columnconfigure(1, weight=0); self.main_frame.rowconfigure(0, weight=1)

        paned_window = ttk.PanedWindow(self.main_frame, orient=tk.VERTICAL); paned_window.grid(row=0, column=0, sticky="nsew", pady=5)
        
        # --- EDITOR SETUP (UPDATED) ---
        editor_outer_frame = ttk.Labelframe(paned_window, text="Script Editor", padding=5)
        editor_outer_frame.columnconfigure(1, weight=1); editor_outer_frame.rowconfigure(0, weight=1)
        
        # Line numbers
        self.linenumbers = TextLineNumbers(editor_outer_frame, width=30, bg="#f0f0f0")
        self.linenumbers.grid(row=0, column=0, sticky="ns")
        
        # Text editor widget
        self.editor = tk.Text(editor_outer_frame, height=20, width=80, font=("Courier New", 10), undo=True, wrap="word")
        self.editor.grid(row=0, column=1, sticky="nsew")
        
        # Scrollbar
        editor_scrollbar = ttk.Scrollbar(editor_outer_frame, orient=tk.VERTICAL, command=self.editor.yview)
        editor_scrollbar.grid(row=0, column=2, sticky="ns")
        self.editor['yscrollcommand'] = editor_scrollbar.set
        
        # Attach line numbers to editor
        self.linenumbers.attach(self.editor)
        
        # Create syntax highlighter
        self.highlighter = SyntaxHighlighter(self.editor)

        # Sync scrolling and redraw line numbers
        def on_scroll(*args):
            editor_scrollbar.set(*args)
            self.linenumbers.redraw()
        self.editor['yscrollcommand'] = on_scroll
        
        def on_editor_change(event):
            self.linenumbers.redraw()
        self.editor.bind("<<Modified>>", on_editor_change, add=True) # add=True to not overwrite highlighter's bind

        paned_window.add(editor_outer_frame, weight=3)
        
        output_frame = ttk.Labelframe(paned_window, text="Output Console", padding=5); output_frame.columnconfigure(0, weight=1); output_frame.rowconfigure(0, weight=1)
        self.output = tk.Text(output_frame, height=10, width=80, state='disabled', font=("Courier New", 10)); self.output.grid(row=0, column=0, sticky="nsew")
        output_scrollbar = ttk.Scrollbar(output_frame, orient=tk.VERTICAL, command=self.output.yview); output_scrollbar.grid(row=0, column=1, sticky="ns")
        self.output['yscrollcommand'] = output_scrollbar.set; paned_window.add(output_frame, weight=1)

        # --- COMMAND PANEL (no changes) ---
        cmd_outer_frame = ttk.LabelFrame(self.main_frame, text="Commands", padding=5); cmd_outer_frame.grid(row=0, column=1, sticky="ns", padx=(10, 0))
        cmd_canvas = tk.Canvas(cmd_outer_frame, borderwidth=0, highlightthickness=0, width=200)
        cmd_scrollbar = ttk.Scrollbar(cmd_outer_frame, orient="vertical", command=cmd_canvas.yview)
        self.command_panel = ttk.Frame(cmd_canvas)
        cmd_canvas.configure(yscrollcommand=cmd_scrollbar.set); cmd_scrollbar.pack(side="right", fill="y"); cmd_canvas.pack(side="left", fill="both", expand=True)
        canvas_frame_id = cmd_canvas.create_window((0, 0), window=self.command_panel, anchor="nw")
        self.command_panel.bind("<Configure>", lambda e: cmd_canvas.configure(scrollregion=cmd_canvas.bbox("all")))
        cmd_canvas.bind("<Configure>", lambda e: cmd_canvas.itemconfig(canvas_frame_id, width=e.width))
        cmd_canvas.bind_all("<MouseWheel>", lambda e: cmd_canvas.yview_scroll(int(-1*(e.delta/120)), "units"))
        commands = { "Click": [('click_location', 'click (location)'), ('click_text', 'click (text)'), ('click_image', 'click (image)')], "Double-Click": [('double_click_location', 'double_click (location)'), ('double_click_text', 'double_click (text)'), ('double_click_image', 'double_click (image)')], "Other Mouse": [('right_click_location', 'right_click (location)'), ('move_to', 'move_to (location)'), ('click_and_drag', 'click_and_drag'), ('scroll', 'scroll')], "Variables & Logic": [('var', 'var (set variable)'), ('eval', 'eval (math)'), ('if_eval', 'if (logic)')], "Conditional (IF)": [('if_text_region', 'if (text in region)'), ('if_text_screen', 'if (text on screen)'), ('if_image_screen', 'if (image on screen)'), ('endif', 'endif')], "Loops": ['loop', 'endloop', 'break'], "Flow & Logging": ['script', 'popup', 'log'], "Timing": ['wait', 'delay'], "Window & Keyboard": ['select_window', 'key', 'type'] }
        row = 0
        for category, cmds in commands.items():
            ttk.Label(self.command_panel, text=category, font=("Arial", 10, "bold")).grid(row=row, column=0, sticky="w", pady=(10, 2), padx=5); row += 1
            for cmd_item in cmds:
                if isinstance(cmd_item, tuple): cmd_id, cmd_text = cmd_item
                else: cmd_id, cmd_text = cmd_item, cmd_item
                btn = ttk.Button(self.command_panel, text=cmd_text, command=lambda c=cmd_id: self.insert_command(c)); btn.grid(row=row, column=0, sticky="ew", pady=1, padx=5); Tooltip(btn, f"Insert {cmd_text} command."); row += 1
        
        self.status_var = tk.StringVar(value="Ready"); status_bar = ttk.Label(self.main_frame, textvariable=self.status_var, relief=tk.SUNKEN, anchor='w', padding=5); status_bar.grid(row=1, column=0, columnspan=2, sticky="ew")
        
        menubar = tk.Menu(self.root); filemenu = tk.Menu(menubar, tearoff=0)
        filemenu.add_command(label="New Window", command=self.new_script_window)
        filemenu.add_command(label="Open in New Window...", command=self.open_script_window)
        filemenu.add_separator(); filemenu.add_command(label="Save", command=self.save_script); filemenu.add_command(label="Save As...", command=self.save_script_as)
        filemenu.add_separator(); filemenu.add_command(label="Exit", command=self.quit_app)
        menubar.add_cascade(label="File", menu=filemenu); self.root.config(menu=menubar)

        self.root.bind('<F5>', self.start_script_event); self.root.bind('<F6>', self.stop_script_event); self.root.bind('<Escape>', self.cancel_selection_with_event)
    
    # --- Other methods (no significant changes) ---
    def new_script_window(self): subprocess.Popen([sys.executable, sys.argv[0]])
    def open_script_window(self):
        file_path = filedialog.askopenfilename(defaultextension=".txt", filetypes=[("Text Files", "*.txt"), ("All files", "*.*")])
        if file_path: subprocess.Popen([sys.executable, sys.argv[0], file_path])
    def load_script_from_path(self, file_path):
        try:
            script = self.script_manager.load_script(file_path); self.editor.delete("1.0", tk.END); self.editor.insert("1.0", script)
            self.root.title(f"Automation Script Editor - {os.path.basename(file_path)}"); self.update_status(f"Loaded {os.path.basename(file_path)}")
            # Manually trigger highlighter and line numbers after loading
            self.highlighter.highlight_all()
            self.linenumbers.redraw()
        except Exception as e: messagebox.showerror("Error", f"Failed to load script: {e}"); self.logger.error(f"Failed to load {file_path}: {e}")
    def save_script(self):
        if self.script_manager.current_file:
            try: self.script_manager.save_script(self.script_manager.current_file, self.editor.get("1.0", tk.END)); self.update_status(f"Saved {os.path.basename(self.script_manager.current_file)}")
            except Exception as e: messagebox.showerror("Error", f"Failed to save script: {e}"); self.logger.error(f"Failed to save {self.script_manager.current_file}: {e}")
        else: self.save_script_as()
    def save_script_as(self):
        file_path = filedialog.asksaveasfilename(defaultextension=".txt", filetypes=[("Text Files", "*.txt"), ("All files", "*.*")])
        if file_path:
            try:
                self.script_manager.save_script(file_path, self.editor.get("1.0", tk.END))
                self.root.title(f"Automation Script Editor - {os.path.basename(file_path)}"); self.update_status(f"Saved to {os.path.basename(file_path)}")
            except Exception as e: messagebox.showerror("Error", f"Failed to save script: {e}"); self.logger.error(f"Failed to save {file_path}: {e}")
    def quit_app(self):
        if self.is_script_running.is_set():
            if messagebox.askokcancel("Quit", "A script is running. Quit anyway?"): self.stop_script_event(); self.root.destroy()
        else: self.root.destroy()
    def insert_command(self, command_id):
        self.cancel_selection(); self.current_command = command_id
        if command_id in ['click_location', 'double_click_location', 'right_click_location', 'move_to']: self.selection_mode = 'point'; self.status_var.set(f"Click a point on screen (Esc to cancel)"); self.root.iconify(); PointSelectorOverlay(self.root, self.finalize_point_selection)
        elif command_id == 'click_and_drag': self.selection_mode = 'drag_start'; self.status_var.set("Click the START point (Esc to cancel)"); self.start_pynput_listener()
        elif command_id == 'if_text_region': self.selection_mode = 'region'; self.status_var.set("Drag a region to check for text (Esc to cancel)"); self.root.iconify(); RegionSelectorOverlay(self.root, self.finalize_region_selection)
        elif command_id in ['click_image', 'double_click_image', 'if_image_screen']:
            file_path = filedialog.askopenfilename(title="Select Image File", filetypes=[("Image files", "*.png *.jpg *.bmp")])
            if file_path: self.editor.insert(tk.INSERT, f"{command_id} \"{file_path}\"\n")
        elif command_id in ['click_text', 'double_click_text', 'if_text_screen']:
            text = simpledialog.askstring("Input", "Enter text to find on screen:", parent=self.root)
            if text: self.editor.insert(tk.INSERT, f"{command_id} \"{text}\"\n")
        elif command_id == 'script':
            file_path = filedialog.askopenfilename(title="Select Script File", filetypes=[("Text files", "*.txt")])
            if file_path: self.editor.insert(tk.INSERT, f"script \"{file_path}\"\n")
        else:
            line_content = f"{command_id}\n" if command_id in ['endloop', 'endif', 'break'] else f"{command_id} "
            self.editor.insert(tk.INSERT, line_content); self.status_var.set(f"Inserted {command_id}. Fill in parameters.")
    def start_pynput_listener(self): self.root.iconify(); self.mouse_listener = mouse.Listener(on_click=self.on_global_click); self.mouse_listener.start()
    def on_global_click(self, x, y, button, pressed):
        if not pressed or button != mouse.Button.left: return True
        if self.selection_mode == 'drag_start': self.drag_start_pos = (x, y); self.selection_mode = 'drag_end'; self.root.after(0, self.update_status, "Click the END point (Esc to cancel)"); return True
        elif self.selection_mode == 'drag_end': self.root.after(0, self.finalize_drag_selection, self.drag_start_pos, (x, y)); return False
    def stop_pynput_listener(self):
        if self.mouse_listener: self.mouse_listener.stop(); self.mouse_listener = None
    def finalize_point_selection(self, coords):
        if coords: x, y = coords; self.editor.insert(tk.INSERT, f"{self.current_command} {x} {y}\n"); self.status_var.set(f"Captured for {self.current_command}: ({x}, {y})")
        else: self.status_var.set("Selection cancelled.")
        self.cancel_selection()
    def finalize_drag_selection(self, start_pos, end_pos):
        self.stop_pynput_listener(); self.root.deiconify(); self.root.lift()
        duration = simpledialog.askfloat("Input", "Drag duration (s):", parent=self.root, minvalue=0.1, maxvalue=10.0, initialvalue=1.0)
        if duration is None: duration = 1.0
        self.editor.insert(tk.INSERT, f"click_and_drag {start_pos[0]} {start_pos[1]} {end_pos[0]} {end_pos[1]} {duration}\n")
        self.cancel_selection()
    def finalize_region_selection(self, region):
        if region:
            text = simpledialog.askstring("Input", "Enter text to find in region:", parent=self.root)
            if text: x1, y1, x2, y2 = region; self.editor.insert(tk.INSERT, f"if_text_region \"{text}\" {x1} {y1} {x2} {y2}\n"); self.status_var.set("Region/text captured.")
            else: self.status_var.set("Region selection cancelled: no text.")
        else: self.status_var.set("Region selection cancelled.")
        self.cancel_selection()
    def cancel_selection_with_event(self, event=None): self.cancel_selection()
    def cancel_selection(self):
        self.stop_pynput_listener();
        if self.selection_mode: self.root.deiconify()
        self.selection_mode = None; self.current_command = None; self.drag_start_pos = None; self.status_var.set("Ready")
    def update_output(self, message):
        def _update(): self.output.config(state='normal'); self.output.insert(tk.END, message + '\n'); self.output.see(tk.END); self.output.config(state='disabled'); self.logger.info(message)
        if self.root: self.root.after(0, _update)
    def update_status(self, status):
        if self.root: self.root.after(0, lambda: self.status_var.set(status))
    def start_script_event(self, event=None):
        if self.is_script_running.is_set(): messagebox.showwarning("Busy", "A script is already running in this window."); return
        script = self.editor.get("1.0", "end-1c") # Use end-1c to avoid trailing newline
        if not script: messagebox.showinfo("Empty Script", "The script is empty."); return
        self.is_script_running.set()
        thread = threading.Thread(target=self.run_script_in_thread, args=(script,), daemon=True); thread.start()
    def run_script_in_thread(self, script):
        try: self.engine.run_script(script)
        finally: self.is_script_running.clear()
    def stop_script_event(self, event=None):
        if self.is_script_running.is_set(): self.engine.stop_script()
        else: self.update_status("No script is currently running.")

if __name__ == "__main__":
    root = tk.Tk()
    file_to_open = sys.argv[1] if len(sys.argv) > 1 else None
    app = AutomationApp(root, file_to_open=file_to_open)
    root.mainloop()