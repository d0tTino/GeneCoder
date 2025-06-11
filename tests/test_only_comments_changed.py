import subprocess
from pathlib import Path

import pytest

from scripts.only_comments_changed import only_comments_changed


def git(cwd: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=cwd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)


def setup_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    git(repo, "init")
    git(repo, "config", "user.email", "test@example.com")
    git(repo, "config", "user.name", "Test")
    (repo / "file.py").write_text("print('hi')\n")
    git(repo, "add", "file.py")
    git(repo, "commit", "-m", "init")
    return repo


def test_python_comment_only(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = setup_repo(tmp_path)
    (repo / "file.py").write_text("print('hi')\n# comment\n")
    git(repo, "add", "file.py")
    monkeypatch.chdir(repo)
    assert only_comments_changed("HEAD")


def test_docs_only(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = setup_repo(tmp_path)
    docs = repo / "docs"
    docs.mkdir()
    (docs / "index.md").write_text("# docs\n")
    git(repo, "add", "docs/index.md")
    monkeypatch.chdir(repo)
    assert only_comments_changed("HEAD")


def test_python_code_change(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = setup_repo(tmp_path)
    (repo / "file.py").write_text("print('bye')\n")
    git(repo, "add", "file.py")
    monkeypatch.chdir(repo)
    assert not only_comments_changed("HEAD")


def test_other_file_change(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = setup_repo(tmp_path)
    (repo / "config.yml").write_text("a: 1\n")
    git(repo, "add", "config.yml")
    monkeypatch.chdir(repo)
    assert not only_comments_changed("HEAD")
