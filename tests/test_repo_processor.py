import json
from pathlib import Path

from core.repo_processor import build_code_context, extract_source_files, validate_github_url


def test_validate_url():
    assert validate_github_url("https://github.com/user/repo") == "https://github.com/user/repo"


def test_notebook_code_is_extracted(tmp_path: Path):
    nb = {
        "cells": [
            {"cell_type": "markdown", "source": ["# Documentation"]},
            {"cell_type": "code", "source": ["import pandas as pd\n", "print('hello')\n"]},
        ]
    }
    (tmp_path / "demo.ipynb").write_text(json.dumps(nb), encoding="utf-8")
    data = extract_source_files(tmp_path)
    context = build_code_context(data)
    assert "import pandas as pd" in context
    assert "Documentation" not in context


def test_code_is_prioritized_over_readme(tmp_path: Path):
    (tmp_path / "README.md").write_text("long documentation", encoding="utf-8")
    (tmp_path / "app.py").write_text("print('implementation')", encoding="utf-8")
    data = extract_source_files(tmp_path)
    assert data.files[0]["path"] == "app.py"
