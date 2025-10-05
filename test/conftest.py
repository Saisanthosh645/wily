import pathlib
import shutil
import tempfile
import json
from textwrap import dedent

import pytest
from click.testing import CliRunner
from git.repo.base import Repo
from git.util import Actor

import wily.__main__ as main


# ---------------------- Helper Functions ---------------------- #

def git_commit(repo: Repo, file_path: pathlib.Path, message: str, author: Actor, committer: Actor,
               author_date: str, commit_date: str):
    """Add file to index and commit to git repo."""
    index = repo.index
    index.add([str(file_path)])
    index.commit(
        message,
        author=author,
        committer=committer,
        author_date=author_date,
        commit_date=commit_date,
    )


def run_cli(*args):
    """Run Wily CLI and assert success."""
    runner = CliRunner()
    result = runner.invoke(main.cli, list(args))
    assert result.exit_code == 0, result.stdout
    return result


def make_ipynb(cells):
    """Create a minimal notebook dictionary from a list of cells."""
    return {
        "cells": cells,
        "metadata": {
            "kernelspec": {
                "display_name": "Python 3",
                "language": "python",
                "name": "python3"
            },
            "language_info": {
                "name": "python",
                "version": "3.4.2"
            }
        },
        "nbformat": 4,
        "nbformat_minor": 0
    }


def make_code_cell(source):
    """Create a code cell dictionary for a notebook."""
    return {
        "cell_type": "code",
        "metadata": {},
        "source": source,
        "outputs": [],
        "execution_count": 0,
        "input": []
    }


# ---------------------- Fixtures ---------------------- #

@pytest.fixture
def gitdir(tmpdir) -> str:
    """Create a temporary Git repo with a Python test file and multiple commits."""
    tmppath = pathlib.Path(tmpdir)
    src_path = tmppath / "src"
    src_path.mkdir()
    test_file = src_path / "test.py"
    test_file.write_text("import abc")

    repo = Repo.init(path=tmpdir)
    author = Actor("An author", "author@example.com")
    committer = Actor("A committer", "committer@example.com")

    # Initial commit
    git_commit(repo, test_file, "basic test", author, committer,
               "Thu, 07 Apr 2019 22:13:13 +0200", "Thu, 07 Apr 2019 22:13:13 +0200")

    # Subsequent versions
    versions = [
        ("add line", """
            import abc
            foo = 1
            def function1():
                a = 1 + 1

            class Class1(object):
                def method(self):
                    b = 1 + 5
        """, "Mon, 10 Apr 2019 22:13:13 +0200"),
        ("remove line", """
            import abc
            foo = 1
            def function1():
                a = 1 + 1
            class Class1(object):
                def method(self):
                    b = 1 + 5
                    if b == 6:
                        return 'banana'
        """, "Thu, 14 Apr 2019 22:13:13 +0200")
    ]

    for message, content, date in versions:
        test_file.write_text(dedent(content))
        git_commit(repo, test_file, message, author, committer, date, date)

    yield str(tmpdir)
    repo.close()


@pytest.fixture
def builddir(gitdir):
    """Create a wily cache index for the gitdir project."""
    tmppath = pathlib.Path(gitdir)
    run_cli("--debug", "--path", gitdir, "build", str(tmppath / "src"))
    run_cli("--debug", "--path", gitdir, "index")

    yield gitdir

    run_cli("--debug", "--path", gitdir, "clean", "-y")


@pytest.fixture
def ipynbgitdir(tmpdir) -> str:
    """Create a temporary Git repo with a Jupyter notebook and multiple commits."""
    tmppath = pathlib.Path(tmpdir)
    src_path = tmppath / "src"
    src_path.mkdir()
    notebook_file = src_path / "test.ipynb"

    repo = Repo.init(path=tmpdir)
    author = Actor("An author", "author@example.com")
    committer = Actor("A committer", "committer@example.com")

    # Initial empty notebook
    empty_nb = make_ipynb([])
    notebook_file.write_text(json.dumps(empty_nb))
    git_commit(repo, notebook_file, "empty notebook", author, committer,
               "Thu, 07 Apr 2019 22:13:13 +0200", "Thu, 07 Apr 2019 22:13:13 +0200")

    # Notebook version 1
    nb_v1 = make_ipynb([
        make_code_cell([
            "import abc\n",
            "foo = 1\n",
            "def function1():\n    a = 1 + 1\n",
            "class Class1(object):\n    def method(self):\n        b = 1 + 5\n"
        ])
    ])
    notebook_file.write_text(json.dumps(nb_v1))
    git_commit(repo, notebook_file, "single cell", author, committer,
               "Mon, 10 Apr 2019 22:13:13 +0200", "Mon, 10 Apr 2019 22:13:13 +0200")

    # Notebook version 2
    nb_v2 = make_ipynb([
        make_code_cell([
            "import abc\nfoo = 1\ndef function1():\n    a = 1 + 1\nclass Class1(object):\n"
            "    def method(self):\n        b = 1 + 5\n        if b == 6:\n            return 'banana'\n"
        ]),
        make_code_cell([
            "foo = 1\nclass Class1(object):\n    def method(self):\n        b = 1 + 5\n"
            "        if b == 6:\n            return 'banana'\n"
        ])
    ])
    notebook_file.write_text(json.dumps(nb_v2))
    git_commit(repo, notebook_file, "second cell", author, committer,
               "Thu, 14 Apr 2019 22:13:13 +0200", "Thu, 14 Apr 2019 22:13:13 +0200")

    yield str(tmpdir)
    repo.close()


@pytest.fixture
def ipynbbuilddir(ipynbgitdir):
    """Convert an ipynbgitdir repo into a wily cache index."""
    tmppath = pathlib.Path(ipynbgitdir)
    config = """
    [wily]
    include_ipynb = true
    ipynb_cells = true
    """
    (tmppath / "wily.cfg").write_text(config)

    run_cli("--debug", "--path", ipynbgitdir, "build", str(tmppath / "src"))
    run_cli("--debug", "--path", ipynbgitdir, "index")

    yield ipynbgitdir

    run_cli("--debug", "--path", ipynbgitdir, "clean", "-y")


@pytest.fixture(autouse=True)
def cache_path(monkeypatch):
    """Configure wily cache and home path, clean up after test."""
    tmp = tempfile.mkdtemp()
    monkeypatch.setenv("HOME", tmp)
    yield tmp
    shutil.rmtree(tmp)
