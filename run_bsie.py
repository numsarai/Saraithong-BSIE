import os, sys

project = r"G:\BSIE\Saraithong-BSIE"
os.chdir(project)
sys.path.insert(0, project)

import uvicorn
uvicorn.run("app:app", host="127.0.0.1", port=5001, log_level="info")
