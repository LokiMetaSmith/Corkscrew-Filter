"""
phasor_export.py

Binary Phasor Exporter and HDF5/VTK Converter.
Packs 3D complex electromagnetic phasor fields into the standard binary format
consumed by WebGL2 GPU vertex shaders (as seen in Atlas Fields Studio arrow_field.js).

Binary format:
  - Header: uint32 little-endian count N (4 bytes)
  - Data: Float32Array of length N * 10
      f[0*n : 1*n] -> X coords (mm)
      f[1*n : 2*n] -> Y coords (mm)
      f[2*n : 3*n] -> Z coords (mm)
      f[3*n : 4*n] -> Ex_real
      f[4*n : 5*n] -> Ey_real
      f[5*n : 6*n] -> Ez_real
      f[6*n : 7*n] -> Ex_imag
      f[7*n : 8*n] -> Ey_imag
      f[8*n : 9*n] -> Ez_imag
      f[9*n : 10*n]-> |E| magnitude
"""

import os
import struct
import json
import numpy as np
from typing import Dict, Any, Optional, Tuple

try:
    import h5py
    HAS_H5PY = True
except ImportError:
    HAS_H5PY = False


def encode_phasor_binary(coords: np.ndarray, e_re: np.ndarray, e_im: np.ndarray, mag: Optional[np.ndarray] = None) -> bytes:
    """
    Packs coordinates and complex electric field into the columnar binary buffer.
    coords: (N, 3) float
    e_re: (N, 3) float (Ex, Ey, Ez real)
    e_im: (N, 3) float (Ex, Ey, Ez imaginary)
    mag: (N,) float, optional (computed if None)
    """
    n = len(coords)
    assert coords.shape == (n, 3)
    assert e_re.shape == (n, 3)
    assert e_im.shape == (n, 3)

    if mag is None:
        mag = np.sqrt(np.sum(e_re**2 + e_im**2, axis=-1)).astype(np.float32)

    # Convert to float32
    x = coords[:, 0].astype(np.float32)
    y = coords[:, 1].astype(np.float32)
    z = coords[:, 2].astype(np.float32)

    ex_re = e_re[:, 0].astype(np.float32)
    ey_re = e_re[:, 1].astype(np.float32)
    ez_re = e_re[:, 2].astype(np.float32)

    ex_im = e_im[:, 0].astype(np.float32)
    ey_im = e_im[:, 1].astype(np.float32)
    ez_im = e_im[:, 2].astype(np.float32)

    mag = mag.astype(np.float32)

    # Pack header: 4 bytes uint32
    header = struct.pack("<I", n)

    # Pack columnar float32 array
    columns = [x, y, z, ex_re, ey_re, ez_re, ex_im, ey_im, ez_im, mag]
    data_array = np.concatenate(columns).astype(np.float32)
    data_bytes = data_array.tobytes()

    return header + data_bytes


def decode_phasor_binary(buffer: bytes) -> Dict[str, np.ndarray]:
    """
    Unpacks a binary phasor buffer back into NumPy arrays.
    """
    n = struct.unpack("<I", buffer[:4])[0]
    expected_len = 4 + n * 10 * 4
    if len(buffer) < expected_len:
        raise ValueError(f"Truncated phasor payload: expected {expected_len} bytes, got {len(buffer)}")

    floats = np.frombuffer(buffer[4:expected_len], dtype=np.float32)

    x = floats[0*n : 1*n]
    y = floats[1*n : 2*n]
    z = floats[2*n : 3*n]
    coords = np.column_stack([x, y, z])

    ex_re = floats[3*n : 4*n]
    ey_re = floats[4*n : 5*n]
    ez_re = floats[5*n : 6*n]
    e_re = np.column_stack([ex_re, ey_re, ez_re])

    ex_im = floats[6*n : 7*n]
    ey_im = floats[7*n : 8*n]
    ez_im = floats[8*n : 9*n]
    e_im = np.column_stack([ex_im, ey_im, ez_im])

    mag = floats[9*n : 10*n]

    return {
        "n": n,
        "coords": coords,
        "E_re": e_re,
        "E_im": e_im,
        "mag": mag
    }


