import os
import subprocess
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser_path = p.chromium.executable_path

print("Chromium:", browser_path)

result = subprocess.run(
    ["ldd", browser_path],
    capture_output=True,
    text=True
)

print("\nMISSING LIBRARIES:")
missing = [
    line.strip()
    for line in result.stdout.splitlines()
    if "not found" in line
]

print("\n".join(missing) if missing else "None")

print("\nFULL LDD OUTPUT:")
print(result.stdout)
