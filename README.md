# Nexus Automation Studio

Nexus Automation Studio is a powerful, user-friendly desktop application for creating and running automation scripts on Windows. Built with Python, it offers a complete Integrated Development Environment (IDE) for visual automation.

Whether you're automating game sequences, data entry, or system checks, Nexus provides the tools you need in a clean, modern interface.

---

## 🚀 Features

- **Modern IDE Interface**: Clean tabbed layout with script explorer, code editor, command panel, and output console.
- **Syntax Highlighting & Line Numbers**: Color-coded scripts for better readability and debugging.
- **Script Management**: Built-in file explorer for managing scripts and folders.
- **Rich Command Set**: 30+ commands for mouse/keyboard control, OCR, image/text detection, logic, loops, and more.
- **Interactive Command Insertion**: Capture screen regions and generate command syntax automatically.
- **Global & Customizable Hotkeys**: Control automation even when the app isn't in focus.
- **Macro Recorder**: Record and reuse mouse and keyboard actions.
- **Standalone & Portable**: Bundle as a single `.exe` file with no installation required.

---

## 🛠️ Project Setup Guide

### ✅ Prerequisites

- Python 3.10+
- Tesseract OCR

### 📦 Step-by-Step Setup

1. **Clone the Repository**

   ```bash
   git clone https://your-repository-url.git
   cd nexus-automation-studio
Set Up Virtual Environment (Recommended)

bash
Copy
Edit
python -m venv venv

# Activate on Windows
.\venv\Scripts\activate

# On macOS/Linux
# source venv/bin/activate
Install Dependencies

bash
Copy
Edit
pip install -r requirements.txt
Set Up Tesseract OCR

Download Tesseract OCR for Windows from the UB Mannheim repo.

Install it temporarily (e.g., C:\Tesseract-Temp).

Create a folder tesseract/ inside your project root.

Copy:

tesseract.exe

tessdata/ folder (must contain eng.traineddata)

css
Copy
Edit
nexus-automation-studio/
├── main.py
├── ...
└── tesseract/
    ├── tesseract.exe
    └── tessdata/
        └── eng.traineddata
Run the App

bash
Copy
Edit
python main.py
📘 User Guide
🧭 Interface Overview
Script Explorer: Open/rename/delete scripts or macros. Set workspace via "Open Folder".

Script Editor: Write scripts with syntax highlighting and line numbers.

Output Console: See logs, actions, and errors during execution.

Command Panel: Click to insert command syntax and see usage examples.

⌨️ Hotkeys
Action	Shortcut
Start Script	F5
Stop Script	F6
Stop Macro Recording	Ctrl+Shift+F12
Save	Ctrl+S
Save As	Ctrl+Shift+S
New Window	Ctrl+N
Open Workspace	Ctrl+O
Close Window	Ctrl+Q / Ctrl+W

🧾 Writing Scripts
Commands: One command per line, executed top to bottom.

Comments: Start with # for non-executable notes.

Indentation: Optional, for readability.

Variables: var my_count 10 → use as $my_count.

Logic: Use if_..., else, and endif.

🎥 Macro Recorder
Go to Settings → Record Macro.

Perform actions (mouse/keyboard).

Press Ctrl+Shift+F12 to stop.

Choose:

Save to File → as .json

Insert Directly → script format

Cancel

📦 Creating a Standalone .exe
1. Install PyInstaller
bash
Copy
Edit
pip install pyinstaller
2. Prepare build.spec
Ensure your build.spec file looks like this:

python
Copy
Edit
# -*- mode: python ; coding: utf-8 -*-
a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[('tesseract', 'tesseract')],
    hiddenimports=['pynput.keyboard._win32', 'pynput.mouse._win32', 'sv_ttk'],
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=None
)
pyz = PYZ(a.pure, a.zipped_data, cipher=None)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='NexusAutomationStudio',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    icon='icon.ico'  # Remove or replace if icon.ico is missing
)
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='NexusAutomationStudio'
)
3. Build the Executable
bash
Copy
Edit
pyinstaller build.spec
4. Distribute
Go to dist/NexusAutomationStudio/

Find NexusAutomationStudio.exe

You can zip this folder and share it. No Python installation required.

📸 Screenshot
<!-- You can upload a screenshot to Imgur and replace the link below -->

📄 License
Add your license info here if applicable.

yaml
Copy
Edit

---

Let me know if you'd like me to auto-generate the `requirements.txt` or help set up GitHub Actions for packaging!