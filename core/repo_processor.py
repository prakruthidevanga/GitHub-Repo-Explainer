from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

try:
    from git import Repo as GitPythonRepo
except ImportError:
    GitPythonRepo = None

IGNORED_DIRS = {
    ".git", ".github", ".gitlab", ".idea", ".vscode", "node_modules", "venv", ".venv", "env",
    "dist", "build", "target", "__pycache__", ".pytest_cache", ".mypy_cache", ".next", ".nuxt",
    "coverage", "site-packages", "vendor", "bin", "obj",
}
CODE_EXTENSIONS = {
    ".py", ".js", ".jsx", ".ts", ".tsx", ".java", ".kt", ".kts", ".go", ".rs", ".cpp", ".cc",
    ".cxx", ".c", ".h", ".hpp", ".cs", ".php", ".rb", ".swift", ".dart", ".scala", ".sh",
    ".bash", ".sql", ".html", ".css", ".scss", ".sass", ".vue", ".svelte", ".xml", ".json",
    ".yml", ".yaml", ".toml", ".ini", ".ipynb",
}
CONFIG_FILES = {
    "Dockerfile", "Makefile", "Procfile", "requirements.txt", "pyproject.toml", "package.json",
    "package-lock.json", "pnpm-lock.yaml", "yarn.lock", "pom.xml", "build.gradle", "settings.gradle",
    "Cargo.toml", "go.mod", "composer.json", "Gemfile", "environment.yml",
}
DOC_FILES = {"README.md", "README.rst", "README.txt"}
MAX_FILE_CHARS = 12000
MAX_TOTAL_CHARS = 36000
MAX_FILES = 24
MAX_DOC_CHARS = 7000
FULL_SCAN_FILE_CHARS = 18000

@dataclass
class RepositoryData:
    name: str
    url: str
    files: list[dict]
    total_chars: int
    truncated: bool
    language_hints: list[str]
    manifest: str
    documentation: str
    total_candidate_files: int


def validate_github_url(url: str) -> str:
    parsed = urlparse(url.strip())
    if parsed.scheme not in {"http", "https"} or parsed.netloc.lower() != "github.com":
        raise ValueError("Enter a public GitHub repository URL such as https://github.com/user/repository")
    parts = [p for p in parsed.path.strip("/").split("/") if p]
    if len(parts) < 2:
        raise ValueError("The URL must point to a GitHub repository.")
    return f"https://github.com/{parts[0]}/{parts[1]}"


def clone_repository(url: str) -> tuple[Path, str]:
    clean_url = validate_github_url(url)
    temp_dir = Path(tempfile.mkdtemp(prefix="github_explainer_"))
    destination = temp_dir / Path(urlparse(clean_url).path).name
    try:
        if GitPythonRepo is not None:
            try:
                GitPythonRepo.clone_from(clean_url, destination, depth=1)
                return destination, clean_url
            except Exception:
                pass
        subprocess.run(["git", "clone", "--depth", "1", clean_url, str(destination)], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=90)
        return destination, clean_url
    except Exception as exc:
        shutil.rmtree(temp_dir, ignore_errors=True)
        raise RuntimeError("Could not clone the repository. Make sure it is public and the URL is correct.") from exc


def _ignored(path: Path, root: Path) -> bool:
    return any(part in IGNORED_DIRS for part in path.relative_to(root).parts[:-1])


def _is_candidate(path: Path) -> bool:
    return path.name in CONFIG_FILES or path.suffix.lower() in CODE_EXTENSIONS


def _read_notebook(path: Path) -> str:
    notebook = json.loads(path.read_text(encoding="utf-8", errors="ignore"))
    cells = []
    for index, cell in enumerate(notebook.get("cells", []), start=1):
        if cell.get("cell_type") != "code":
            continue
        source = "".join(cell.get("source", []))
        if source.strip():
            cells.append(f"# --- code cell {index} ---\n{source.strip()}")
    return "\n\n".join(cells)


def _read(path: Path) -> str:
    if path.suffix.lower() == ".ipynb":
        return _read_notebook(path)
    return path.read_text(encoding="utf-8", errors="ignore")


