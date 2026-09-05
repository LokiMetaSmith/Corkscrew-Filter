"""
kicad_plugin/kicad_modifier.py

Bi-Directional S-Expression Layout Modifier for KiCad 7, 8, 9, 10.
Safely updates trace geometry, net trace widths, and microstrip parameters directly
in the active .kicad_pcb file with automatic timestamped safety backups.
"""

import os
import re
import time
import shutil
from typing import Dict, Any, Optional, Tuple


class KiCadLayoutModifier:
    """Safely modifies KiCad PCB S-expression files with transactional backups."""

    def __init__(self, pcb_filepath: str):
        self.pcb_filepath = pcb_filepath

    def create_backup(self) -> str:
        """Creates a timestamped backup of the target .kicad_pcb file."""
        if not os.path.exists(self.pcb_filepath):
            raise FileNotFoundError(f"Board file not found: {self.pcb_filepath}")

        timestamp = int(time.time())
        backup_path = f"{self.pcb_filepath}.bak_{timestamp}"
        shutil.copy2(self.pcb_filepath, backup_path)
        return backup_path

    def update_net_trace_width(
        self,
        net_name: str,
        new_width_mm: float,
        create_backup: bool = True
    ) -> Dict[str, Any]:
        """
        Updates the trace width of all segments belonging to the specified net.
        Preserves indentation, line breaks, comments, and UUIDs.
        """
        if not os.path.exists(self.pcb_filepath):
            return {
                "success": False,
                "error": f"Board file not found: {self.pcb_filepath}"
            }

        backup_file = None
        if create_backup:
            try:
                backup_file = self.create_backup()
            except Exception as e:
                return {"success": False, "error": f"Backup creation failed: {e}"}

        with open(self.pcb_filepath, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()

        def extract_s_expr_spans(text: str, tag: str):
            spans = []
            pattern = re.compile(rf'\({tag}\b')
            for m in pattern.finditer(text):
                start = m.start()
                depth = 0
                in_string = False
                escape = False
                end = -1
                for i in range(start, len(text)):
                    ch = text[i]
                    if escape:
                        escape = False
                        continue
                    if ch == '\\':
                        escape = True
                        continue
                    if ch == '"':
                        in_string = not in_string
                        continue
                    if not in_string:
                        if ch == '(':
                            depth += 1
                        elif ch == ')':
                            depth -= 1
                            if depth == 0:
                                end = i + 1
                                break
                if end != -1:
                    spans.append((start, end))
            return spans

        seg_spans = extract_s_expr_spans(content, "segment")
        modified_count = 0
        chunks = []
        last_idx = 0

        net_quoted = re.escape(net_name)
        net_check_pat = re.compile(rf'\(net\s+(?:\d+\s+)?\"?{net_quoted}\"?\)')

        for start, end in seg_spans:
            seg_text = content[start:end]
            if net_check_pat.search(seg_text):
                formatted_w = f"{new_width_mm:.4f}".rstrip("0").rstrip(".")
                new_seg_text, n_subs = re.subn(
                    r'\(width\s+[\d\.]+\)',
                    f"(width {formatted_w})",
                    seg_text,
                    count=1
                )
                if n_subs > 0:
                    chunks.append(content[last_idx:start])
                    chunks.append(new_seg_text)
                    last_idx = end
                    modified_count += 1

        if modified_count == 0:
            return {
                "success": False,
                "modified_segments": 0,
                "backup_path": backup_file,
                "message": f"No segments found for net '{net_name}'"
            }

        chunks.append(content[last_idx:])
        new_content = "".join(chunks)

        temp_path = f"{self.pcb_filepath}.tmp_{int(time.time())}"
        with open(temp_path, "w", encoding="utf-8") as f:
            f.write(new_content)

        shutil.move(temp_path, self.pcb_filepath)

        return {
            "success": True,
            "net_name": net_name,
            "new_width_mm": new_width_mm,
            "modified_segments": modified_count,
            "backup_path": backup_file,
            "message": f"Successfully updated {modified_count} segments on net '{net_name}' to {new_width_mm:.3f} mm."
        }
