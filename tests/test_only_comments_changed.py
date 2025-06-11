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


def test_docstring_only(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = setup_repo(tmp_path)
    (repo / "file.py").write_text('"""a"""\nprint("hi")\n')
    git(repo, "add", "file.py")
    git(repo, "commit", "-m", "add docstring")
    (repo / "file.py").write_text('"""b"""\nprint("hi")\n')
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


def test_module_docstring_change(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = setup_repo(tmp_path)
    (repo / "file.py").write_text('"""hi"""\nprint("hi")\n')
    git(repo, "add", "file.py")
    git(repo, "commit", "-m", "add docstring")
    (repo / "file.py").write_text('"""bye"""\nprint("hi")\n')
    git(repo, "add", "file.py")
    monkeypatch.chdir(repo)
    assert only_comments_changed("HEAD")


def test_function_docstring_change(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = setup_repo(tmp_path)
    (repo / "file.py").write_text('def f():\n    """hi"""\n    pass\n')
    git(repo, "add", "file.py")
    git(repo, "commit", "-m", "add func doc")
    (repo / "file.py").write_text('def f():\n    """bye"""\n    pass\n')
    git(repo, "add", "file.py")
    monkeypatch.chdir(repo)
    assert only_comments_changed("HEAD")


def test_triple_quoted_string_not_docstring(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = setup_repo(tmp_path)
    (repo / "file.py").write_text('data = """hi"""\nprint(data)\n')
    git(repo, "add", "file.py")
    git(repo, "commit", "-m", "init triple string")
    (repo / "file.py").write_text('data = """bye"""\nprint(data)\n')
    git(repo, "add", "file.py")
    monkeypatch.chdir(repo)
    assert not only_comments_changed("HEAD")
