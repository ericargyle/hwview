"""Simple Hardware Viewer

Standalone Windows GUI that displays CPU, GPU, and RAM details.
- CPU/RAM via psutil + py-cpuinfo
- GPU via WMI on Windows (fallback text if unavailable)

Build EXE:
  py -m pip install -r requirements.txt
  py -m pip install pyinstaller
  py -m PyInstaller --onefile --windowed --name hwview src/hwview.py
"""

from __future__ import annotations

import os
import platform
import sys
import tkinter as tk
from tkinter import ttk

import psutil
import cpuinfo


def _fmt_bytes(n: int) -> str:
    step = 1024.0
    v = float(n)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if v < step:
            return f"{v:.1f} {unit}" if unit != "B" else f"{int(v)} {unit}"
        v /= step
    return f"{v:.1f} PB"


def get_cpu_details() -> dict:
    info = cpuinfo.get_cpu_info()
    brand = info.get("brand_raw") or info.get("brand") or platform.processor() or "Unknown"
    arch = info.get("arch") or platform.machine() or "Unknown"
    hz = info.get("hz_advertised_friendly") or info.get("hz_advertised") or "Unknown"
    cores_physical = psutil.cpu_count(logical=False) or 0
    cores_logical = psutil.cpu_count(logical=True) or 0
    return {
        "Name": str(brand),
        "Arch": str(arch),
        "Advertised": str(hz),
        "Cores (physical)": str(cores_physical),
        "Cores (logical)": str(cores_logical),
    }


def get_ram_details() -> dict:
    vm = psutil.virtual_memory()
    return {
        "Total": _fmt_bytes(vm.total),
        "Available": _fmt_bytes(vm.available),
        "Used": _fmt_bytes(vm.used),
        "Percent": f"{vm.percent:.0f}%",
    }


def get_gpu_details() -> list[dict]:
    # Windows WMI: Win32_VideoController
    if platform.system().lower() != "windows":
        return [{"Name": "(GPU details only available on Windows in this build)", "VRAM": "—"}]

    try:
        import wmi  # type: ignore

        c = wmi.WMI()
        gpus = []
        for vc in c.Win32_VideoController():
            name = getattr(vc, "Name", None) or "Unknown"
            ram = getattr(vc, "AdapterRAM", None)
            vram = _fmt_bytes(int(ram)) if ram is not None else "—"
            driver = getattr(vc, "DriverVersion", None) or "—"
            status = getattr(vc, "Status", None) or "—"
            gpus.append({"Name": str(name), "VRAM": vram, "Driver": str(driver), "Status": str(status)})
        return gpus or [{"Name": "(No GPU detected via WMI)", "VRAM": "—"}]
    except Exception as e:
        return [{"Name": f"(GPU lookup failed: {e.__class__.__name__})", "VRAM": "—"}]


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Simple Hardware Viewer")
        self.geometry("700x520")
        self.minsize(640, 480)

        self.style = ttk.Style(self)
        try:
            self.style.theme_use("vista")
        except Exception:
            pass

        root = ttk.Frame(self, padding=14)
        root.pack(fill="both", expand=True)

        title = ttk.Label(root, text="Simple Hardware Viewer", font=("Segoe UI", 18, "bold"))
        title.pack(anchor="w")

        sub = ttk.Label(
            root,
            text=f"OS: {platform.system()} {platform.release()}   |   Python: {platform.python_version()}",
            foreground="#555",
        )
        sub.pack(anchor="w", pady=(2, 12))

        self.nb = ttk.Notebook(root)
        self.nb.pack(fill="both", expand=True)

        self.cpu_tab = ttk.Frame(self.nb, padding=12)
        self.gpu_tab = ttk.Frame(self.nb, padding=12)
        self.ram_tab = ttk.Frame(self.nb, padding=12)
        self.live_tab = ttk.Frame(self.nb, padding=12)

        self.nb.add(self.cpu_tab, text="CPU")
        self.nb.add(self.gpu_tab, text="GPU")
        self.nb.add(self.ram_tab, text="RAM")
        self.nb.add(self.live_tab, text="Live")

        self.cpu_tree = self._kv_table(self.cpu_tab)
        self.ram_tree = self._kv_table(self.ram_tab)

        self.gpu_text = tk.Text(self.gpu_tab, height=14, wrap="word")
        self.gpu_text.pack(fill="both", expand=True)
        self.gpu_text.configure(state="disabled")

        self.live = ttk.Label(self.live_tab, text="", font=("Consolas", 14))
        self.live.pack(anchor="w")

        btns = ttk.Frame(root)
        btns.pack(fill="x", pady=(12, 0))

        ttk.Button(btns, text="Refresh", command=self.refresh_all).pack(side="left")
        ttk.Button(btns, text="Copy Summary", command=self.copy_summary).pack(side="left", padx=(8, 0))

        self.status = ttk.Label(btns, text="", foreground="#555")
        self.status.pack(side="right")

        self.refresh_all()
        self.after(500, self._tick_live)

    def _kv_table(self, parent: ttk.Frame) -> ttk.Treeview:
        tree = ttk.Treeview(parent, columns=("k", "v"), show="headings", height=12)
        tree.heading("k", text="Field")
        tree.heading("v", text="Value")
        tree.column("k", width=220, anchor="w")
        tree.column("v", width=420, anchor="w")
        tree.pack(fill="both", expand=True)
        return tree

    def _set_kv(self, tree: ttk.Treeview, d: dict):
        tree.delete(*tree.get_children())
        for k, v in d.items():
            tree.insert("", "end", values=(k, v))

    def refresh_all(self):
        self._set_kv(self.cpu_tree, get_cpu_details())
        self._set_kv(self.ram_tree, get_ram_details())

        gpus = get_gpu_details()
        lines = []
        for i, g in enumerate(gpus, start=1):
            lines.append(f"GPU {i}")
            for k in ("Name", "VRAM", "Driver", "Status"):
                if k in g:
                    lines.append(f"  {k}: {g[k]}")
            lines.append("")

        self.gpu_text.configure(state="normal")
        self.gpu_text.delete("1.0", "end")
        self.gpu_text.insert("1.0", "\n".join(lines).strip() + "\n")
        self.gpu_text.configure(state="disabled")

        self.status.configure(text="Refreshed")

    def _tick_live(self):
        try:
            cpu = psutil.cpu_percent(interval=None)
            vm = psutil.virtual_memory()
            self.live.configure(text=f"CPU: {cpu:5.1f}%   RAM: {vm.percent:5.1f}%   (Total: {_fmt_bytes(vm.total)})")
        except Exception:
            pass
        self.after(750, self._tick_live)

    def copy_summary(self):
        cpu = get_cpu_details()
        ram = get_ram_details()
        gpus = get_gpu_details()

        parts = [
            "Simple Hardware Viewer",
            f"OS: {platform.system()} {platform.release()} ({platform.version()})",
            "",
            "CPU:",
        ]
        for k, v in cpu.items():
            parts.append(f"- {k}: {v}")
        parts.append("")
        parts.append("RAM:")
        for k, v in ram.items():
            parts.append(f"- {k}: {v}")
        parts.append("")
        parts.append("GPU:")
        for i, g in enumerate(gpus, start=1):
            parts.append(f"- GPU {i}: {g.get('Name','Unknown')} ({g.get('VRAM','—')})")

        text = "\n".join(parts)
        self.clipboard_clear()
        self.clipboard_append(text)
        self.status.configure(text="Copied to clipboard")


def main():
    app = App()
    app.mainloop()


if __name__ == "__main__":
    main()
