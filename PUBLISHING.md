# 📦 Publishing `worker-agent` to PyPI

## Prerequisites

- A [PyPI account](https://pypi.org/account/register/)
- An [API token](https://pypi.org/manage/account/token/) (starts with `pypi-`)

---

## 1. Build

```bash
uv build
```

This creates `dist/worker_agent-1.0.0-py3-none-any.whl` and `.tar.gz`.

---

## 2. Test on TestPyPI (Optional but Recommended)

TestPyPI is a separate instance of PyPI for testing package uploads before going live.

### Important: TestPyPI vs PyPI are completely separate

- **Separate accounts** — register at [test.pypi.org/account/register](https://test.pypi.org/account/register/)
- **Separate tokens** — create one at [test.pypi.org/manage/account/token](https://test.pypi.org/manage/account/token/)
- A PyPI token will **not** work on TestPyPI and vice versa

### Publish to TestPyPI

```bash
uv publish --publish-url https://test.pypi.org/legacy/ --token pypi-YOUR_TESTPYPI_TOKEN
```

### Verify the upload

TestPyPI doesn't host most dependencies (like `langchain`, `fastmcp`, etc.), so you must:

1. Use `--extra-index-url` to add TestPyPI **alongside** the real PyPI
2. Use `--index-strategy unsafe-best-match` so uv pulls dependencies from both indexes

```bash
uvx --extra-index-url https://test.pypi.org/simple/ --index-strategy unsafe-best-match worker-agent@latest --help
```

> **Why `--index-strategy unsafe-best-match`?**
> By default, uv only considers versions from the first index that contains a package (to prevent dependency confusion attacks). Since TestPyPI has old/dev versions of common packages like `mcp`, uv would try to use those instead of the real ones. This flag tells uv to pick the best matching version from any index.

### Troubleshooting: Cached old version

If `uvx` returns an error from an older version, clear the cache and retry:

```bash
uv cache clean worker-agent --force
uvx --extra-index-url https://test.pypi.org/simple/ --index-strategy unsafe-best-match worker-agent@latest --help
```

---

## 3. Publish to PyPI

```bash
uv publish --token pypi-YOUR_API_TOKEN
```

---

## 4. After Publishing

Anyone can now install and run:

```bash
# One-shot run (no install needed)
uvx worker-agent

# Or install permanently
uv pip install worker-agent
```

MCP client config becomes:

```json
{
  "mcpServers": {
    "file-worker": {
      "command": "uvx",
      "args": ["worker-agent"]
    }
  }
}
```

---

## Updating the Version

1. Bump `version` in `pyproject.toml` and `config.yaml`
2. Rebuild and republish:
   ```bash
   uv build
   uv publish --token pypi-YOUR_API_TOKEN
   ```

> **Note:** PyPI does not allow re-uploading the same version. Always bump the version before publishing again.
