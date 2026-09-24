"""Interactive, cross-platform path selection via the OS-native file dialog.

Uses tkinter (bundled with the conda Python distribution) so folder/file
pickers work the same way on Windows and macOS.
"""
import tkinter as tk
from tkinter import filedialog, simpledialog
from pathlib import Path


def _dialog_root():
    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)
    return root


def pick_directory(title, initialdir=None):
    root = _dialog_root()
    try:
        selected = filedialog.askdirectory(
            title=title,
            initialdir=str(initialdir) if initialdir else None,
            mustexist=True
        )
    finally:
        root.destroy()

    if not selected:
        raise RuntimeError(f"No folder selected for: {title}")

    return Path(selected)


def pick_file(title, filetypes, initialdir=None):
    root = _dialog_root()
    try:
        selected = filedialog.askopenfilename(
            title=title,
            initialdir=str(initialdir) if initialdir else None,
            filetypes=filetypes
        )
    finally:
        root.destroy()

    if not selected:
        raise RuntimeError(f"No file selected for: {title}")

    return Path(selected)


def prompt_epsg_code(prompt, initial_value=""):
    """Prompt user to type an EPSG code (e.g. "EPSG:6340+5703") via a
    dialog box -- used as a manual fallback when a dataset's CRS can't
    be detected automatically.
    """
    root = _dialog_root()
    try:
        entered = simpledialog.askstring(
            title="Enter EPSG code",
            prompt=prompt,
            initialvalue=initial_value,
            parent=root
        )
    finally:
        root.destroy()

    if not entered:
        raise RuntimeError(f"No EPSG code entered for: {prompt}")

    return entered.strip()


def prompt_dataset_crs(label, folder_name, horizontal_crs=None, example="EPSG:6340+5703"):
    """Ask for one epoch's CRS when it couldn't be read from the files.
    If the files do record a horizontal CRS (horizontal_crs, e.g.
    "EPSG:6340") but no vertical one, the dialog says so and is pre-filled
    with "<horizontal>+" -- only the vertical code is left to add.
    """
    if horizontal_crs:
        prompt = (
            f"The {label} files ({folder_name}) only record a horizontal CRS: "
            f"{horizontal_crs}.\n"
            f"Their elevations need a vertical CRS too. Add its EPSG code after "
            f"the '+', matching the elevations' datum AND units -- e.g. NAVD88 "
            f"height: +5703 (meters) or +6360 (US survey feet)."
        )
        initial_value = f"{horizontal_crs}+"
    else:
        prompt = (
            f"No CRS found in the {label} dataset's metadata ({folder_name}).\n"
            f"Enter its EPSG code (e.g. {example}):"
        )
        initial_value = ""

    return prompt_epsg_code(prompt, initial_value=initial_value)
