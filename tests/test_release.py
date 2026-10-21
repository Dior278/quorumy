"""Protect the handoff boundary: private files never enter the source archive."""

import hashlib
import zipfile
from uuid import uuid4

import pytest
from scripts.release import ROOT, build_archive, check_secrets, source_files


@pytest.fixture
def checkout(tmp_path):
    for source in source_files(ROOT):
        target = tmp_path / source.relative_to(ROOT)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(source.read_bytes())
    return tmp_path


def test_archive_excludes_local_state_and_has_verified_manifest(checkout):
    marker = uuid4().hex
    for name in (
        ".env",
        ".Secrets",
        ".data/meeting.sqlite3",
        "tmp/private.log",
        "frontend/node_modules/private.js",
        "frontend/dist/index.html",
    ):
        path = checkout / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(marker, encoding="utf-8")
    target = build_archive(checkout, checkout / "release/first.zip")
    second = build_archive(checkout, checkout / "release/second.zip")
    assert target.read_bytes() == second.read_bytes()
    with zipfile.ZipFile(target) as archive:
        assert archive.testzip() is None
        assert not any(
            marker.encode() in archive.read(name) for name in archive.namelist()
        )
        for line in archive.read("quorumy/MANIFEST.sha256").decode().splitlines():
            digest, name = line.split("  ", 1)
            assert hashlib.sha256(archive.read("quorumy/" + name)).hexdigest() == digest
        assert "quorumy/.env.example" in archive.namelist()
        assert "quorumy/.github/workflows/quality.yml" in archive.namelist()
    with pytest.raises(FileExistsError):
        build_archive(checkout, target)


@pytest.mark.parametrize("origin", (".env", ".Secrets", "environment"))
def test_leaked_configured_secret_blocks_export_without_printing_it(
    checkout, monkeypatch, origin
):
    value = "fictional-credential-for-export-test"
    if origin == "environment":
        monkeypatch.setenv("CUSTOM_API_KEY", value)
    else:
        (checkout / origin).write_text(f"CUSTOM_API_KEY={value}\n", encoding="utf-8")
    (checkout / "docs/leak.md").write_text(value, encoding="utf-8")
    target = checkout / "release/source.zip"
    with pytest.raises(ValueError, match="docs/leak.md") as error:
        build_archive(checkout, target)
    assert value not in str(error.value)
    assert not target.exists()


def test_unexpected_file_in_source_tree_is_rejected(checkout):
    (checkout / "src/.env").write_text("private", encoding="utf-8")
    with pytest.raises(ValueError, match="inattendu"):
        source_files(checkout)


def test_known_credential_signature_is_rejected_without_local_configuration(checkout):
    path = checkout / "docs/leak.md"
    path.write_text("sk-" + "x" * 32, encoding="utf-8")
    with pytest.raises(ValueError, match="docs/leak.md"):
        check_secrets(checkout, [path])


def test_source_link_is_rejected(checkout, tmp_path):
    link = checkout / "src/leak.py"
    try:
        link.symlink_to(tmp_path / "README.md")
    except OSError:
        pytest.skip(
            "Creating symlinks requires permission on this Windows installation"
        )
    with pytest.raises(ValueError, match="lien interdit"):
        source_files(checkout)
