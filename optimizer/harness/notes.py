import os

class NotesManager:
    def __init__(self, filepath: str = "notes.md"):
        self.filepath = filepath

    def append_note(self, title: str, section_content: str):
        """
        Appends or updates a section in the notes.md file.
        """
        dir_name = os.path.dirname(self.filepath)
        if dir_name:
            os.makedirs(dir_name, exist_ok=True)

        mode = "a" if os.path.exists(self.filepath) else "w"
        with open(self.filepath, mode) as f:
            f.write(f"\n## {title}\n")
            f.write(f"{section_content.strip()}\n")

    def read_notes(self) -> str:
        if not os.path.exists(self.filepath):
            return ""
        with open(self.filepath, "r") as f:
            return f.read()
