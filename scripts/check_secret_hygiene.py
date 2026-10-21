"""Check publishable sources without displaying credential values."""

import subprocess

from release import ROOT, check_secrets, source_files


def main() -> int:
    try:
        paths = source_files(ROOT)
        check_secrets(ROOT, paths)
    except (ValueError, OSError, subprocess.CalledProcessError) as exc:
        print(f"Failed: {exc}")
        return 1
    print(f"OK: {len(paths)} files, no configured key or known signature detected.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
