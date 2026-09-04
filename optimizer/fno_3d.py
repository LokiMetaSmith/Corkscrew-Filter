"""
fno_3d.py

3D Fourier Neural Operator (FNO-3D) for Volumetric Electromagnetic Scattering.
Implements the spectral convolution architecture from arXiv:2302.01934v2:
  - 3D Real FFT / Inverse FFT (torch.fft.rfftn / irfftn)
  - Truncated low-frequency mode parametrization with complex weights
  - GELU activation and skip connections
  - Dual-head: predicts 3D complex phasor electric fields (Ex, Ey, Ez) and S-parameters.
"""

import os
import math
import numpy as np
from typing import Dict, Any, Optional, Tuple, List

try:
    import torch
    import torch.nn as nn
    import torch.nn.functional as F
    HAS_TORCH = True
except (ImportError, OSError):
    HAS_TORCH = False


if HAS_TORCH:
    class SpectralConv3d(nn.Module):
        """
        3D Spectral Convolution Layer in Fourier Space.
        Applies learned complex matrix multiplication to low-frequency modes.
        """
        def __init__(self, in_channels: int, out_channels: int, modes1: int, modes2: int, modes3: int):
            super().__init__()
            self.in_channels = in_channels
            self.out_channels = out_channels
            self.modes1 = modes1  # Modes along X
            self.modes2 = modes2  # Modes along Y
            self.modes3 = modes3  # Modes along Z

            # Complex weights for the 4 corners of the 3D half-Hermitian Fourier spectrum
            scale = 1.0 / (in_channels * out_channels)
            self.weights1 = nn.Parameter(scale * torch.randn(in_channels, out_channels, self.modes1, self.modes2, self.modes3, dtype=torch.cfloat))
            self.weights2 = nn.Parameter(scale * torch.randn(in_channels, out_channels, self.modes1, self.modes2, self.modes3, dtype=torch.cfloat))
            self.weights3 = nn.Parameter(scale * torch.randn(in_channels, out_channels, self.modes1, self.modes2, self.modes3, dtype=torch.cfloat))
            self.weights4 = nn.Parameter(scale * torch.randn(in_channels, out_channels, self.modes1, self.modes2, self.modes3, dtype=torch.cfloat))

        def _compl_mul3d(self, order: str, input_tensor: torch.Tensor, weights: torch.Tensor) -> torch.Tensor:
            # (batch, in_channel, x, y, z) * (in_channel, out_channel, x, y, z) -> (batch, out_channel, x, y, z)
            return torch.einsum(f"bixyz,ioxyz->boxyz", input_tensor, weights)

        def forward(self, x: torch.Tensor) -> torch.Tensor:
            batch_size = x.shape[0]
            # Compute 3D real FFT -> shape (B, C, X, Y, Z//2 + 1)
            x_ft = torch.fft.rfftn(x, dim=[-3, -2, -1])

            out_ft = torch.zeros(
                batch_size, self.out_channels, x.size(-3), x.size(-2), x.size(-1) // 2 + 1,
                device=x.device, dtype=torch.cfloat
            )

            # Multiply lowest spatial frequencies across the 4 octants
            m1 = min(self.modes1, x_ft.size(-3) // 2)
            m2 = min(self.modes2, x_ft.size(-2) // 2)
            m3 = min(self.modes3, x_ft.size(-1))

            out_ft[:, :, :m1, :m2, :m3] = self._compl_mul3d("1", x_ft[:, :, :m1, :m2, :m3], self.weights1[:, :, :m1, :m2, :m3])
            out_ft[:, :, -m1:, :m2, :m3] = self._compl_mul3d("2", x_ft[:, :, -m1:, :m2, :m3], self.weights2[:, :, :m1, :m2, :m3])
            out_ft[:, :, :m1, -m2:, :m3] = self._compl_mul3d("3", x_ft[:, :, :m1, -m2:, :m3], self.weights3[:, :, :m1, -m2:, :m3])
            out_ft[:, :, -m1:, -m2:, :m3] = self._compl_mul3d("4", x_ft[:, :, -m1:, -m2:, :m3], self.weights4[:, :, :m1, -m2:, :m3])

            # Inverse 3D FFT back to spatial domain
            x_out = torch.fft.irfftn(out_ft, s=(x.size(-3), x.size(-2), x.size(-1)), dim=[-3, -2, -1])
            return x_out


    class FNO3D(nn.Module):
        """
        Complete 3D Fourier Neural Operator Model.
        Maps (dielectric / metal geometry volume, frequency) -> 3D Complex E-Field + S11.
        """
        def __init__(
            self,
            in_channels: int = 2,      # Channel 0: Permittivity epsilon, Channel 1: Frequency normalized
            out_channels: int = 6,     # Ex_re, Ey_re, Ez_re, Ex_im, Ey_im, Ez_im
            width: int = 32,           # Hidden feature channels
            modes: Tuple[int, int, int] = (8, 8, 8), # Truncated modes
            n_blocks: int = 4,
            sparam_bins: int = 11      # Number of frequency bins in S11 curve
        ):
            super().__init__()
            self.width = width
            self.modes = modes
            self.n_blocks = n_blocks

            # 1. Lifting linear layer: maps in_channels -> width
            self.lift = nn.Conv3d(in_channels, width, kernel_size=1)

            # 2. Fourier blocks with spectral conv and local skip connections
            self.spectral_convs = nn.ModuleList([
                SpectralConv3d(width, width, modes[0], modes[1], modes[2]) for _ in range(n_blocks)
            ])
            self.ws = nn.ModuleList([
                nn.Conv3d(width, width, kernel_size=1) for _ in range(n_blocks)
            ])

            # 3. Field projection head: maps width -> 6 complex field components
            self.field_proj1 = nn.Conv3d(width, width * 2, kernel_size=1)
            self.field_proj2 = nn.Conv3d(width * 2, out_channels, kernel_size=1)

            # 4. S-Parameter Head: Global pooling + MLP
            self.sparam_head = nn.Sequential(
                nn.AdaptiveAvgPool3d((1, 1, 1)),
                nn.Flatten(),
                nn.Linear(width, 128),
                nn.GELU(),
                nn.Linear(128, sparam_bins)
            )

        def forward(self, x: torch.Tensor) -> Tuple[torch.Tensor, torch.Tensor]:
            """
            x shape: (Batch, in_channels, Nx, Ny, Nz)
            Returns:
              - fields: (Batch, 6, Nx, Ny, Nz) [Ex_re, Ey_re, Ez_re, Ex_im, Ey_im, Ez_im]
              - s_params: (Batch, sparam_bins) [S11(f) in dB]
            """
            h = self.lift(x)

            for spectral_conv, w in zip(self.spectral_convs, self.ws):
                h1 = spectral_conv(h)
                h2 = w(h)
                h = F.gelu(h1 + h2)

            # Predict volumetric complex electric field
            f = F.gelu(self.field_proj1(h))
            fields = self.field_proj2(f)

            # Predict S-parameter curve
            s_params = self.sparam_head(h)

            return fields, s_params


def relative_l2_loss(pred: Any, target: Any) -> Any:
    """Computes normalized L2 error ||pred - target||_2 / ||target||_2."""
    if not HAS_TORCH:
        diff = np.linalg.norm(pred - target)
        norm = np.linalg.norm(target) + 1e-8
        return diff / norm
    diff = torch.norm(pred.view(pred.size(0), -1) - target.view(target.size(0), -1), dim=1)
    norm = torch.norm(target.view(target.size(0), -1), dim=1) + 1e-8
    return torch.mean(diff / norm)


class FNOModelWrapper:
    """
    Manager for training, evaluating, and running inference with FNO3D.
    Seamlessly handles PyTorch CPU/GPU devices and fallback modes.
    """
    def __init__(self, width: int = 32, modes: Tuple[int, int, int] = (8, 8, 8), device: Optional[str] = None):
        if not HAS_TORCH:
            self.model = None
            self.device = "cpu"
            print("Notice: PyTorch not found. FNOModelWrapper operating in mock mode.")
            return

        if device is None:
            self.device = "cuda" if torch.cuda.is_available() else "cpu"
        else:
            self.device = device

        self.model = FNO3D(in_channels=2, out_channels=6, width=width, modes=modes).to(self.device)
        self.optimizer = torch.optim.AdamW(self.model.parameters(), lr=1e-3, weight_decay=1e-4)
        self.scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(self.optimizer, T_max=100)

    def predict_field_and_sparam(self, voxel_grid: np.ndarray, freq_ghz: float = 2.45) -> Tuple[np.ndarray, np.ndarray]:
        """
        Takes a 3D geometry voxel grid (Nx, Ny, Nz) where 0=air, 1=dielectric, 2=metal
        and returns:
          - fields: (6, Nx, Ny, Nz)
          - s11_curve: (sparam_bins,)
        """
        if not HAS_TORCH or self.model is None:
            # Lightweight heuristic fallback
            nx, ny, nz = voxel_grid.shape
            fields = np.zeros((6, nx, ny, nz), dtype=np.float32)
            # Standing wave pattern
            x = np.linspace(-np.pi, np.pi, nx)
            y = np.linspace(-np.pi, np.pi, ny)
            z = np.linspace(-np.pi, np.pi, nz)
            gx, gy, gz = np.meshgrid(x, y, z, indexing="ij")
            fields[0] = np.sin(gx) * np.cos(gy)
            fields[1] = np.cos(gx) * np.sin(gy)
            fields[2] = np.sin(gz)
            s11 = -12.0 - 5.0 * np.sin(np.linspace(0, np.pi, 11))
            return fields, s11

        self.model.eval()
        with torch.no_grad():
            # Build 2-channel input: channel 0 = normalized material, channel 1 = freq
            chan0 = voxel_grid.astype(np.float32) / 2.0
            chan1 = np.full_like(chan0, freq_ghz / 10.0, dtype=np.float32)
            inp = np.stack([chan0, chan1], axis=0)
            inp_tensor = torch.from_numpy(inp).unsqueeze(0).to(self.device)

            fields_t, sparams_t = self.model(inp_tensor)
            fields = fields_t.squeeze(0).cpu().numpy()
            sparams = sparams_t.squeeze(0).cpu().numpy()
            return fields, sparams

    def train_step(self, voxel_batch: np.ndarray, freqs: np.ndarray, target_fields: np.ndarray, target_sparams: np.ndarray) -> float:
        """Runs a single optimization step."""
        if not HAS_TORCH or self.model is None:
            return 0.0

        self.model.train()
        self.optimizer.zero_grad()

        # Format input tensor: (B, 2, X, Y, Z)
        B, X, Y, Z = voxel_batch.shape
        inps = np.zeros((B, 2, X, Y, Z), dtype=np.float32)
        inps[:, 0, :, :, :] = voxel_batch / 2.0
        for i, f in enumerate(freqs):
            inps[i, 1, :, :, :] = f / 10.0

        inps_t = torch.from_numpy(inps).to(self.device)
        target_fields_t = torch.from_numpy(target_fields).to(self.device)
        target_sparams_t = torch.from_numpy(target_sparams).to(self.device)

        pred_fields, pred_sparams = self.model(inps_t)

        loss_fields = relative_l2_loss(pred_fields, target_fields_t)
        loss_sparams = F.mse_loss(pred_sparams, target_sparams_t)
        total_loss = loss_fields + 0.5 * loss_sparams

        total_loss.backward()
        self.optimizer.step()

        return float(total_loss.item())

    def save_checkpoint(self, path: str):
        if HAS_TORCH and self.model is not None:
            os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
            torch.save({
                "model_state": self.model.state_dict(),
                "optimizer_state": self.optimizer.state_dict()
            }, path)

    def load_checkpoint(self, path: str):
        if HAS_TORCH and self.model is not None and os.path.exists(path):
            ckpt = torch.load(path, map_location=self.device)
            self.model.load_state_dict(ckpt["model_state"])
            self.optimizer.load_state_dict(ckpt["optimizer_state"])
