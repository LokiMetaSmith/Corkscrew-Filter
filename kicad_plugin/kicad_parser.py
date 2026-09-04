"""
kicad_parser.py

Pure-Python KiCad PCB (.kicad_pcb) S-Expression Parser.
Extracts:
  - Board layer stackup (thickness, copper thickness, dielectric constant, loss tangent)
  - Controlled impedance / RF trace segments (start, end, width, net, layer)
  - Differential pair spacing for coupled nets (e.g. _POS / _NEG or _P / _N)
  - Board boundary outline (Edge.Cuts)
Operates 100% standalone without requiring KiCad C++ pcbnew library.
"""

import re
import os
import math
from typing import Dict, Any, List, Optional, Tuple


class KiCadPcbParser:
    """
    High-performance pure-Python S-expression parser for KiCad PCB layouts.
    """

    def __init__(self, pcb_filepath: Optional[str] = None):
        self.pcb_filepath = pcb_filepath
        self.raw_text = ""
        self.stackup: Dict[str, float] = {
            "substrate_height_mm": 1.6,
            "copper_thickness_mm": 0.035,
            "dielectric_constant": 4.3,
            "loss_tangent": 0.02
        }
        self.nets: Dict[int, str] = {}
        self.segments: List[Dict[str, Any]] = []
        self.differential_pairs: List[Dict[str, Any]] = []
        self.board_bounds: Dict[str, float] = {"width_mm": 50.0, "length_mm": 50.0}
        self.edge_cuts: List[Dict[str, Any]] = []
        self.component_pads: List[Dict[str, Any]] = []
        self.zones: List[Dict[str, Any]] = []

        if pcb_filepath and os.path.exists(pcb_filepath):
            self.load_file(pcb_filepath)

    def load_file(self, pcb_filepath: str) -> bool:
        """Loads and parses a .kicad_pcb file."""
        self.pcb_filepath = pcb_filepath
        try:
            with open(pcb_filepath, "r", encoding="utf-8", errors="ignore") as f:
                self.raw_text = f.read()
            self._parse_all()
            return True
        except Exception as e:
            print(f"[KiCadPcbParser] Error reading {pcb_filepath}: {e}")
            return False

    def load_string(self, pcb_content: str) -> bool:
        """Parses in-memory .kicad_pcb S-expression string."""
        self.raw_text = pcb_content
        self._parse_all()
        return True

    def _parse_all(self):
        self._parse_nets()
        self._parse_stackup()
        self._parse_segments()
        self._parse_differential_pairs()
        self._parse_board_bounds()
        self._parse_component_pads()
        self._parse_zones()

    def _parse_nets(self):
        """Extracts (net <id> "<name>") definitions."""
        self.nets = {}
        pattern = re.compile(r'\(net\s+(\d+)\s+"([^"]*)"\)')
        for match in pattern.finditer(self.raw_text):
            net_id = int(match.group(1))
            net_name = match.group(2)
            self.nets[net_id] = net_name

    def _parse_stackup(self):
        """Extracts thickness, epsilon_r, and copper thickness."""
        # General thickness
        m_thick = re.search(r'\(general\s+.*?\bthickness\s+([\d\.]+)', self.raw_text, re.DOTALL)
        if m_thick:
            self.stackup["substrate_height_mm"] = float(m_thick.group(1))

        # Dielectric constant (epsilon_r) from stackup if present
        m_eps = re.search(r'\(epsilon_r\s+([\d\.]+)\)', self.raw_text)
        if m_eps:
            self.stackup["dielectric_constant"] = float(m_eps.group(1))

        # Loss tangent
        m_tand = re.search(r'\(loss_tangent\s+([\d\.]+)\)', self.raw_text)
        if m_tand:
            self.stackup["loss_tangent"] = float(m_tand.group(1))

        # Copper thickness
        m_cu = re.search(r'\(thickness\s+([\d\.]+)\)\s*\(material\s+"copper"\)', self.raw_text, re.IGNORECASE)
        if m_cu:
            self.stackup["copper_thickness_mm"] = float(m_cu.group(1))

    def _parse_segments(self):
        """
        Extracts trace segments supporting both single-line (KiCad 7/8) and
        multi-line indented (KiCad 9/10) formats with integer or string net names.
        """
        self.segments = []
        seg_pat = re.compile(r'\(segment\b((?:[^\(\)]*|\([^\(\)]*\))*)\)', re.DOTALL)
        for m in seg_pat.finditer(self.raw_text):
            body = m.group(1)
            m_start = re.search(r'\(start\s+([\d\.\-]+)\s+([\d\.\-]+)\)', body)
            m_end = re.search(r'\(end\s+([\d\.\-]+)\s+([\d\.\-]+)\)', body)
            m_width = re.search(r'\(width\s+([\d\.]+)\)', body)
            m_layer = re.search(r'\(layer\s+\"?([^\"\)\s]+)\"?\)', body)
            m_net = re.search(r'\(net\s+(?:(\d+)\s+)?\"?([^\"\)\s]+)\"?\)', body)

            if m_start and m_end and m_width and m_layer:
                x1, y1 = float(m_start.group(1)), float(m_start.group(2))
                x2, y2 = float(m_end.group(1)), float(m_end.group(2))
                width = float(m_width.group(1))
                layer = m_layer.group(1)

                net_id = None
                net_name = "UNKNOWN"
                if m_net:
                    if m_net.group(1) is not None:
                        net_id = int(m_net.group(1))
                        net_name = self.nets.get(net_id, m_net.group(2) or f"Net-{net_id}")
                    else:
                        val = m_net.group(2)
                        if val.isdigit() and int(val) in self.nets:
                            net_id = int(val)
                            net_name = self.nets[net_id]
                        else:
                            net_name = val

                length = math.hypot(x2 - x1, y2 - y1)
                self.segments.append({
                    "start": (x1, y1),
                    "end": (x2, y2),
                    "width_mm": width,
                    "length_mm": length,
                    "layer": layer,
                    "net_id": net_id,
                    "net_name": net_name
                })


    def _parse_differential_pairs(self):
        """
        Identifies differential pairs by scanning parallel segments with matching
        differential net name conventions (POS/NEG, P/N, +/-).
        """
        self.differential_pairs = []
        if len(self.segments) < 2:
            return

        # Find parallel segments on the same layer
        for i in range(len(self.segments)):
            seg_a = self.segments[i]
            net_a = seg_a["net_name"].upper()

            for j in range(i + 1, len(self.segments)):
                seg_b = self.segments[j]
                net_b = seg_b["net_name"].upper()

                if seg_a["layer"] != seg_b["layer"] or seg_a["net_name"] == seg_b["net_name"]:
                    continue

                # Check for differential naming affinity
                is_pair_named = (
                    ("POS" in net_a and "NEG" in net_b) or
                    ("NEG" in net_a and "POS" in net_b) or
                    (net_a.endswith("_P") and net_b.endswith("_N")) or
                    (net_a.endswith("_N") and net_b.endswith("_P")) or
                    (net_a.endswith("+") and net_b.endswith("-")) or
                    (net_a.endswith("-") and net_b.endswith("+")) or
                    (net_a.endswith("_DP") and net_b.endswith("_DN")) or
                    (net_a.endswith("_DN") and net_b.endswith("_DP"))
                )

                if is_pair_named:
                    # Compute center-to-center distance
                    mid_a = ((seg_a["start"][0] + seg_a["end"][0]) / 2.0, (seg_a["start"][1] + seg_a["end"][1]) / 2.0)
                    mid_b = ((seg_b["start"][0] + seg_b["end"][0]) / 2.0, (seg_b["start"][1] + seg_b["end"][1]) / 2.0)
                    center_dist = math.hypot(mid_b[0] - mid_a[0], mid_b[1] - mid_a[1])

                    # Edge-to-edge spacing s = center_dist - width
                    avg_w = (seg_a["width_mm"] + seg_b["width_mm"]) / 2.0
                    spacing = max(0.05, center_dist - avg_w)

                    if spacing < 5.0:  # Physically coupled pair threshold
                        self.differential_pairs.append({
                            "net_positive": seg_a["net_name"],
                            "net_negative": seg_b["net_name"],
                            "trace_width_mm": avg_w,
                            "spacing_mm": round(spacing, 4),
                            "length_mm": (seg_a["length_mm"] + seg_b["length_mm"]) / 2.0,
                            "layer": seg_a["layer"]
                        })

    def _extract_s_exprs(self, text: str, tag: str) -> List[str]:
        """Extracts top-level and sub-level S-expressions with given tag using linear balanced parenthesis scanning."""
        results = []
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
                results.append(text[start:end])
        return results

    def _parse_board_bounds(self):
        """Extracts board outline from Edge.Cuts gr_line / gr_rect / gr_arc elements."""
        coords_x = []
        coords_y = []
        self.edge_cuts = []

        # Extract all gr_line elements
        gr_lines = self._extract_s_exprs(self.raw_text, 'gr_line')
        for block in gr_lines:
            if 'Edge.Cuts' in block or '"Edge.Cuts"' in block:
                m_start = re.search(r'\(start\s+([\d\.\-]+)\s+([\d\.\-]+)\)', block)
                m_end = re.search(r'\(end\s+([\d\.\-]+)\s+([\d\.\-]+)\)', block)
                m_w = re.search(r'\(width\s+([\d\.\-]+)\)', block)
                if m_start and m_end:
                    x1, y1 = float(m_start.group(1)), float(m_start.group(2))
                    x2, y2 = float(m_end.group(1)), float(m_end.group(2))
                    w = float(m_w.group(1)) if m_w else 0.15
                    self.edge_cuts.append({"x1": x1, "y1": y1, "x2": x2, "y2": y2, "width": w})
                    coords_x.extend([x1, x2])
                    coords_y.extend([y1, y2])

        # Fallback to single-line regex if not matched
        if not coords_x:
            single_pat = re.compile(r'\(gr_line\s+\(start\s+([\d\.\-]+)\s+([\d\.\-]+)\)\s+\(end\s+([\d\.\-]+)\s+([\d\.\-]+)\)\s+\(layer\s+"Edge\.Cuts"\)')
            for m in single_pat.finditer(self.raw_text):
                x1, y1 = float(m.group(1)), float(m.group(2))
                x2, y2 = float(m.group(3)), float(m.group(4))
                self.edge_cuts.append({"x1": x1, "y1": y1, "x2": x2, "y2": y2, "width": 0.15})
                coords_x.extend([x1, x2])
                coords_y.extend([y1, y2])

        # Fallback to segment bounds + 5mm margin
        if not coords_x and self.segments:
            for s in self.segments:
                coords_x.extend([s["start"][0], s["end"][0]])
                coords_y.extend([s["start"][1], s["end"][1]])

        if coords_x and coords_y:
            min_x, max_x = min(coords_x), max(coords_x)
            min_y, max_y = min(coords_y), max(coords_y)
            self.board_bounds = {
                "width_mm": round(max_x - min_x, 2),
                "height_mm": round(max_y - min_y, 2),
                "center_x": round((min_x + max_x) / 2.0, 3),
                "center_y": round((min_y + max_y) / 2.0, 3),
                "min_x": round(min_x, 3),
                "max_x": round(max_x, 3),
                "min_y": round(min_y, 3),
                "max_y": round(max_y, 3)
            }
        else:
            self.board_bounds = {
                "width_mm": 50.0,
                "height_mm": 50.0,
                "center_x": 25.0,
                "center_y": 25.0,
                "min_x": 0.0,
                "max_x": 50.0,
                "min_y": 0.0,
                "max_y": 50.0
            }

    def _parse_component_pads(self):
        """Extracts component pads across all footprints, transforming them to world coordinates."""
        self.component_pads = []
        cx = self.board_bounds.get("center_x", 0.0)
        cy = self.board_bounds.get("center_y", 0.0)

        import math
        footprints = self._extract_s_exprs(self.raw_text, 'footprint')
        for fp in footprints:
            fp_at_m = re.search(r'\(at\s+([\d\.\-]+)\s+([\d\.\-]+)(?:\s+([\d\.\-]+))?\)', fp)
            if not fp_at_m:
                continue
            fpx = float(fp_at_m.group(1))
            fpy = float(fp_at_m.group(2))
            fprot = float(fp_at_m.group(3)) if fp_at_m.group(3) else 0.0
            rad = math.radians(fprot)
            cos_r = math.cos(rad)
            sin_r = math.sin(rad)

            ref_m = re.search(r'\(property\s+"Reference"\s+"([^"]*)"', fp)
            ref_name = ref_m.group(1) if ref_m else ""

            pads = self._extract_s_exprs(fp, 'pad')
            for pad in pads:
                head_m = re.match(r'\(pad\s+("[^"]*"|\S+)\s+(\S+)\s+(\S+)', pad)
                if not head_m:
                    continue
                pad_num = head_m.group(1).strip('"')
                pad_type = head_m.group(2)
                pad_shape = head_m.group(3)

                at_m = re.search(r'\(at\s+([\d\.\-]+)\s+([\d\.\-]+)(?:\s+([\d\.\-]+))?\)', pad)
                size_m = re.search(r'\(size\s+([\d\.\-]+)\s+([\d\.\-]+)\)', pad)
                layer_m = re.search(r'\(layers?\s+([^\)]+)\)', pad)
                net_m = re.search(r'\(net\s+("?[^"\)\s]+"?)', pad)

                if not size_m:
                    continue
                lx = float(at_m.group(1)) if at_m else 0.0
                ly = float(at_m.group(2)) if at_m else 0.0
                pad_rot = float(at_m.group(3)) if (at_m and at_m.group(3)) else 0.0

                wx = fpx + lx * cos_r - ly * sin_r
                wy = fpy + lx * sin_r + ly * cos_r

                layer_str = layer_m.group(1) if layer_m else ""
                is_top = ("F.Cu" in layer_str or "*.Cu" in layer_str)
                is_bot = ("B.Cu" in layer_str or "*.Cu" in layer_str)
                is_thru = (pad_type in ["thru_hole", "np_thru_hole"])

                self.component_pads.append({
                    "ref": ref_name,
                    "num": pad_num,
                    "type": pad_type,
                    "shape": pad_shape,
                    "x": round(wx - cx, 4),
                    "y": round(wy - cy, 4),
                    "w": float(size_m.group(1)),
                    "h": float(size_m.group(2)),
                    "rot": round((fprot + pad_rot) % 360, 2),
                    "is_top": is_top,
                    "is_bot": is_bot,
                    "is_thru": is_thru,
                    "net": net_m.group(1).strip('"') if net_m else ""
                })

    def _parse_zones(self):
        """Extracts metal pours (zones) and their filled polygons."""
        self.zones = []
        cx = self.board_bounds.get("center_x", 0.0)
        cy = self.board_bounds.get("center_y", 0.0)

        zone_blocks = self._extract_s_exprs(self.raw_text, 'zone')
        for z in zone_blocks:
            net_m = re.search(r'\((?:net_name|net)\s+("?[^"\)\s]+"?)', z)
            net_str = net_m.group(1).strip('"') if net_m else "GND"

            filled_polys = self._extract_s_exprs(z, 'filled_polygon')
            if not filled_polys:
                outline_polys = self._extract_s_exprs(z, 'polygon')
                layer_m = re.search(r'\(layers?\s+([^\)]+)\)', z)
                layer_str = layer_m.group(1).strip('"') if layer_m else "F.Cu"
                for p in outline_polys:
                    pts = re.findall(r'\(xy\s+([\d\.\-]+)\s+([\d\.\-]+)\)', p)
                    if len(pts) >= 3:
                        pts_norm = [[round(float(pt[0]) - cx, 3), round(float(pt[1]) - cy, 3)] for pt in pts]
                        self.zones.append({
                            "net": net_str,
                            "layer": layer_str,
                            "is_top": "F.Cu" in layer_str,
                            "is_bot": "B.Cu" in layer_str,
                            "pts": pts_norm
                        })
                continue

            for fp in filled_polys:
                layer_m = re.search(r'\(layers?\s+("?[^"\)\s]+"?)', fp)
                layer_str = layer_m.group(1).strip('"') if layer_m else "F.Cu"
                pts = re.findall(r'\(xy\s+([\d\.\-]+)\s+([\d\.\-]+)\)', fp)
                if len(pts) < 3:
                    continue

                pts_float = [(float(p[0]) - cx, float(p[1]) - cy) for p in pts]
                simplified = [pts_float[0]]
                for p in pts_float[1:]:
                    dx = p[0] - simplified[-1][0]
                    dy = p[1] - simplified[-1][1]
                    if dx * dx + dy * dy > 0.0004:
                        simplified.append(p)

                self.zones.append({
                    "net": net_str,
                    "layer": layer_str,
                    "is_top": "F.Cu" in layer_str,
                    "is_bot": "B.Cu" in layer_str,
                    "pts": [[round(p[0], 3), round(p[1], 3)] for p in simplified]
                })


    def get_all_nets_summary(self) -> Dict[str, Dict[str, Any]]:
        """
        Groups segments by net name and returns aggregate statistics.
        """
        from collections import defaultdict
        grouped = defaultdict(list)
        for s in self.segments:
            grouped[s["net_name"]].append(s)

        summary = {}
        for net, segs in grouped.items():
            total_len = sum(s["length_mm"] for s in segs)
            avg_w = sum(s["width_mm"] * s["length_mm"] for s in segs) / max(1e-6, total_len)
            primary_layer = max(set(s["layer"] for s in segs), key=lambda l: sum(s["length_mm"] for s in segs if s["layer"] == l))
            summary[net] = {
                "net_name": net,
                "trace_width_mm": round(avg_w, 4),
                "total_length_mm": round(total_len, 3),
                "segment_count": len(segs),
                "primary_layer": primary_layer
            }
        return summary

    def get_primary_rf_trace(self) -> Dict[str, Any]:
        """
        Returns primary RF/Signal trace (prioritizing differential pairs,
        high-speed keywords, and total trace length).
        """
        if not self.segments:
            return {
                "trace_width_mm": 3.043,
                "length_mm": 40.0,
                "layer": "F.Cu",
                "is_differential": False,
                "spacing_mm": None,
                "net_name": "DEFAULT_RF"
            }

        if self.differential_pairs:
            pair = self.differential_pairs[0]
            return {
                "trace_width_mm": pair["trace_width_mm"],
                "length_mm": pair["length_mm"],
                "layer": pair["layer"],
                "is_differential": True,
                "spacing_mm": pair["spacing_mm"],
                "net_name": f"{pair['net_positive']}/{pair['net_negative']}"
            }

        # Group segments by net to compute total continuous net length
        nets_summary = self.get_all_nets_summary()

        # Prioritize nets with signal/RF keywords
        keywords = ["RF", "SIGNAL", "PORE", "ANT", "GUARD", "AMP", "IN", "OUT", "TRACE"]
        for kw in keywords:
            matches = [n for n in nets_summary.values() if kw in n["net_name"].upper()]
            if matches:
                chosen = max(matches, key=lambda n: n["total_length_mm"])
                return {
                    "trace_width_mm": chosen["trace_width_mm"],
                    "length_mm": chosen["total_length_mm"],
                    "layer": chosen["primary_layer"],
                    "is_differential": False,
                    "spacing_mm": None,
                    "net_name": chosen["net_name"]
                }

        # Fallback to longest non-power/non-ground trace
        non_pwr = [n for n in nets_summary.values() if not any(p in n["net_name"].upper() for p in ["GND", "VCC", "VDD", "VSS", "POWER"])]
        chosen = max(non_pwr, key=lambda n: n["total_length_mm"]) if non_pwr else max(nets_summary.values(), key=lambda n: n["total_length_mm"])

        return {
            "trace_width_mm": chosen["trace_width_mm"],
            "length_mm": chosen["total_length_mm"],
            "layer": chosen["primary_layer"],
            "is_differential": False,
            "spacing_mm": None,
            "net_name": chosen["net_name"]
        }

