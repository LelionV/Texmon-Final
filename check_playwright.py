import sys
import platform
import os

print("Python:", sys.version)
print("Executable:", sys.executable)
print("Platform:", platform.platform())
print("System:", platform.system())

try:
    import playwright
    print("Playwright:", playwright.__file__)
    print("Version:", playwright.__version__)
except Exception as e:
    print("Import error:", e)

try:
    with open("/etc/os-release") as f:
        print("Runtime OS:", f.read())
except Exception:
    print("OS release information unavailable")
