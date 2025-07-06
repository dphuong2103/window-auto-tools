# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[
        # Bundle the entire Tesseract folder
        ('tesseract', 'tesseract')
    ],
    hiddenimports=[
        # Add libraries that PyInstaller might miss
        'pynput.keyboard._win32', 
        'pynput.mouse._win32',
        'sv_ttk'
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='NexusAutomationStudio', # This will be the name of your .exe file
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False, # IMPORTANT: Set to False for a GUI application
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='icon.ico' # Change this to your icon file name, or remove if you don't have one
)
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='NexusAutomationStudio' # This will be the name of the output folder
)