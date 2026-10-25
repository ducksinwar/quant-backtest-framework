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

## Testing Infrastructure
- pytest's built-in `tmp_path` works as-is here; no local override is needed.
  Verified 2026-10-23: `python -m pytest -q` -> 581 passed, 0 failures,
  0 errors, no `PermissionError [WinError 5]`.
- A local, untracked `tests/conftest.py` previously overrode `tmp_path` to work
  around restricted-token sandboxes under the DeepSeek harness. That harness is
  no longer in use, so the override and its scratch directory `tests/.tmp/`
  have been deleted. Do not recreate either.
- Never pass `--basetemp`, never create probe/diagnostic directories, and
  never request elevated or full-access permissions to work around temp-dir
  permission errors. If `WinError 5` reappears, stop and report it.
