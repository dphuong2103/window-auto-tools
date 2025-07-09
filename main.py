import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog
import os, sys, threading, subprocess, logging, re, json, shutil, sv_ttk
from key_binder import KeyBinder
from script_engine import ScriptEngine, ScriptExitException
from script_manager import ScriptManager
from macro_recorder import MacroRecorder
from pynput import mouse
import pyautogui

class Tooltip:
    def __init__(self, widget, title, example=""):
        self.widget = widget; self.title = title; self.example = example; self.tip_window = None
        self.widget.bind("<Enter>", self.show_tip); self.widget.bind("<Leave>", self.hide_tip)
    def show_tip(self, event=None):
        if self.tip_window or not self.title: return
        x, y, _, _ = self.widget.bbox("insert"); x += self.widget.winfo_rootx() + 25; y += self.widget.winfo_rooty() + 25
        self.tip_window = tw = tk.Toplevel(self.widget); tw.wm_overrideredirect(True); tw.wm_geometry(f"+{x}+{y}")
        frame = ttk.Frame(tw, borderwidth=1, relief="solid", padding=5); frame.pack()
        ttk.Label(frame, text=self.title, font=("Segoe UI", 9, "bold")).pack(anchor="w")
        if self.example: ttk.Label(frame, text=self.example, font=("Consolas", 9), relief="groove", padding=5).pack(anchor="w", pady=(5,0), fill="x")
    def hide_tip(self, event=None):
        if self.tip_window: self.tip_window.destroy(); self.tip_window = None
class BaseOverlay(tk.Toplevel):
    def __init__(self, root, on_complete):
        super().__init__(root); self.on_complete = on_complete; self.root = root
        self.wm_attributes("-alpha", 0.3); self.overrideredirect(True); self.geometry(f"{self.winfo_screenwidth()}x{self.winfo_screenheight()}+0+0")
        self.focus_force(); self.grab_set(); self.bind("<Escape>", self.cancel)
    def cancel(self, event=None): self.destroy(); self.root.deiconify(); self.root.lift(); self.on_complete(None)
class PointSelectorOverlay(BaseOverlay):
    def __init__(self, root, on_complete): super().__init__(root, on_complete); self.config(cursor="crosshair"); self.bind("<ButtonRelease-1>", self.on_click)
    def on_click(self, event): coords = (event.x_root, event.y_root); self.destroy(); self.root.deiconify(); self.root.lift(); self.on_complete(coords)
class RegionSelectorOverlay(BaseOverlay):
    def __init__(self, root, on_complete):
        super().__init__(root, on_complete); self.start_x = 0; self.start_y = 0; self.rect = None
        self.canvas = tk.Canvas(self, cursor="crosshair", bg="black"); self.canvas.pack(fill="both", expand=True)
        self.canvas.bind("<ButtonPress-1>", self.on_press); self.canvas.bind("<B1-Motion>", self.on_drag); self.canvas.bind("<ButtonRelease-1>", self.on_release)
    def on_press(self, event): self.start_x = event.x_root; self.start_y = event.y_root; self.rect = self.canvas.create_rectangle(self.start_x, self.start_y, self.start_x, self.start_y, outline='red', width=2)
    def on_drag(self, event):
        if self.rect: self.canvas.coords(self.rect, self.start_x, self.start_y, event.x_root, event.y_root)
    def on_release(self, event):
        end_x, end_y = event.x_root, event.y_root; x1, y1 = min(self.start_x, end_x), min(self.start_y, end_y); x2, y2 = max(self.start_x, end_x), max(self.start_y, end_y)
        self.destroy(); self.root.deiconify(); self.root.lift(); self.on_complete((x1, y1, x2, y2))
class TextLineNumbers(tk.Canvas):
    def __init__(self, *args, **kwargs): tk.Canvas.__init__(self, *args, **kwargs); self.textwidget = None
    def attach(self, text_widget): self.textwidget = text_widget
    def redraw(self, *args):
        self.delete("all"); i = self.textwidget.index("@0,0")
        while True :
            dline= self.textwidget.dlineinfo(i);
            if dline is None: break
            y = dline[1]; linenum = str(i).split(".")[0]
            self.create_text(2, y, anchor="nw", text=linenum, fill="#606366", font=("Segoe UI", 9)); i = self.textwidget.index("%s+1line" % i)
