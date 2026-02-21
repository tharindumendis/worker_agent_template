"""
setup.py — Production packaging for the Universal Worker Agent Template
=======================================================================

Install (editable / development):
    pip install -e .

Install (standard):
    pip install .

Build a distributable wheel:
    pip install build
    python -m build

Publish to PyPI:
    pip install twine
    twine upload dist/*
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

from setuptools import find_packages, setup

# ---------------------------------------------------------------------------
# Minimum Python guard
# ---------------------------------------------------------------------------
if sys.version_info < (3, 10):
    sys.exit(
        "ERROR: worker-agent requires Python 3.10 or later. "
        f"You are running Python {sys.version}."
    )

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

HERE = Path(__file__).parent.resolve()


def _read(filename: str) -> str:
    """Read a file relative to this setup.py, stripping BOM if present."""
    return (HERE / filename).read_text(encoding="utf-8-sig")


def _version() -> str:
    """
    Pull the version from config.yaml so there is a single source of truth.
    Falls back to '0.0.0' if the file or key is missing.
    """
    try:
        config_text = _read("config.yaml")
        match = re.search(r"^\s*version:\s*[\"']?([^\"'\n]+)[\"']?", config_text, re.M)
        if match:
            return match.group(1).strip()
    except FileNotFoundError:
        pass
    return "0.0.0"


def _parse_requirements(filename: str) -> list[str]:
    """
    Parse a pip-style requirements file, ignoring comments, blank lines,
    and -r / --index-url directives.
    """
    reqs: list[str] = []
    try:
        for line in _read(filename).splitlines():
            line = line.strip()
            if not line or line.startswith("#") or line.startswith("-"):
                continue
            # Strip inline comments
            line = line.split(" #")[0].strip()
            reqs.append(line)
    except FileNotFoundError:
        pass
    return reqs


# ---------------------------------------------------------------------------
# Metadata
# ---------------------------------------------------------------------------

NAME = "worker-agent"
DESCRIPTION = (
    "A config-driven, plug-and-play worker agent template built on "
    "LangGraph + FastMCP. Clone the folder, edit config.yaml, and you "
    "have a brand-new specialized agent — no code changes needed."
)
AUTHOR = "Tharindumendis"
AUTHOR_EMAIL = ""          # ← fill in your e-mail
URL = "https://github.com/tharindumendis/worker_agent_template"
LICENSE_EXPRESSION = "MIT"   # SPDX expression (PEP 639)
PYTHON_REQUIRES = ">=3.10"

CLASSIFIERS = [
    # Maturity
    "Development Status :: 4 - Beta",
    # Audience
    "Intended Audience :: Developers",
    "Intended Audience :: Science/Research",
    # Topic
    "Topic :: Scientific/Engineering :: Artificial Intelligence",
    "Topic :: Software Development :: Libraries :: Application Frameworks",
    # License (kept for broad PyPI compatibility; SPDX field is set separately)
    "License :: OSI Approved :: MIT License",
    # Python
    "Programming Language :: Python :: 3",
    "Programming Language :: Python :: 3.10",
    "Programming Language :: Python :: 3.11",
    "Programming Language :: Python :: 3.12",
    "Programming Language :: Python :: 3 :: Only",
    # OS
    "Operating System :: OS Independent",
    # Type checking
    "Typing :: Typed",
]

KEYWORDS = [
    "agent",
    "worker-agent",
    "langgraph",
    "langchain",
    "mcp",
    "fastmcp",
    "ollama",
    "llm",
    "react-agent",
    "autonomous-agent",
]

# ---------------------------------------------------------------------------
# Dependencies
# ---------------------------------------------------------------------------

INSTALL_REQUIRES = _parse_requirements("requirements.txt")

EXTRAS_REQUIRE = {
    # Extras for running tests
    "dev": [
        "pytest>=7.0",
        "pytest-asyncio>=0.23",
        "pytest-cov>=4.0",
        "ruff>=0.4",
        "mypy>=1.8",
        "types-PyYAML",
        "pre-commit>=3.0",
    ],
    # Extras for building and publishing the package
    "release": [
        "build>=1.0",
        "twine>=5.0",
    ],
}

# Convenience alias that installs everything
EXTRAS_REQUIRE["all"] = sorted(
    {dep for deps in EXTRAS_REQUIRE.values() for dep in deps}
)

# ---------------------------------------------------------------------------
# Entry points (CLI)
# ---------------------------------------------------------------------------

ENTRY_POINTS = {
    "console_scripts": [
        # Allows:  worker-agent  (uses defaults from config.yaml)
        # or:      worker-agent --transport sse --port 8001
        "worker-agent=main:_cli_entry",
    ],
}

# ---------------------------------------------------------------------------
# Package data
# ---------------------------------------------------------------------------

PACKAGE_DATA = {
    "": [
        "*.yaml",
        "*.yml",
        "*.json",
        "*.md",
        "py.typed",          # PEP 561 marker — signals this package is typed
    ],
}

# ---------------------------------------------------------------------------
# Setup
# ---------------------------------------------------------------------------

setup(
    # ── Identity ──────────────────────────────────────────────────────────
    name=NAME,
    version=_version(),
    description=DESCRIPTION,
    long_description=_read("README.md"),
    long_description_content_type="text/markdown",
    author=AUTHOR,
    author_email=AUTHOR_EMAIL,
    url=URL,
    license=LICENSE_EXPRESSION,
    license_files=["LICENSE"],
    # ── Classification ────────────────────────────────────────────────────
    classifiers=CLASSIFIERS,
    keywords=", ".join(KEYWORDS),
    # ── Packages ──────────────────────────────────────────────────────────
    packages=find_packages(
        exclude=["tests", "tests.*", "*.egg-info", ".venv", ".venv.*"]
    ),
    # Bare .py modules at project root (not inside a package directory)
    # main.py must be installed for the 'worker-agent' console script to work
    py_modules=["main", "sample_main_agent"],
    package_data=PACKAGE_DATA,
    include_package_data=True,   # also picks up files listed in MANIFEST.in
    # ── Python / pip requirements ─────────────────────────────────────────
    python_requires=PYTHON_REQUIRES,
    install_requires=INSTALL_REQUIRES,
    extras_require=EXTRAS_REQUIRE,
    # ── CLI entry points ──────────────────────────────────────────────────
    entry_points=ENTRY_POINTS,
    # ── Build flags ───────────────────────────────────────────────────────
    zip_safe=False,    # needed for packages that read data files at runtime
    # ── Project URLs (shown on PyPI) ──────────────────────────────────────
    project_urls={
        "Source":       URL,
        "Bug Tracker":  f"{URL}/issues",
        "Changelog":    f"{URL}/blob/main/CHANGELOG.md",
        "Documentation": f"{URL}#readme",
    },
)
