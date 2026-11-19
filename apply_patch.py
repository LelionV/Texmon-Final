
import os
import urllib.request
import re

PATCH_URL = (
    "https://raw.githubusercontent.com/"
    "LelionV/Texmon-Final/main/texmon-final-fixes.patch"
)

PATCH_FILE = "/app/texmon-final-fixes.patch"
BASE_DIR = "/app"

# Download patch
if not os.path.exists(PATCH_FILE):
    urllib.request.urlretrieve(PATCH_URL, PATCH_FILE)

print("Patch downloaded:", os.path.getsize(PATCH_FILE), "bytes")

with open(PATCH_FILE, "r", encoding="utf-8") as f:
    patch = f.read()

# Parse and apply unified diff
sections = re.split(r"(?=^diff --git )", patch, flags=re.MULTILINE)

for section in sections:
    if not section.startswith("diff --git "):
        continue

    match = re.search(
        r"^diff --git a/(.*?) b/(.*?)$",
        section,
        re.MULTILINE
    )

    if not match:
        continue

    old_path, new_path = match.groups()
    target = os.path.normpath(os.path.join(BASE_DIR, new_path))

    if not target.startswith(BASE_DIR + os.sep):
        raise ValueError("Unsafe patch path")

    if not os.path.isfile(target):
        print("SKIPPED (file missing):", new_path)
        continue

    with open(target, "r", encoding="utf-8") as f:
        original = f.read()

    hunks = re.split(r"(?=^@@ )", section, flags=re.MULTILINE)[1:]

    updated = original
    for hunk in hunks:
        lines = hunk.splitlines()
        old_lines = []
        new_lines = []

        for line in lines[1:]:
            if line.startswith("\\ No newline"):
                continue
            if line.startswith(" "):
                old_lines.append(line[1:])
                new_lines.append(line[1:])
            elif line.startswith("-"):
                old_lines.append(line[1:])
            elif line.startswith("+"):
                new_lines.append(line[1:])

        old_text = "\n".join(old_lines)
        new_text = "\n".join(new_lines)

        if old_text and old_text in updated:
            updated = updated.replace(old_text, new_text, 1)
        else:
            raise RuntimeError(
                "Patch context mismatch in " + new_path
            )

    with open(target, "w", encoding="utf-8") as f:
        f.write(updated)

    print("UPDATED:", new_path)

print("Patch processing completed.")
