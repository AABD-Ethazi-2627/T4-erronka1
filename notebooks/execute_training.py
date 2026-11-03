"""Notebooka exekutatu eta grafikoak/taulak irteeretan gorde.

Proiektuaren errotik: python notebooks/execute_training.py
Uneko Python interpretea erabiltzen da kernel gisa (.venv erabiltzea gomendatua).
"""

from pathlib import Path
import os
import sys

import nbformat
from nbclient import NotebookClient
from jupyter_client import KernelManager


ROOT = Path(__file__).resolve().parent.parent
NOTEBOOK = ROOT / "notebooks" / "02_training.ipynb"


def main() -> None:
    # Erabiltzailearen karpeta orokorretan konfiguraziorik sortu ez dadin.
    runtime = ROOT / "reports" / ".jupyter-runtime"
    runtime.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("IPYTHONDIR", str(runtime / "ipython"))
    os.environ.setdefault("JUPYTER_CONFIG_DIR", str(runtime / "config"))
    os.environ.setdefault("JUPYTER_RUNTIME_DIR", str(runtime))
    notebook = nbformat.read(NOTEBOOK, as_version=4)
    nbformat.validate(notebook)
    manager = KernelManager(kernel_name="python3")
    # Ez erabili sistemako Python bat ustekabean: exekutatzailearen .venv bera.
    manager.kernel_spec.argv = [sys.executable, "-m", "ipykernel_launcher", "-f", "{connection_file}"]
    client = NotebookClient(
        notebook, km=manager, timeout=600,
        resources={"metadata": {"path": str(ROOT)}},
        allow_errors=False,
    )
    # Kerneleko aldi baterako fitxategiak proiektuaren karpetan gorde.
    manager.connection_file = str(runtime / "training-kernel.json")
    try:
        client.execute()
    finally:
        if manager.has_kernel:
            manager.shutdown_kernel(now=True)
        manager.cleanup_resources()
    nbformat.validate(notebook)
    nbformat.write(notebook, NOTEBOOK)
    code_cells = [cell for cell in notebook.cells if cell.cell_type == "code"]
    images = sum("image/png" in output.get("data", {}) for cell in code_cells for output in cell.outputs)
    print(f"Notebooka gordeta: {NOTEBOOK}")
    print(f"Exekutatutako kode-gelaxkak: {len(code_cells)}; PNG irteerak: {images}")


if __name__ == "__main__":
    main()
