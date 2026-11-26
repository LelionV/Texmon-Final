
import os
import sys
import subprocess

print("Python:", sys.executable)
print("HOME:", os.environ.get("HOME"))

result = subprocess.run(
    [sys.executable, "-m", "playwright", "install", "chromium"],
    capture_output=True,
    text=True
)

print("INSTALL EXIT CODE:", result.returncode)
print("OUTPUT:", result.stdout)
print("ERROR:", result.stderr)

sys.exit(result.returncode)
