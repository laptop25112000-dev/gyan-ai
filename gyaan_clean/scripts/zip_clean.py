import os
import zipfile

# Files and directories to exclude
EXCLUDE_DIRS = {
    ".deps",
    ".venv",
    "venv",
    "__pycache__",
    ".git",
    ".vercel",
    ".idea",
    ".vscode",
}
EXCLUDE_FILES = {
    ".env",
    "gyaan_clean.zip",
}

def zip_project(output_filename="gyaan_clean.zip"):
    root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    print(f"Creating clean zip archive at: {os.path.join(root_dir, output_filename)}")
    
    with zipfile.ZipFile(os.path.join(root_dir, output_filename), "w", zipfile.ZIP_DEFLATED) as zipf:
        for root, dirs, files in os.walk(root_dir):
            # Modify dirs in-place to skip excluded directories
            dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]
            
            for file in files:
                if file in EXCLUDE_FILES or file.endswith((".pyc", ".log")):
                    continue
                
                full_path = os.path.join(root, file)
                relative_path = os.path.relpath(full_path, root_dir)
                
                # Skip the zip file itself if it matches the output name
                if relative_path == output_filename or relative_path == f"scripts/{output_filename}":
                    continue
                
                print(f"Adding: {relative_path}")
                zipf.write(full_path, relative_path)
                
    print("\nZip archive created successfully!")

if __name__ == "__main__":
    zip_project()
