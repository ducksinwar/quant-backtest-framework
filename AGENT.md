# Environment
This project uses a conda environment named `backtest`.
The environment uses Python 3.12. Do not use system Python.
All Python commands must run inside this environment.

## Initial Setup
If the environment does not exist, create it:
```bash
conda create -n backtest python=3.12 pandas numpy matplotlib pyyaml pytest -y
```

## Running commands
Always use `conda run`:
```bash
# Run tests
conda run -n backtest python -m pytest

# Run example scripts
conda run -n backtest python examples/sma_crossover_example.py
```

## If `conda run` is unavailable
First, locate conda. Common installation locations include:
- `C:\Users\<username>\anaconda3`
- `C:\Users\<username>\miniconda3`
- `C:\ProgramData\Anaconda3`
- `D:\anaconda3`
- `/opt/anaconda3`
- `~/anaconda3`
- `~/miniconda3`
Then run commands with the full conda path:
```bash
<conda_root>\Scripts\conda.exe run -n backtest python -m pytest
```
Or call the environment's Python directly:
```bash
<conda_root>\envs\backtest\python.exe -m pytest   # Windows
<conda_root>/envs/backtest/bin/python -m pytest   # Linux / macOS
```
If conda cannot be found, ask the user for the correct conda path.

## Dependency Management
Install dependencies only into the `backtest` environment:
```bash
conda run -n backtest pip install <package>
```
Do not install project dependencies globally or into another environment.

## Testing Infrastructure (environment-specific)
- On normal environments (Linux/macOS/standard Windows) pytest's built-in
  `tmp_path` works; no extra configuration is needed and `tests/conftest.py`
  does not exist in the repository.
- Under restricted-token sandboxes on Windows (e.g. the DeepSeek harness),
  `tmp_path` fails with `PermissionError [WinError 5]` because pytest creates
  temp dirs with an explicit 0o700 mode whose Security Descriptor breaks DACL
  inheritance (https://github.com/deepseek-ai/deepseek-harness/discussions/81).
- If and only if you hit that error: create a LOCAL, UNTRACKED
  `tests/conftest.py` (gitignored; never commit it) that overrides `tmp_path`
  to create per-test dirs via `os.makedirs()` (no explicit mode) under
  `tests/.tmp/`, with per-test teardown and a session-start sweep of stale
  `tests/.tmp/*`.
- Never pass `--basetemp`, never create probe/diagnostic directories, and
  never request elevated or full-access permissions to work around temp-dir
  permission errors. If the error reappears despite the override, stop and
  report it.
