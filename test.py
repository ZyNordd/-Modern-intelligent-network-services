from pathlib import Path

folder = Path("screenshots")

for file in folder.iterdir():
    if file.is_file() and file.suffix == ".png":
        print(file.name)
