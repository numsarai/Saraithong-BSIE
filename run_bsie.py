"""Quick-start script for BSIE development server."""
import os
import sys
from pathlib import Path

project = Path(__file__).parent
os.chdir(project)
sys.path.insert(0, str(project))

import uvicorn
uvicorn.run("app:app", host="127.0.0.1", port=5001, log_level="info")
