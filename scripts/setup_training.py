#!/usr/bin/env python3
"""Install prototype training/eval dependencies on a compute machine.

The root ``requirements.txt`` stays focused on data collection. This script
installs the heavier Hugging Face / PyTorch stack from ``requirements-compute``
into a training virtualenv by default.
"""

from __future__ import annotations

import argparse
import os
import shlex
import shutil
import subprocess
import sys
from pathlib import Path


DEFAULT_REQ_FILE = "requirements-compute.txt"
DEFAULT_TORCH_PACKAGE = "torch"
DEFAULT_VENV_DIR = ".venv-training"


def env_flag(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in {"1", "true", "yes", "on"}


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def print_command(cmd: list[str]) -> None:
    print("+", " ".join(shlex.quote(part) for part in cmd))


def run(cmd: list[str], *, dry_run: bool) -> None:
    if dry_run:
        print_command(cmd)
        return
    subprocess.run(cmd, check=True)


def display_path(path: Path, root: Path) -> Path:
    try:
        return path.relative_to(root)
    except ValueError:
        return path


def venv_python(venv_dir: Path) -> Path:
    if os.name == "nt":
        return venv_dir / "Scripts" / "python.exe"
    return venv_dir / "bin" / "python"


def ensure_venv(venv_dir: Path, python: str, *, dry_run: bool) -> Path:
    pyvenv_cfg = venv_dir / "pyvenv.cfg"
    if venv_dir.exists() and not pyvenv_cfg.is_file():
        raise SystemExit(
            f"error: {venv_dir} exists but is not a Python venv. Refusing to touch it."
        )

    if venv_dir.exists():
        print(f">> reusing existing venv at {venv_dir}")
    else:
        print(f">> creating venv at {venv_dir}")
        run([python, "-m", "venv", str(venv_dir)], dry_run=dry_run)

    return venv_python(venv_dir)


def report_gpu() -> None:
    nvidia_smi = shutil.which("nvidia-smi")
    if not nvidia_smi:
        print(">> note: nvidia-smi not found; installing deps anyway")
        return

    print(">> detected NVIDIA runtime:")
    result = subprocess.run(
        [
            nvidia_smi,
            "--query-gpu=name,driver_version,memory.total",
            "--format=csv,noheader",
        ],
        check=False,
    )
    if result.returncode != 0:
        print(">> warning: nvidia-smi failed; continuing with dependency install")


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Install Hawaiian LLM prototype training/eval dependencies."
    )
    parser.add_argument(
        "--python",
        default=os.environ.get("PYTHON", sys.executable),
        help="Python executable used to create the venv (default: current Python).",
    )
    parser.add_argument(
        "--venv-dir",
        default=os.environ.get("VENV_DIR", DEFAULT_VENV_DIR),
        help=f"Virtualenv path to create/reuse (default: {DEFAULT_VENV_DIR}).",
    )
    parser.add_argument(
        "--requirements",
        default=os.environ.get("REQ_FILE", DEFAULT_REQ_FILE),
        help=f"Compute requirements file (default: {DEFAULT_REQ_FILE}).",
    )
    parser.add_argument(
        "--torch-package",
        default=os.environ.get("TORCH_PACKAGE", DEFAULT_TORCH_PACKAGE),
        help=f"Torch requirement spec (default: {DEFAULT_TORCH_PACKAGE}).",
    )
    parser.add_argument(
        "--torch-index-url",
        default=os.environ.get("TORCH_INDEX_URL"),
        help=(
            "Optional PyTorch wheel index, e.g. "
            "https://download.pytorch.org/whl/cu121"
        ),
    )
    parser.add_argument(
        "--skip-torch",
        action="store_true",
        default=env_flag("SKIP_TORCH"),
        help="Skip installing torch, useful on provider images that preinstall it.",
    )
    parser.add_argument(
        "--no-venv",
        action="store_true",
        default=env_flag("NO_VENV"),
        help="Install into the current Python environment instead of creating a venv.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=env_flag("DRY_RUN"),
        help="Print install commands without running them.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    root = repo_root()
    req_file = (root / args.requirements).resolve()

    if not req_file.is_file():
        raise SystemExit(f"error: {req_file} not found")

    os.chdir(root)
    report_gpu()

    if args.no_venv:
        install_python = sys.executable
        print(f">> installing into current Python environment: {install_python}")
    else:
        install_python = str(
            ensure_venv(root / args.venv_dir, args.python, dry_run=args.dry_run)
        )

    print(">> upgrading pip / wheel / setuptools")
    run(
        [install_python, "-m", "pip", "install", "--upgrade", "pip", "wheel", "setuptools"],
        dry_run=args.dry_run,
    )

    if args.skip_torch:
        print(">> skipping torch install")
    else:
        print(">> installing torch")
        torch_cmd = [install_python, "-m", "pip", "install"]
        if args.torch_index_url:
            torch_cmd.extend(["--index-url", args.torch_index_url])
        torch_cmd.append(args.torch_package)
        run(torch_cmd, dry_run=args.dry_run)

    print(f">> installing {display_path(req_file, root)}")
    run(
        [install_python, "-m", "pip", "install", "-r", str(req_file)],
        dry_run=args.dry_run,
    )

    print(">> checking installed package metadata")
    run([install_python, "-m", "pip", "check"], dry_run=args.dry_run)

    print()
    if args.dry_run:
        print("dry run complete; no packages were installed.")
    elif args.no_venv:
        print("done. Dependencies were installed into the current Python environment.")
    else:
        print("done. Activate with:")
        print(f"    . {args.venv_dir}/bin/activate")

    if not args.dry_run:
        print()
        print("For gated Hugging Face models such as Llama-3.1-8B, also run:")
        print("    huggingface-cli login")
        print("or set HF_TOKEN in the compute environment.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
