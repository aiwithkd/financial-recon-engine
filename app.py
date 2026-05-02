import sys
import os
from pathlib import Path

# Ensure project root is always on sys.path regardless of how Streamlit launches
ROOT = Path(os.path.abspath(__file__)).parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Also set working directory to project root so relative paths resolve
os.chdir(ROOT)

# Import and execute the actual app module
exec(open(ROOT / "src" / "ui" / "app.py").read())
