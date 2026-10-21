"""Build a source-only handoff from explicit paths, excluding local credentials and data."""

import argparse
import hashlib
import os
import re
import stat
import subprocess
import sys
import zipfile
from pathlib import Path

from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[1]
ROOT_FILES = (
    ".env.example",
    ".gitignore",
    ".python-version",
    "README.md",
    "ARCHITECTURE.md",
    "ATTRIBUTIONS.md",
    "CONTRACT.md",
    "Makefile",
    "pyproject.toml",
    "uv.lock",
    "product.json",
)
TREES = {
    "src": {".py", ".json", ".md", ".mthds"},
    "tests": {".py", ".json"},
    "scripts": {".py"},
    "docs": {".md", ".json"},
    ".github/workflows": {".yml", ".yaml"},
    "frontend/src": {".ts", ".tsx", ".css"},
    "frontend/public": {".svg", ".png", ".ico"},
}
FRONTEND_FILES = (
    "package.json",
    "bun.lock",
    "index.html",
    "tsconfig.json",
    "vite.config.ts",
    "vitest.config.ts",
    "openapi.json",
    ".prettierignore",
)
IGNORED_DIRS = {"__pycache__", ".pytest_cache", ".ruff_cache", "node_modules", ".git"}
CREDENTIAL_PATTERN = re.compile(
    rb"sk-(?:proj-|svcacct-)?[A-Za-z0-9_-]{24,}|gh[pousr]_[A-Za-z0-9]{30,}"
    rb"|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"
)


def is_link(path: Path) -> bool:
    info = path.lstat()
    return path.is_symlink() or bool(
        getattr(info, "st_file_attributes", 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT
    )


def source_files(root: Path) -> list[Path]:
    """Fail closed on links and unexpected files inside publishable directories."""
    paths = [root / name for name in ROOT_FILES]
    paths.extend(root / "frontend" / name for name in FRONTEND_FILES)
    for folder, extensions in TREES.items():
        base = root / folder
        if not base.is_dir() or is_link(base):
            raise ValueError(f"Dossier source absent ou lien interdit : {folder}")
        for parent, directories, files in os.walk(base, followlinks=False):
            for name in directories:
                if is_link(Path(parent) / name):
                    raise ValueError("Lien interdit dans les sources")
            directories[:] = [name for name in directories if name not in IGNORED_DIRS]
            for name in files:
                path = Path(parent) / name
                if path.suffix not in extensions:
                    raise ValueError(f"Fichier inattendu : {path.relative_to(root)}")
                paths.append(path)
    for path in paths:
        if (
            not path.is_file()
            or is_link(path)
            or not path.resolve().is_relative_to(root.resolve())
        ):
            raise ValueError(
                f"Source absente ou lien interdit : {path.relative_to(root)}"
            )
    return sorted(paths, key=lambda path: path.relative_to(root).as_posix())


def configured_secrets(root: Path) -> list[bytes]:
    # Include overridden values from BOTH files, as well as exported credentials.
    sources = [os.environ]
    for name in (".env", ".Secrets"):
        if (root / name).is_file():
            sources.append(dotenv_values(root / name, encoding="utf-8-sig"))
    return list(
        {
            value.encode("utf-8")
            for values in sources
            for key, value in values.items()
            if value
            and len(value) >= 8
            and any(
                word in key.upper() for word in ("KEY", "TOKEN", "SECRET", "PASSWORD")
            )
        }
    )


def check_secrets(root: Path, paths: list[Path]) -> None:
    secrets = configured_secrets(root)
    exposed = []
    for path in paths:
        content = path.read_bytes()
        if CREDENTIAL_PATTERN.search(content) or any(
            value in content for value in secrets
        ):
            exposed.append(path.relative_to(root).as_posix())
    if exposed:
        raise ValueError("Possible identifier found in: " + ", ".join(exposed))
    if (root / ".git").exists():
        result = subprocess.run(
            ["git", "ls-files", "--cached", "-z"],
            cwd=root,
            capture_output=True,
            check=True,
        )
        tracked = set(result.stdout.decode("utf-8").split("\0")) - {""}
        allowed = {path.relative_to(root).as_posix() for path in paths}
        if tracked - allowed:
            raise ValueError(
                "Tracked files outside the release scope: "
                + ", ".join(sorted(tracked - allowed))
            )


def build_archive(root: Path, output: Path) -> Path:
    paths = source_files(root)
    check_secrets(root, paths)
    output.parent.mkdir(parents=True, exist_ok=True)
    manifest = []
    with zipfile.ZipFile(output, "x", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in paths:
            relative = path.relative_to(root).as_posix()
            content = path.read_bytes()
            entry = zipfile.ZipInfo(
                "quorumy/" + relative, date_time=(2026, 1, 1, 0, 0, 0)
            )
            entry.compress_type = zipfile.ZIP_DEFLATED
            entry.external_attr = 0o100644 << 16
            archive.writestr(entry, content)
            manifest.append(f"{hashlib.sha256(content).hexdigest()}  {relative}")
        entry = zipfile.ZipInfo(
            "quorumy/MANIFEST.sha256", date_time=(2026, 1, 1, 0, 0, 0)
        )
        entry.compress_type = zipfile.ZIP_DEFLATED
        entry.external_attr = 0o100644 << 16
        archive.writestr(entry, "\n".join(manifest) + "\n")
    digest = hashlib.sha256(output.read_bytes()).hexdigest()
    output.with_suffix(output.suffix + ".sha256").write_text(
        f"{digest}  {output.name}\n", encoding="utf-8"
    )
    return output


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    parser.add_argument(
        "--output", type=Path, default=ROOT / "release/quorumy-source.zip"
    )
    args = parser.parse_args()
    try:
        if args.check:
            paths = source_files(ROOT)
            check_secrets(ROOT, paths)
            print(f"OK: {len(paths)} source files checked; no known key detected.")
        else:
            print(build_archive(ROOT, args.output.resolve()))
    except (ValueError, OSError, subprocess.CalledProcessError) as exc:
        print(f"Remise interrompue : {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