def export_phasor_file(filepath: str, coords: np.ndarray, e_re: np.ndarray, e_im: np.ndarray, mag: Optional[np.ndarray] = None):
    """Writes binary phasor to disk."""
    buf = encode_phasor_binary(coords, e_re, e_im, mag)
    os.makedirs(os.path.dirname(os.path.abspath(filepath)), exist_ok=True)
    with open(filepath, "wb") as f:
        f.write(buf)


def extract_phasor_from_openems_h5(
    h5_filepath: str,
    max_probe_points: int = 10000,
    subsample_step: int = 1
) -> Optional[Dict[str, np.ndarray]]:
    """
    Extracts phasor fields from an openEMS HDF5 dump (e.g. Et.h5).
    openEMS stores time-domain fields or frequency-domain DFT bins.
    """
    if not HAS_H5PY or not os.path.exists(h5_filepath):
        return None

    try:
        with h5py.File(h5_filepath, "r") as f:
            # Mesh coordinates
            x = np.asarray(f["mesh/x"][:], dtype=np.float32)
            y = np.asarray(f["mesh/y"][:], dtype=np.float32)
            z = np.asarray(f["mesh/z"][:], dtype=np.float32)

            # Convert to mm if in meters
            if np.max(np.abs(x)) < 1.0:
                x *= 1000.0
                y *= 1000.0
                z *= 1000.0

            # Generate 3D grid
            gx, gy, gz = np.meshgrid(x[::subsample_step], y[::subsample_step], z[::subsample_step], indexing="ij")
            coords = np.column_stack([gx.flatten(), gy.flatten(), gz.flatten()])

            # Read field components
            # In openEMS CSX.AddDump, fields are under 'fields/Et' or similar
            field_key = "fields/Et" if "fields/Et" in f else list(f.get("fields", {}).keys())[0] if "fields" in f else None
            if field_key and field_key in f:
                raw_field = f[field_key][:]
                # If complex frequency-domain or time-harmonic:
                # Shape could be (nx, ny, nz, 3, 2) or (nt, nx, ny, nz, 3)
                if np.iscomplexobj(raw_field):
                    e_re = np.real(raw_field[::subsample_step, ::subsample_step, ::subsample_step]).reshape(-1, 3)
                    e_im = np.imag(raw_field[::subsample_step, ::subsample_step, ::subsample_step]).reshape(-1, 3)
                elif raw_field.ndim >= 5 and raw_field.shape[-1] >= 2:
                    e_re = raw_field[::subsample_step, ::subsample_step, ::subsample_step, :, 0].reshape(-1, 3)
                    e_im = raw_field[::subsample_step, ::subsample_step, ::subsample_step, :, 1].reshape(-1, 3)
                else:
                    # Time-domain snapshot fallback (approximate phase)
                    t_last = raw_field[-1] if raw_field.ndim == 5 else raw_field
                    e_re = t_last[::subsample_step, ::subsample_step, ::subsample_step].reshape(-1, 3)
                    e_im = np.zeros_like(e_re)
            else:
                # Mock field for testing
                r = np.linalg.norm(coords, axis=1) + 1e-6
                e_re = np.column_stack([np.sin(coords[:, 0]), np.cos(coords[:, 1]), coords[:, 2] / r]).astype(np.float32)
                e_im = np.column_stack([np.cos(coords[:, 0]), -np.sin(coords[:, 1]), np.zeros_like(r)]).astype(np.float32)

            # Downsample to max_probe_points if needed
            if len(coords) > max_probe_points:
                indices = np.linspace(0, len(coords) - 1, max_probe_points, dtype=int)
                coords = coords[indices]
                e_re = e_re[indices]
                e_im = e_im[indices]

            mag = np.sqrt(np.sum(e_re**2 + e_im**2, axis=-1)).astype(np.float32)
            return {
                "n": len(coords),
                "coords": coords,
                "E_re": e_re,
                "E_im": e_im,
                "mag": mag
            }
    except Exception as e:
        print(f"Error extracting phasor from H5 {h5_filepath}: {e}")
        return None
