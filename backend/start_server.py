"""Start backend server in background, wait, then verify."""
import subprocess
import sys
import time
import urllib.request
import json
import os

os.chdir(os.path.dirname(__file__) or '.')

# Clear all pyc
for root, dirs, files in os.walk('.'):
    if '__pycache__' in dirs:
        import shutil
        shutil.rmtree(os.path.join(root, '__pycache__'), ignore_errors=True)

proc = subprocess.Popen(
    [sys.executable, '-B', '-m', 'uvicorn', 'main:app', '--host', '0.0.0.0', '--port', '8000'],
    cwd='.'
)
print(f"Server started with PID {proc.pid}")

for i in range(20):
    time.sleep(1)
    try:
        resp = urllib.request.urlopen('http://localhost:8000/api/health', timeout=2)
        data = json.loads(resp.read())
        print(f"Health check OK after {i+1}s: {data.get('qa_model', {}).get('available')}")
        break
    except Exception:
        pass
else:
    print("Server failed to start within 20s")
    proc.kill()
    sys.exit(1)

# Run quick test
try:
    resp = urllib.request.urlopen('http://localhost:8000/api/health', timeout=5)
    data = json.loads(resp.read())
    print(f"Final health: {json.dumps(data, indent=2)}")
except Exception as e:
    print(f"Health check failed: {e}")