def _priority(path: Path) -> tuple[int, int, str]:
    suffix = path.suffix.lower()
    if suffix == ".ipynb": return (0, 0, path.as_posix())
    if suffix in {".py", ".js", ".jsx", ".ts", ".tsx", ".java", ".go", ".rs", ".cpp", ".c", ".cs", ".php", ".rb", ".swift", ".dart", ".scala", ".html", ".css", ".vue", ".svelte", ".sql", ".sh"}: return (1, 0, path.as_posix())
    if path.name in CONFIG_FILES or suffix in {".json", ".yaml", ".yml", ".toml", ".xml", ".ini"}: return (2, 0, path.as_posix())
    if path.name in DOC_FILES: return (4, 0, path.as_posix())
    return (3, 0, path.as_posix())


def _inventory(root: Path, candidates: list[Path]) -> str:
    rows = []
    for p in candidates:
        try:
            text = _read(p)
            lines = text.count("\n") + (1 if text else 0)
            chars = len(text)
        except Exception:
            lines, chars = 0, 0
        kind = "notebook" if p.suffix.lower() == ".ipynb" else ("config" if p.name in CONFIG_FILES else "source")
        rows.append(f"- {p.relative_to(root).as_posix()} | {kind} | {lines} lines | {chars} chars")
    return "\n".join(rows[:80]) or "No supported files found."


def extract_source_files(root: Path, full_scan: bool = False) -> RepositoryData:
    candidates = [p for p in root.rglob("*") if p.is_file() and not _ignored(p, root) and _is_candidate(p)]
    candidates.sort(key=_priority)
    manifest = _inventory(root, candidates)
    documentation = ""
    for p in candidates:
        if p.name in DOC_FILES:
            try:
                documentation = _read(p)[:MAX_DOC_CHARS]
            except Exception:
                pass
            break

    selected, total, truncated = [], 0, False
    for path in candidates:
        if path.name in DOC_FILES:
            continue
        if not full_scan and len(selected) >= MAX_FILES:
            truncated = True
            break
        try:
            content = _read(path).strip()
        except Exception:
            continue
        if not content:
            continue
        if full_scan:
            # Cloud map-reduce mode keeps the complete supported repository in memory.
            # Large files are split into chunks later by cloud_llm, so nothing is silently dropped.
            if len(content) > FULL_SCAN_FILE_CHARS:
                truncated = True
            selected.append({"path": path.relative_to(root).as_posix(), "content": content})
            total += len(content)
            continue
        if len(content) > MAX_FILE_CHARS:
            content = content[:MAX_FILE_CHARS] + "\n... [file excerpt truncated]"
            truncated = True
        remaining = MAX_TOTAL_CHARS - total
        if remaining <= 0:
            truncated = True
            break
        if len(content) > remaining:
            content = content[:remaining] + "\n... [repository context truncated]"
            truncated = True
        selected.append({"path": path.relative_to(root).as_posix(), "content": content})
        total += len(content)
        if total >= MAX_TOTAL_CHARS:
            break

    if not selected:
        raise ValueError("No supported source-code or configuration files were found in this repository.")

    ext_map = {".py":"Python", ".ipynb":"Jupyter/Python", ".js":"JavaScript", ".ts":"TypeScript", ".java":"Java", ".go":"Go", ".rs":"Rust", ".html":"HTML", ".css":"CSS", ".php":"PHP", ".rb":"Ruby", ".sql":"SQL", ".json":"JSON", ".yml":"YAML", ".yaml":"YAML"}
    hints = []
    for item in selected:
        value = ext_map.get(Path(item["path"]).suffix.lower())
        if value and value not in hints: hints.append(value)
    return RepositoryData(root.name, "", selected, total, truncated, hints, manifest, documentation, len(candidates))


def prepare_repository(url: str, full_scan: bool = False) -> RepositoryData:
    root, clean_url = clone_repository(url)
    try:
        data = extract_source_files(root, full_scan=full_scan)
        data.url = clean_url
        return data
    finally:
        shutil.rmtree(root.parent, ignore_errors=True)


def build_code_context(data: RepositoryData) -> str:
    return "\n\n".join(f"===== FILE: {item['path']} =====\n{item['content']}" for item in data.files)
