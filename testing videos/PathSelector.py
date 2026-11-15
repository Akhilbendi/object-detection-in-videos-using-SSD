import tkinter as tk
from tkinter import filedialog, messagebox
import os
import json

# saved_paths.json is stored beside this Python file.
CONFIG_FILE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "saved_paths.json"
)

SUPPORTED_EXTENSIONS = (".csv", ".gpg")


def validate_paths(paths):
    """Validate the selected folders and key-file locations."""

    input_directory = paths.get("input", "")
    output_directory = paths.get("output", "")
    public_key = paths.get("public_key", "")
    private_key = paths.get("private_key", "")

    if not os.path.isdir(input_directory):
        print("Invalid input folder.")
        return False

    input_files = [
        name for name in os.listdir(input_directory)
        if name.lower().endswith(SUPPORTED_EXTENSIONS)
        and os.path.isfile(os.path.join(input_directory, name))
    ]

    if not input_files:
        print("The input folder contains no supported CSV or GPG files.")
        return False

    if not os.path.isdir(output_directory):
        print("Invalid output folder.")
        return False

    if not os.access(output_directory, os.W_OK):
        print("The output folder is not writable.")
        return False

    for key_path, key_name in (
        (public_key, "public"),
        (private_key, "private")
    ):
        if not os.path.isfile(key_path) or not os.access(key_path, os.R_OK):
            print(f"The selected {key_name} key file cannot be accessed.")
            return False

    return True


def select_folder(root, title):
    return filedialog.askdirectory(title=title, parent=root)


def select_key(root, title):
    return filedialog.askopenfilename(
        title=title,
        filetypes=[
            ("All Files", "*.*"),
            ("PGP Key Files", "*.asc *.pgp *.gpg")
        ],
        parent=root
    )


def load_paths():
    if not os.path.isfile(CONFIG_FILE):
        return None

    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as file:
            paths = json.load(file)

        required_fields = ("input", "output", "public_key", "private_key")
        if not isinstance(paths, dict) or any(
            not isinstance(paths.get(field), str) for field in required_fields
        ):
            print("Saved path settings are incomplete.")
            return None

        return paths

    except (OSError, json.JSONDecodeError):
        print("Saved paths could not be loaded.")
        return None


def save_paths(paths):
    """Save locations only, never key contents or passphrases."""
    temporary_file = CONFIG_FILE + ".tmp"

    with open(temporary_file, "w", encoding="utf-8") as file:
        json.dump(paths, file, indent=4)

    os.replace(temporary_file, CONFIG_FILE)


def select_paths():
    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)

    try:
        paths = load_paths()

        if paths is None:
            print("\nFirst-time setup: select all four locations.")
            paths = {
                "input": "",
                "output": "",
                "public_key": "",
                "private_key": ""
            }
            change_all = True

        else:
            print("\nSaved paths found.")
            print("1. Use saved paths")
            print("2. Change selected paths")
            choice = input("Enter your choice (1 or 2): ").strip()

            if choice == "1":
                if validate_paths(paths):
                    print("Using saved paths.")
                    return paths

                print("Saved paths are invalid. Process stopped.")
                print("Run again and choose option 2 to update them.")
                return None

            elif choice == "2":
                change_all = False

            else:
                print("Invalid choice. Process stopped.")
                return None

        fields = [
            ("input", "Change input folder?", "folder"),
            ("output", "Change output folder?", "folder"),
            ("public_key", "Change public key?", "key"),
            ("private_key", "Change private key?", "key")
        ]

        for field, question, field_type in fields:
            if change_all or not paths.get(field):
                change = True
            else:
                answer = input(question + " (y/n): ").strip().lower()

                if answer not in ("y", "yes", "n", "no"):
                    print("Please enter y or n. Process stopped.")
                    return None

                change = answer in ("y", "yes")

            if not change:
                continue

            field_title = field.replace("_", " ").title()

            if field_type == "folder":
                selected = select_folder(
                    root, "Select " + field_title + " Folder"
                )
            else:
                selected = select_key(
                    root, "Select " + field_title + " File"
                )

            if not selected:
                print("Selection cancelled. Process stopped.")
                return None

            paths[field] = selected

        if not validate_paths(paths):
            messagebox.showerror(
                "Invalid Paths",
                "One or more paths are invalid. Run the application again "
                "and correct the selections."
            )
            return None

        save_paths(paths)
        print("Paths validated and saved successfully.")
        return paths

    except OSError as error:
        print("Could not save or load path settings:", error)
        messagebox.showerror(
            "Path Settings Error",
            "Could not save or load the path settings. Check folder permissions."
        )
        return None

    finally:
        root.destroy()
