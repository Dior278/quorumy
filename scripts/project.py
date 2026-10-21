"""Cross-platform setup and checks, from a checkout or an extracted source archive."""

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run(*args: str) -> None:
    executable = shutil.which(args[0])
    if not executable:
        raise RuntimeError(f"{args[0]} is not on PATH. See the README requirements.")
    print(f"> {' '.join(args)}", flush=True)
    subprocess.run([executable, *args[1:]], cwd=ROOT, check=True)


def setup() -> None:
    for name in ("uv", "bun", "node"):
        run(name, "--version")
    run("uv", "sync", "--locked")
    run("bun", "install", "--cwd", "frontend", "--frozen-lockfile")
    run("bun", "run", "--cwd", "frontend", "build")
    if not any((ROOT / name).exists() for name in (".env", ".Secrets")):
        shutil.copyfile(ROOT / ".env.example", ROOT / ".env")
        print(".env created: set HF_TOKEN, or add the key in the Quorumy account.")
    run("uv", "run", "--locked", "python", "scripts/project.py", "doctor")
    print("Setup complete. Start with: uv run --locked quorumy")


def doctor() -> None:
    from quorumy.settings import AppSettings
    from quorumy.workspace.config import load_config, load_product

    for name in ("uv", "bun", "node"):
        run(name, "--version")
    print(f"Python {sys.version.split()[0]}")
    try:
        settings = AppSettings()
        load_product()
        load_config()
    except Exception as exc:
        # Validation errors can embed environment values; never echo them.
        raise RuntimeError(
            f"Invalid configuration ({type(exc).__name__}). "
            "Compare .env and .data/config.json with the documented examples."
        ) from None
    frontend = Path(os.environ.get("QUORUMY_FRONTEND_DIR", ROOT / "frontend/dist"))
    if not (frontend / "index.html").is_file():
        raise RuntimeError("Interface missing. Run: bun run --cwd frontend build")
    print("Configuration and built interface: OK")
    print(
        "Hugging Face: "
        + ("key present" if settings.key("hf_token") else "key missing")
    )
    print("Present keys are not tested against providers.")
    print("Without a Hugging Face key, an account can still supply one.")


def check() -> None:
    (ROOT / "tmp").mkdir(exist_ok=True)
    # Own the test scratch directory; never depend on another checkout's temp ACLs.
    with tempfile.TemporaryDirectory(prefix="pytest-", dir=ROOT / "tmp") as temporary:
        run(
            "uv",
            "run",
            "--locked",
            "pytest",
            "-q",
            "-p",
            "no:cacheprovider",
            "--basetemp",
            str(Path(temporary) / "cases"),
        )
    run("uv", "run", "--locked", "ruff", "check", "src", "tests", "scripts")
    run("uv", "run", "--locked", "ruff", "format", "--check", "src", "tests", "scripts")
    run("bun", "run", "--cwd", "frontend", "format:check")
    run("bun", "run", "--cwd", "frontend", "test")
    run("bun", "run", "--cwd", "frontend", "build")
    run("uv", "run", "--locked", "python", "scripts/check_secret_hygiene.py")
    paths = [ROOT / "frontend/openapi.json", ROOT / "frontend/src/protocol.gen.ts"]
    before = {path: path.read_bytes() for path in paths}
    try:
        run("uv", "run", "--locked", "python", "scripts/export_workspace_protocol.py")
        run("bun", "run", "--cwd", "frontend", "generate:protocol")
        if any(
            path.read_bytes().replace(b"\r\n", b"\n") != data.replace(b"\r\n", b"\n")
            for path, data in before.items()
        ):
            raise RuntimeError(
                "Generated contract is stale: regenerate openapi.json and protocol.gen.ts "
                "with the two commands printed above."
            )
    finally:
        for path, data in before.items():
            path.write_bytes(data)
    print("Checks passed, with no calls to AI providers.")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("setup", "doctor", "check"))
    args = parser.parse_args()
    os.chdir(ROOT)
    try:
        {"setup": setup, "doctor": doctor, "check": check}[args.command]()
    except (RuntimeError, OSError, subprocess.CalledProcessError) as exc:
        print(f"Failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
