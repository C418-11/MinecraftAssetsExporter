./.venv/Scripts/activate.ps1
# app.py + tk
nuitka --onefile --enable-plugin=tk-inter --windows-console-mode=attach app.py