class SyntaxHighlighter:
    def __init__(self, text_widget):
        self.text = text_widget; self.text.bind("<<Modified>>", self.on_text_modified, add=True)
        self.patterns = { 'comment': r'#.*', 'command': r'\b(click|double_click|right_click|move_to|scroll|click_and_drag|wait|delay|loop|endloop|break|if|endif|eval|var|script|popup|log|select_window|key|type|playback|get_text|sound|screenshot|exit|mouse_pos)\w*\b', 'string': r'\"[^\"\n]*\"', 'number': r'\b-?\d+(\.\d+)?\b', 'operator': r'[\+\-\*/<>=!]=?', 'variable': r'\$\w+' }
        self.text.tag_configure("command", foreground="#0000ff"); self.text.tag_configure("string", foreground="#A31515"); self.text.tag_configure("comment", foreground="#008000"); self.text.tag_configure("number", foreground="#881391"); self.text.tag_configure("operator", foreground="#881391"); self.text.tag_configure("variable", foreground="#001080", font=("Segoe UI", 10, "italic"))
    def on_text_modified(self, event=None):
        if self.text.edit_modified(): self.highlight_all(); self.text.edit_modified(False)
    def highlight_all(self):
        for tag in self.text.tag_names():
            if tag != "sel": self.text.tag_remove(tag, "1.0", "end")
        for tag, pattern in self.patterns.items(): self.apply_tag(tag, pattern)
    def apply_tag(self, tag, pattern):
        content = self.text.get("1.0", "end")
        for match in re.finditer(pattern, content, re.IGNORECASE):
            start, end = match.span(); self.text.tag_add(tag, f"1.0 + {start} chars", f"1.0 + {end} chars")

class PixelColorDialog(tk.Toplevel):
    def __init__(self, parent, x, y, initial_color, callback):
        super().__init__(parent); self.callback = callback
        self.title("Pixel Condition"); self.transient(parent); self.grab_set()
        
        frame = ttk.Frame(self, padding=15); frame.pack(expand=True, fill="both")
        
        ttk.Label(frame, text=f"Pixel at ({x}, {y})", font=("Segoe UI", 10, "bold")).grid(row=0, columnspan=2, pady=(0,10))
        
        self.r_var = tk.StringVar(value=str(initial_color[0])); self.g_var = tk.StringVar(value=str(initial_color[1])); self.b_var = tk.StringVar(value=str(initial_color[2])); self.tol_var = tk.StringVar(value="10")
        
        ttk.Label(frame, text="Red (R):").grid(row=1, column=0, sticky="w", pady=2); ttk.Entry(frame, textvariable=self.r_var).grid(row=1, column=1, sticky="ew")
        ttk.Label(frame, text="Green (G):").grid(row=2, column=0, sticky="w", pady=2); ttk.Entry(frame, textvariable=self.g_var).grid(row=2, column=1, sticky="ew")
        ttk.Label(frame, text="Blue (B):").grid(row=3, column=0, sticky="w", pady=2); ttk.Entry(frame, textvariable=self.b_var).grid(row=3, column=1, sticky="ew")
        ttk.Label(frame, text="Tolerance:").grid(row=4, column=0, sticky="w", pady=2); ttk.Entry(frame, textvariable=self.tol_var).grid(row=4, column=1, sticky="ew")
        
        btn_frame = ttk.Frame(frame); btn_frame.grid(row=5, columnspan=2, pady=(10,0))
        ttk.Button(btn_frame, text="Confirm", command=lambda: self.on_confirm(x, y), style="Accent.TButton").pack(side="left", padx=5)
        ttk.Button(btn_frame, text="Cancel", command=self.destroy).pack(side="left", padx=5)

    def on_confirm(self, x, y):
        try:
            r, g, b, tol = self.r_var.get(), self.g_var.get(), self.b_var.get(), self.tol_var.get()
            self.callback(f"if_pixel_matches {x} {y} {r} {g} {b} {tol}\n")
            self.destroy()
        except Exception as e:
            messagebox.showerror("Invalid Input", str(e), parent=self)

