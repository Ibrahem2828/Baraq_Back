#!/usr/bin/env python3
"""Dependency-free static release gate for the Baraq backend source tree."""
from __future__ import annotations

import ast
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKIP_DIRS = {'.git', '.venv', 'venv', '__pycache__', 'staticfiles', 'media'}
FORBIDDEN_NAMES = {'.env', 'db.sqlite3', 'db.sqlite3-journal'}
SECRET_PATTERNS = [
    re.compile(r'\bsk-[A-Za-z0-9_-]{20,}\b'),
    re.compile(r'OPENAI_[A-Z_]*API_KEY\s*=\s*(?!replace|$)[^\s]+', re.I),
    re.compile(r'SECRET_KEY\s*=\s*["\']django-insecure-[^"\']+', re.I),
]


def iter_files(pattern='*'):
    for path in ROOT.rglob(pattern):
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        yield path


def fail(errors, message):
    errors.append(message)


def tracked_paths():
    """Return Git-tracked paths, or None when the source is not a Git checkout.

    Local ``.env`` files and transient SQLite databases are intentionally
    ignored by Git and Docker. They must not make a source-tree release check
    fail, while the same files remain forbidden when they are actually staged
    for release. A non-Git export retains the conservative old behaviour.
    """

    try:
        result = subprocess.run(
            ['git', 'ls-files', '-z'],
            cwd=ROOT,
            check=True,
            capture_output=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    return {
        Path(value.decode('utf-8'))
        for value in result.stdout.split(b'\0')
        if value
    }


def validate_python(errors):
    modules = {}
    py_files = list(iter_files('*.py'))
    for path in py_files:
        try:
            tree = ast.parse(path.read_text(encoding='utf-8'), filename=str(path))
        except Exception as exc:
            fail(errors, f'Python parse failed: {path.relative_to(ROOT)}: {exc}')
            continue
        module_name = '.'.join(path.relative_to(ROOT).with_suffix('').parts)
        if module_name.endswith('.__init__'):
            module_name = module_name[:-9]
        modules[module_name] = path
        for node in ast.walk(tree):
            if isinstance(node, (ast.Module, ast.ClassDef)):
                seen = {}
                for item in getattr(node, 'body', []):
                    if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                        seen.setdefault(item.name, []).append(item.lineno)
                for name, lines in seen.items():
                    if len(lines) > 1:
                        owner = getattr(node, 'name', '<module>')
                        fail(errors, f'Duplicate definition: {path.relative_to(ROOT)}:{owner}.{name} lines={lines}')
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == 'register':
                if len(node.args) > 2:
                    fail(errors, f'Router register has too many positional arguments: {path.relative_to(ROOT)}:{node.lineno}')

    for path in py_files:
        try:
            tree = ast.parse(path.read_text(encoding='utf-8'))
        except Exception:
            continue
        current_parts = path.relative_to(ROOT).with_suffix('').parts
        current_package = list(current_parts[:-1])
        if current_parts[-1] == '__init__':
            current_package = list(current_parts[:-1])
        for node in ast.walk(tree):
            if not isinstance(node, ast.ImportFrom) or node.level == 0:
                continue
            base = current_package[: max(0, len(current_package) - node.level + 1)]
            target = base + (node.module.split('.') if node.module else [])
            candidate_file = ROOT.joinpath(*target).with_suffix('.py')
            candidate_package = ROOT.joinpath(*target, '__init__.py')
            if not candidate_file.exists() and not candidate_package.exists():
                fail(errors, f'Unresolved relative import: {path.relative_to(ROOT)}:{node.lineno}')
    return len(py_files)


def validate_hygiene(errors):
    tracked = tracked_paths()
    for path in iter_files('*'):
        relative_path = path.relative_to(ROOT)
        is_release_file = tracked is None or relative_path in tracked
        if is_release_file and path.name in FORBIDDEN_NAMES:
            fail(errors, f'Forbidden release file: {path.relative_to(ROOT)}')
        if is_release_file and path.suffix in {'.pyc', '.sqlite3', '.db'}:
            fail(errors, f'Forbidden generated/database file: {path.relative_to(ROOT)}')
        if path.is_file() and path.stat().st_size <= 3_000_000 and path.suffix.lower() in {
            '.py', '.md', '.txt', '.json', '.yaml', '.yml', '.toml', '.ini', '.example', ''
        }:
            try:
                text = path.read_text(encoding='utf-8')
            except (UnicodeDecodeError, OSError):
                continue
            if path.name == '.env.example':
                continue
            for pattern in SECRET_PATTERNS:
                if pattern.search(text):
                    fail(errors, f'Potential secret found: {path.relative_to(ROOT)}')
                    break


def validate_required(errors):
    required = [
        'Dockerfile', 'docker-compose.yml', '.env.example', 'entrypoint.sh',
        'config/settings.py', 'config/urls.py', 'config/api_urls.py',
        'apps/ai_integration/models.py', 'apps/ai_integration/internal_urls.py',
        'templates/home.html', 'templates/404.html', 'templates/500.html',
    ]
    for relative in required:
        if not (ROOT / relative).exists():
            fail(errors, f'Missing required release file: {relative}')


def main():
    errors = []
    python_count = validate_python(errors)
    validate_hygiene(errors)
    validate_required(errors)
    print(f'Python files checked: {python_count}')
    print(f'Errors: {len(errors)}')
    for error in errors:
        print(f'ERROR: {error}')
    return 1 if errors else 0


if __name__ == '__main__':
    sys.exit(main())
