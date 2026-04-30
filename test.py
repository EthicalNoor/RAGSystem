import os

# Folders to exclude
EXCLUDE_DIRS = {
    "node_modules",
    "venv",
    ".venv",
    "__pycache__",
    ".git",
    "dist",
    "build"
}

def print_structure(root_path, indent=""):
    """
    Recursively prints directory structure in tree format
    """
    try:
        # Filter excluded directories/files
        items = sorted([
            item for item in os.listdir(root_path)
            if item not in EXCLUDE_DIRS
        ])
    except PermissionError:
        print(indent + "└── [Permission Denied]")
        return

    for index, item in enumerate(items):
        path = os.path.join(root_path, item)
        is_last = index == len(items) - 1

        connector = "└── " if is_last else "├── "
        print(indent + connector + item)

        if os.path.isdir(path):
            new_indent = indent + ("    " if is_last else "│   ")
            print_structure(path, new_indent)


def generate_tree(root_path):
    """
    Entry function
    """
    if not os.path.exists(root_path):
        print("❌ Path does not exist")
        return

    print(f"\n📁 {os.path.basename(root_path)}")
    print_structure(root_path)


if __name__ == "__main__":
    folder_path = input("Enter folder path: ").strip()
    generate_tree(folder_path)