class AutomationApp:
    def __init__(self, root, file_to_open=None):
        self.root = root; sv_ttk.set_theme("light"); self.root.title("Nexus Automation Studio"); self.root.geometry("1200x800")
        self.selection_mode = None; self.current_command = None; self.drag_start_pos = None; self.mouse_listener = None
        self.is_script_running = threading.Event(); self.workspace_dir = None
        self.recorder = MacroRecorder(); self.is_recording = False
        
        self.setup_gui(); self.setup_logging(); self.setup_keybinds()
        self.script_manager = ScriptManager(); self.engine = ScriptEngine(self.update_output, self.update_status, self.show_popup)
        if file_to_open: self.load_script_from_path(file_to_open)

    def setup_logging(self): logging.basicConfig(filename='automation.log', level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s'); self.logger = logging.getLogger()
    def show_popup(self, message): self.root.after(0, lambda: messagebox.showinfo("Script Message", message))
    def setup_keybinds(self):
        self.keybinder = KeyBinder(); self.keybinder.load_keybinds()
        self.keybinder.set_callbacks(self.start_script_event, self.stop_script_event, self.toggle_macro_recorder)
        self.keybinder.start(); self.root.protocol("WM_DELETE_WINDOW", self.quit_app)
    def setup_gui(self):
        self.main_frame = ttk.Frame(self.root, padding=10); self.main_frame.pack(fill="both", expand=True)
        self.main_frame.rowconfigure(0, weight=1); self.main_frame.columnconfigure(1, weight=1)
        explorer_frame = ttk.Frame(self.main_frame, padding=5); explorer_frame.grid(row=0, column=0, sticky="ns"); explorer_frame.rowconfigure(1, weight=1)
        explorer_toolbar = ttk.Frame(explorer_frame); explorer_toolbar.grid(row=0, column=0, sticky="ew", pady=5)
        ttk.Button(explorer_toolbar, text="📂 Open Folder", command=self.open_workspace).pack(side="left")
        ttk.Button(explorer_toolbar, text="➕ New Script", command=self.create_new_file_from_button).pack(side="left", padx=5)
        ttk.Button(explorer_toolbar, text="🔃 Refresh", command=self.populate_explorer).pack(side="left")
        self.tree = ttk.Treeview(explorer_frame, selectmode="browse"); self.tree.grid(row=1, column=0, sticky="ns")
        tree_scroll = ttk.Scrollbar(explorer_frame, orient="vertical", command=self.tree.yview); tree_scroll.grid(row=1, column=1, sticky="ns")
        self.tree.configure(yscrollcommand=tree_scroll.set); self.tree.bind("<Double-1>", self.on_tree_double_click); self.tree.bind("<Button-3>", self.on_tree_right_click)
        main_paned_window = ttk.PanedWindow(self.main_frame, orient=tk.HORIZONTAL); main_paned_window.grid(row=0, column=1, sticky="nsew", padx=10)
        editor_console_pane = ttk.PanedWindow(main_paned_window, orient=tk.VERTICAL)
        editor_outer_frame = ttk.LabelFrame(editor_console_pane, text="Script Editor", padding=5)
        editor_outer_frame.columnconfigure(1, weight=1); editor_outer_frame.rowconfigure(0, weight=1)
        self.linenumbers = TextLineNumbers(editor_outer_frame, width=40, bg="#f5f5f5"); self.linenumbers.grid(row=0, column=0, sticky="ns")
        self.editor = tk.Text(editor_outer_frame, height=20, font=("Consolas", 11), undo=True, wrap="word", relief="flat"); self.editor.grid(row=0, column=1, sticky="nsew")
        editor_scrollbar = ttk.Scrollbar(editor_outer_frame, orient=tk.VERTICAL, command=self.editor.yview); editor_scrollbar.grid(row=0, column=2, sticky="ns")
        self.linenumbers.attach(self.editor); self.highlighter = SyntaxHighlighter(self.editor)
        self.editor['yscrollcommand'] = lambda *args: (editor_scrollbar.set(*args), self.linenumbers.redraw())
        self.editor.bind("<<Modified>>", lambda e: self.linenumbers.redraw(), add=True)
        editor_console_pane.add(editor_outer_frame, weight=3)
        output_frame = ttk.LabelFrame(editor_console_pane, text="Output", padding=5); output_frame.columnconfigure(0, weight=1); output_frame.rowconfigure(0, weight=1)
        self.output = tk.Text(output_frame, height=10, state='disabled', font=("Consolas", 10), wrap="word", relief="flat"); self.output.grid(row=0, column=0, sticky="nsew")
        output_scrollbar = ttk.Scrollbar(output_frame, orient=tk.VERTICAL, command=self.output.yview); output_scrollbar.grid(row=0, column=1, sticky="ns")
        self.output['yscrollcommand'] = output_scrollbar.set; editor_console_pane.add(output_frame, weight=1)
        main_paned_window.add(editor_console_pane, weight=3)
        cmd_outer_frame = ttk.LabelFrame(main_paned_window, text="Commands", padding=5); cmd_outer_frame.rowconfigure(0, weight=1); cmd_outer_frame.columnconfigure(0, weight=1)
        cmd_canvas = tk.Canvas(cmd_outer_frame, borderwidth=0, highlightthickness=0); cmd_scrollbar = ttk.Scrollbar(cmd_outer_frame, orient="vertical", command=cmd_canvas.yview)
        self.command_panel = ttk.Frame(cmd_canvas)
        cmd_canvas.configure(yscrollcommand=cmd_scrollbar.set); cmd_scrollbar.pack(side="right", fill="y"); cmd_canvas.pack(side="left", fill="both", expand=True)
        canvas_frame_id = cmd_canvas.create_window((0, 0), window=self.command_panel, anchor="nw")
        self.command_panel.bind("<Configure>", lambda e: cmd_canvas.configure(scrollregion=cmd_canvas.bbox("all")))
        cmd_canvas.bind("<Configure>", lambda e: cmd_canvas.itemconfig(canvas_frame_id, width=e.width))
        self.root.bind_all("<MouseWheel>", lambda e: self._on_mousewheel(e, cmd_canvas), add=True)
        main_paned_window.add(cmd_outer_frame, weight=1); self.populate_command_panel()
        self.status_var = tk.StringVar(value="Ready"); status_bar = ttk.Label(self.root, textvariable=self.status_var, relief=tk.SUNKEN, anchor='w', padding=5); status_bar.pack(side="bottom", fill="x")
        menubar = tk.Menu(self.root); filemenu = tk.Menu(menubar, tearoff=0); settingsmenu = tk.Menu(menubar, tearoff=0)
        filemenu.add_command(label="New Window", accelerator="Ctrl+N", command=lambda: subprocess.Popen([sys.executable, sys.argv[0]]))
        filemenu.add_command(label="Open Folder...", accelerator="Ctrl+O", command=self.open_workspace)
        filemenu.add_separator(); filemenu.add_command(label="Save", accelerator="Ctrl+S", command=self.save_script); filemenu.add_command(label="Save As...", accelerator="Ctrl+Shift+S", command=self.save_script_as)
        filemenu.add_separator(); filemenu.add_command(label="Exit", accelerator="Ctrl+Q", command=self.quit_app)
        settingsmenu.add_command(label="Configure Keybinds...", command=self.open_keybind_settings)
        settingsmenu.add_command(label="Record Macro...", command=self.toggle_macro_recorder)
        menubar.add_cascade(label="File", menu=filemenu); menubar.add_cascade(label="Settings", menu=settingsmenu); self.root.config(menu=menubar)
        self.root.bind_all("<Control-n>", lambda e: subprocess.Popen([sys.executable, sys.argv[0]])); self.root.bind_all("<Control-o>", lambda e: self.open_workspace()); self.root.bind_all("<Control-s>", lambda e: self.save_script()); self.root.bind_all("<Control-S>", lambda e: self.save_script_as()); self.root.bind_all("<Control-q>", lambda e: self.quit_app()); self.root.bind_all("<Control-w>", lambda e: self.quit_app())
    
    def _on_mousewheel(self, event, canvas):
        x, y = self.root.winfo_pointerxy(); widget = self.root.winfo_containing(x, y)
        if widget is canvas or str(widget).startswith(str(canvas)): canvas.yview_scroll(int(-1*(event.delta/120)), "units")
    def populate_command_panel(self):
        commands = { "Click": [('click_location', 'Click at a specific coordinate', 'click_location 100 200'), ('click_text', 'Find and click on visible text', 'click_text "Login"'), ('click_image', 'Find and click an image on screen', 'click_image "images/button.png"')], "Double-Click": [('double_click_location', 'Double-click at a coordinate', 'double_click_location 100 200'), ('double_click_text', 'Find and double-click text', 'double_click_text "My Computer"'), ('double_click_image', 'Find and double-click an image', 'double_click_image "images/icon.png"')], "Other Mouse": [('right_click_location', 'Right-click at a coordinate', 'right_click_location 100 200'), ('move_to', 'Move the mouse without clicking', 'move_to 500 500'), ('click_and_drag', 'Drag mouse from start to end point', 'click_and_drag 100 100 500 500 1.5'), ('scroll', 'Scroll the mouse wheel', 'scroll -10')], "Variables & Logic": [('var', 'Assign a value to a variable', 'var my_var 10'), ('eval', 'Perform math and assign', 'eval result = $my_var * 2'), ('if_eval', 'Check a condition using variables', 'if_eval $result > 15')], "Conditional (IF)": [('if_pixel_matches', 'IF a pixel matches a color', 'if_pixel_matches 100 200 255 0 0 10'), ('if_text_region', 'IF text is in a region', 'if_text_region "Success" 100 100 300 200'), ('if_text_screen', 'IF text is on screen', 'if_text_screen "Welcome"'), ('if_image_screen', 'IF image is on screen', 'if_image_screen "ok.png"'), ('if_not_image_screen', 'IF NOT image is on screen', 'if_not_image_screen "error.png"'), ('else', 'ELSE block for a preceding IF', 'else'), ('endif', 'Marks the end of an IF/ELSE block', 'endif')], "Loops & Control Flow": [('loop', 'Repeat a block of code N times', 'loop 5'), ('endloop', 'Marks the end of a LOOP block', 'endloop'), ('break', 'Exit the current loop', 'break'), ('exit', 'Terminate the entire script', 'exit')], "Data & Text": [('get_text_region', 'Get text from a region into a variable', 'get_text_region my_variable 10 20 30 40'), ('mouse_pos', 'Get mouse coords into variables', 'mouse_pos x_coord y_coord')], "System & Media": [('sound', 'Play a sound file (.wav, .mp3)', 'sound "path/to/alert.mp3"'), ('screenshot', 'Save a screenshot to a file', 'screenshot "capture.png" 10 20 30 40')], "Flow & Logging": [('script', 'Run another script file', 'script "path/to/sub.txt"'), ('playback', 'Playback a recorded macro', 'playback "login.json"'), ('popup', 'Show a message box to the user', 'popup "Task Complete!"'), ('log', 'Write a message to the output console', 'log "Starting Step 2..."')], "Timing": [('wait', 'Pause the script for seconds', 'wait 2.5'), ('delay', 'Alias for wait', 'delay 1')], "Window & Keyboard": [('select_window', 'Bring a window to the foreground', 'select_window "Notepad"'), ('key', 'Press a special keyboard key', 'key enter'), ('type', 'Type a string of text', 'type "Hello, World!"')] }
        row = 0
        for category, cmds in commands.items():
            ttk.Label(self.command_panel, text=category, font=("Segoe UI", 10, "bold")).grid(row=row, column=0, sticky="w", pady=(10, 2), padx=5); row += 1
            for cmd_id, desc, example in cmds: btn = ttk.Button(self.command_panel, text=cmd_id, command=lambda c=cmd_id: self.insert_command(c), style="Accent.TButton"); btn.grid(row=row, column=0, sticky="ew", pady=1, padx=5); Tooltip(btn, desc, example); row += 1

    def open_keybind_settings(self):
        dialog = tk.Toplevel(self.root); dialog.title("Configure Keybinds"); dialog.transient(self.root); dialog.grab_set()
        ttk.Label(dialog, text="Start Script:").grid(row=0, column=0, padx=10, pady=10)
        start_var = tk.StringVar(value=self.keybinder.keybinds.get('start_script')); ttk.Entry(dialog, textvariable=start_var, state="readonly").grid(row=0, column=1, padx=10, pady=10)
        ttk.Label(dialog, text="Stop Script:").grid(row=1, column=0, padx=10, pady=10)
        stop_var = tk.StringVar(value=self.keybinder.keybinds.get('stop_script')); ttk.Entry(dialog, textvariable=stop_var, state="readonly").grid(row=1, column=1, padx=10, pady=10)
        ttk.Label(dialog, text="Stop Macro Recording:").grid(row=2, column=0, padx=10, pady=10)
        macro_var = tk.StringVar(value=self.keybinder.keybinds.get('stop_macro')); ttk.Entry(dialog, textvariable=macro_var, state="readonly").grid(row=2, column=1, padx=10, pady=10)
        def set_key(var):
            self.keybinder.stop(); captured = self.keybinder.capture_key(self.root);
            if captured: var.set(captured)
            self.keybinder.start()
        ttk.Button(dialog, text="Set", command=lambda: set_key(start_var)).grid(row=0, column=2)
        ttk.Button(dialog, text="Set", command=lambda: set_key(stop_var)).grid(row=1, column=2)
        ttk.Button(dialog, text="Set", command=lambda: set_key(macro_var)).grid(row=2, column=2)
        def save_and_close():
            self.keybinder.keybinds['start_script'] = start_var.get(); self.keybinder.keybinds['stop_script'] = stop_var.get(); self.keybinder.keybinds['stop_macro'] = macro_var.get()
            self.keybinder.save_keybinds(); self.keybinder.stop(); self.keybinder.start(); dialog.destroy()
        ttk.Button(dialog, text="Save and Close", command=save_and_close, style="Accent.TButton").grid(row=3, columnspan=3, pady=10)

    # --- SCRIPT EXPLORER METHODS ---
    def open_workspace(self):
        dir_path = filedialog.askdirectory(title="Select Workspace Folder");
        if dir_path: self.workspace_dir = dir_path; self.populate_explorer()
    def populate_explorer(self, event=None):
        if not self.workspace_dir: return
        for i in self.tree.get_children(): self.tree.delete(i)
        self.root.title(f"Nexus Automation Studio - {os.path.basename(self.workspace_dir)}")
        def process_directory(parent, path):
            for p in sorted(os.listdir(path)):
                abs_path = os.path.join(path, p); is_dir = os.path.isdir(abs_path)
                node_text = f"📁 {p}" if is_dir else f"📜 {p}"
                if not is_dir and not (p.endswith('.txt') or p.endswith('.json')): continue
                node = self.tree.insert(parent, "end", text=node_text, open=False, values=[abs_path])
                if is_dir: process_directory(node, abs_path)
        process_directory("", self.workspace_dir)
    def on_tree_double_click(self, event):
        item_id = self.tree.focus();
        if not item_id: return
        file_path = self.tree.item(item_id, "values")[0]
        if os.path.isfile(file_path) and file_path.endswith('.txt'): self.load_script_from_path(file_path)
    def on_tree_right_click(self, event):
        item_id = self.tree.identify_row(event.y)
        if not item_id: parent_dir = self.workspace_dir
        else: self.tree.selection_set(item_id); path = self.tree.item(item_id, "values")[0]; parent_dir = path if os.path.isdir(path) else os.path.dirname(path)
        menu = tk.Menu(self.root, tearoff=0)
        if item_id and os.path.isfile(self.tree.item(item_id, "values")[0]):
             menu.add_command(label="Rename...", command=lambda: self.rename_tree_item(self.tree.item(item_id, "values")[0]))
             menu.add_command(label="Duplicate", command=lambda: self.duplicate_tree_item(self.tree.item(item_id, "values")[0]))
        menu.add_command(label="New Script...", command=lambda: self.create_new_file(parent_dir))
        menu.add_command(label="New Folder...", command=lambda: self.create_new_folder(parent_dir))
        if item_id: menu.add_separator(); menu.add_command(label="Delete", command=lambda: self.delete_tree_item(self.tree.item(item_id, "values")[0]))
        menu.post(event.x_root, event.y_root)
    def create_new_file(self, parent_dir):
        file_name = simpledialog.askstring("New Script", "Enter script name (without .txt):", parent=self.root)
        if file_name:
            file_path = os.path.join(parent_dir, f"{file_name}.txt")
            if not os.path.exists(file_path): open(file_path, 'w').close(); self.populate_explorer()
            else: messagebox.showerror("Error", "A file with that name already exists.")
    def create_new_file_from_button(self):
        if self.workspace_dir: self.create_new_file(self.workspace_dir)
        else: messagebox.showwarning("No Workspace", "Please open a folder first to set your workspace.")
    def create_new_folder(self, parent_dir):
        folder_name = simpledialog.askstring("New Folder", "Enter folder name:", parent=self.root)
        if folder_name:
            folder_path = os.path.join(parent_dir, folder_name)
            if not os.path.exists(folder_path): os.makedirs(folder_path); self.populate_explorer()
            else: messagebox.showerror("Error", "A folder with that name already exists.")
    def rename_tree_item(self, old_path):
        old_name = os.path.basename(old_path)
        new_name = simpledialog.askstring("Rename", "Enter new name:", initialvalue=old_name, parent=self.root)
        if new_name and new_name != old_name:
            new_path = os.path.join(os.path.dirname(old_path), new_name)
            try: os.rename(old_path, new_path); self.populate_explorer()
            except Exception as e: messagebox.showerror("Error", f"Could not rename: {e}")
    def duplicate_tree_item(self, old_path):
        base, ext = os.path.splitext(old_path)
        new_path = f"{base}_copy{ext}"
        try: shutil.copy2(old_path, new_path); self.populate_explorer()
        except Exception as e: messagebox.showerror("Error", f"Could not duplicate: {e}")
    def delete_tree_item(self, path):
        if messagebox.askokcancel("Delete", f"Are you sure you want to permanently delete '{os.path.basename(path)}'?"):
            try:
                if os.path.isdir(path): shutil.rmtree(path)
                else: os.remove(path)
                self.populate_explorer()
            except Exception as e: messagebox.showerror("Error", f"Could not delete: {e}")

    # --- SCRIPT EXECUTION & OTHER METHODS ---
    def load_script_from_path(self, file_path):
        try:
            script = self.script_manager.load_script(file_path); self.editor.delete("1.0", tk.END); self.editor.insert("1.0", script)
            self.editor.edit_modified(False); self.highlighter.highlight_all(); self.linenumbers.redraw()
            self.status_var.set(f"Opened: {os.path.relpath(file_path, self.workspace_dir or os.getcwd())}")
        except Exception as e: messagebox.showerror("Error", f"Failed to load script: {e}"); self.logger.error(f"Failed to load {file_path}: {e}")
    def save_script(self):
        if self.script_manager.current_file:
            try: self.script_manager.save_script(self.script_manager.current_file, self.editor.get("1.0", "end-1c")); self.update_status(f"Saved {os.path.basename(self.script_manager.current_file)}")
            except Exception as e: messagebox.showerror("Error", f"Failed to save script: {e}"); self.logger.error(f"Failed to save {self.script_manager.current_file}: {e}")
        else: self.save_script_as()
    def save_script_as(self):
        initial_dir = self.workspace_dir or os.getcwd()
        file_path = filedialog.asksaveasfilename(initialdir=initial_dir, defaultextension=".txt", filetypes=[("Text Files", "*.txt")])
        if file_path:
            try: self.script_manager.save_script(file_path, self.editor.get("1.0", "end-1c")); self.update_status(f"Saved to {os.path.basename(file_path)}")
            except Exception as e: messagebox.showerror("Error", f"Failed to save script: {e}"); self.logger.error(f"Failed to save {file_path}: {e}")
    def quit_app(self):
        self.keybinder.stop()
        if self.is_script_running.is_set():
            if messagebox.askokcancel("Quit", "A script is running. Quit anyway?"): self.stop_script_event(); self.root.destroy()
        else: self.root.destroy()
    
    # --- THIS FUNCTION IS FIXED ---
    def insert_command(self, command_id):
        self.cancel_selection(); self.current_command = command_id
        if command_id in ['click_location', 'double_click_location', 'right_click_location', 'move_to']:
            self.selection_mode = 'point'; self.status_var.set(f"Click a point on screen (Esc to cancel)"); self.root.iconify(); PointSelectorOverlay(self.root, self.finalize_point_selection)
        elif command_id == 'click_and_drag':
            self.selection_mode = 'drag_start'; self.status_var.set("Click the START point (Esc to cancel)"); self.start_pynput_listener()
        elif command_id == 'if_text_region':
            self.selection_mode = 'region'; self.status_var.set("Drag a region to check for text (Esc to cancel)"); self.root.iconify(); RegionSelectorOverlay(self.root, self.finalize_region_selection)
        elif command_id == 'get_text_region':
            var_name = simpledialog.askstring("Variable Name", "Enter variable name to store the text in:", parent=self.root)
            if var_name: self.current_command = f"get_text_region {var_name}"; self.selection_mode = 'region'; self.status_var.set("Drag a region to get text from (Esc to cancel)"); self.root.iconify(); RegionSelectorOverlay(self.root, self.finalize_get_text_region)
        elif command_id in ['click_image', 'double_click_image', 'if_image_screen', 'if_not_image_screen']:
            file_path = filedialog.askopenfilename(title="Select Image File", filetypes=[("Image files", "*.png *.jpg *.bmp")])
            if file_path: self.editor.insert(tk.INSERT, f"{command_id} \"{file_path}\"\n")
        elif command_id in ['click_text', 'double_click_text', 'if_text_screen']:
            text = simpledialog.askstring("Input", "Enter text to find on screen:", parent=self.root)
            if text: self.editor.insert(tk.INSERT, f"{command_id} \"{text}\"\n")
        elif command_id == 'script':
            file_path = filedialog.askopenfilename(title="Select Script File", filetypes=[("Text files", "*.txt")])
            if file_path: self.editor.insert(tk.INSERT, f"script \"{file_path}\"\n")
        elif command_id == 'playback':
            file_path = filedialog.askopenfilename(title="Select Macro File", filetypes=[("Macro files", "*.json")])
            if file_path: self.editor.insert(tk.INSERT, f"playback \"{file_path}\"\n")
        elif command_id == 'sound':
            file_path = filedialog.askopenfilename(title="Select Sound File", filetypes=[("Sound Files", "*.mp3 *.wav")])
            if file_path: self.editor.insert(tk.INSERT, f'sound "{file_path}"\n')
        elif command_id == 'screenshot':
            self.selection_mode = 'region'
            self.status_var.set("Drag a region to capture (Esc for fullscreen)"); self.root.iconify(); 
            RegionSelectorOverlay(self.root, self.finalize_screenshot_selection)
        elif command_id == 'if_pixel_matches':
            self.selection_mode = 'point'; self.status_var.set(f"Click a point on screen to sample pixel color (Esc to cancel)"); self.root.iconify(); 
            PointSelectorOverlay(self.root, self.finalize_pixel_selection)
        else:
            line_content_map = {'endloop': 'endloop\n', 'endif': 'endif\n', 'break': 'break\n', 'else': 'else\n', 'exit': 'exit\n', 'mouse_pos': 'mouse_pos x_var y_var\n'}
            line_content = line_content_map.get(command_id, f"{command_id} ")
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
    def finalize_get_text_region(self, region):
        if region:
            x1, y1, x2, y2 = region; self.editor.insert(tk.INSERT, f"{self.current_command} {x1} {y1} {x2} {y2}\n"); self.status_var.set("Region captured for get_text_region.")
        else: self.status_var.set("Region selection cancelled.")
        self.cancel_selection()
    def finalize_screenshot_selection(self, region):
        file_path = filedialog.asksaveasfilename(defaultextension=".png", filetypes=[("PNG files", "*.png"), ("All files", "*.*")])
        if file_path:
            if region:
                x1, y1, x2, y2 = region
                self.editor.insert(tk.INSERT, f'screenshot "{file_path}" {x1} {y1} {x2} {y2}\n')
            else: # Fullscreen if region selection was cancelled
                self.editor.insert(tk.INSERT, f'screenshot "{file_path}"\n')
            self.status_var.set("Screenshot command inserted.")
        else:
            self.status_var.set("Screenshot cancelled.")
        self.cancel_selection()
    def finalize_pixel_selection(self, coords):
        if coords:
            x, y = coords
            try:
                color = pyautogui.pixel(x, y)
                PixelColorDialog(self.root, x, y, color, lambda cmd: self.editor.insert(tk.INSERT, cmd))
            except Exception as e:
                messagebox.showerror("Error", f"Could not get pixel color: {e}")
        else:
            self.status_var.set("Pixel selection cancelled.")
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
        if self.is_script_running.is_set(): messagebox.showwarning("Busy", "A script is already running."); return
        script = self.editor.get("1.0", "end-1c");
        if not script: messagebox.showinfo("Empty Script", "The script is empty."); return
        self.root.iconify()
        self.is_script_running.set()
        thread = threading.Thread(target=self.run_script_in_thread, args=(script,), daemon=True); thread.start()
    def run_script_in_thread(self, script):
        try: 
            self.engine.run_script(script)
        except ScriptExitException: # Should already be handled in engine, but as a safeguard
             self.update_status("Stopped by exit command")
        finally:
            self.is_script_running.clear(); self.root.after(0, self.root.deiconify)
    def stop_script_event(self, event=None):
        if self.is_script_running.is_set(): self.engine.stop_script()
        else: self.update_status("No script is currently running.")
    def toggle_macro_recorder(self):
        if not self.is_recording:
            self.is_recording = True; self.recorder.start_recording()
            stop_key = self.keybinder.keybinds.get('stop_macro', 'the configured hotkey')
            self.status_var.set(f"🔴 Macro Recording... Press {stop_key.upper()} to stop.")
            self.root.iconify()
        else:
            self.is_recording = False; events = self.recorder.stop_recording()
            self.root.deiconify()
            self.status_var.set("Macro recording stopped.")
            self.process_recorded_macro(events)
    def process_recorded_macro(self, events):
        if not events: messagebox.showinfo("Macro Recorder", "No actions were recorded."); return
        save_type = messagebox.askyesnocancel("Save Macro", "Macro recording finished.\n\nYes = Save to a .json file (for playback)\nNo = Insert commands directly into script")
        if save_type is None: return
        if save_type:
            file_path = filedialog.asksaveasfilename(defaultextension=".json", filetypes=[("JSON files", "*.json")])
            if file_path:
                with open(file_path, 'w') as f: json.dump(events, f, indent=4)
                messagebox.showinfo("Success", f"Macro saved to {os.path.basename(file_path)}"); self.editor.insert(tk.INSERT, f'# Play back recorded macro\nplayback "{file_path}"\n')
        else:
            script_text = "\n# --- Start of recorded macro ---\n"
            for event in events:
                if event['type'] == 'wait': script_text += f"wait {event['duration']}\n"
                elif event['type'] in ['click_location', 'double_click_location', 'right_click_location']: script_text += f"{event['type']} {event['x']} {event['y']}\n"
                elif event['type'] == 'type': script_text += f"type \"{event['text']}\"\n"
                elif event['type'] == 'key': script_text += f"key {event['key_name']}\n"
            script_text += "# --- End of recorded macro ---\n"
            self.editor.insert(tk.INSERT, script_text)

if __name__ == "__main__":
    root = tk.Tk()
    file_to_open = sys.argv[1] if len(sys.argv) > 1 else None
    app = AutomationApp(root, file_to_open=file_to_open)
    root.mainloop()