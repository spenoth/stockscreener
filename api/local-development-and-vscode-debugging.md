# Local API Development and VS Code Debugging

Run PostgreSQL in Docker and the Python API directly on the host. This lets you edit API code and debug it without rebuilding the API image.

## One-time Python setup

From the repository root, create a virtual environment and install the API dependencies:

```powershell
Set-Location api
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

In VS Code, open the repository and select the virtual environment:

1. Open the Command Palette with `Ctrl+Shift+P`.
2. Select **Python: Select Interpreter**.
3. Choose `api\.venv\Scripts\python.exe`.

## Start the database

From the repository root, start only the database service:

```powershell
docker compose -f quant-db\docker-compose.yaml up -d db
```

The database is published on host port `5432`. The API configuration defaults to `localhost` for the database host, so the API can connect to the container through that published port.

## Configure VS Code debugging

Create `.vscode\launch.json` at the repository root:

```json
{
  "version": "0.2.0",
  "configurations": [
    {
      "name": "API (local debug)",
      "type": "debugpy",
      "request": "launch",
      "module": "uvicorn",
      "args": [
        "main:app",
        "--host", "127.0.0.1",
        "--port", "8000"
      ],
      "cwd": "${workspaceFolder}\\api",
      "console": "integratedTerminal",
      "justMyCode": true
    }
  ]
}
```

The `cwd` setting is important: the API imports modules relative to the `api/` directory. The configuration launches Uvicorn using the selected Python interpreter.

## Debug a request

1. Start the database.
2. Set a breakpoint in the API code.
3. Select **API (local debug)** in VS Code's Run and Debug panel.
4. Press `F5`.
5. Send a request to `http://127.0.0.1:8000`.

The API checks database connectivity during startup, so the database must be ready before starting the debug session. Use a different `--port` value in `launch.json` if you want the API to listen on another port.

## Reload behavior

The configuration intentionally omits Uvicorn's `--reload` option. Debugging without the reloader is the most predictable way to have breakpoints hit. After changing code, stop the debug session and press `F5` again; no Docker image rebuild is needed.

To try automatic reload while debugging, add `--reload` to `args` and add this property to the configuration:

```json
"subProcess": true
```

Uvicorn's reloader starts a child process, so breakpoint behavior can be less predictable in this mode. If breakpoints do not hit reliably, remove `--reload` and restart the debug session after code changes.
