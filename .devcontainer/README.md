# Development Container Setup

This directory contains the configuration for using this project with VS Code's Dev Containers feature.

## What is a Dev Container?

A development container is a running Docker container with a well-defined tool/runtime stack and its prerequisites. It allows you to use a container as a full-featured development environment.

## Prerequisites

1. **Docker Desktop** - Install from [docker.com](https://www.docker.com/products/docker-desktop/)
2. **Visual Studio Code** - Install from [code.visualstudio.com](https://code.visualstudio.com/)
3. **Dev Containers Extension** - Install from VS Code marketplace: `ms-vscode-remote.remote-containers`

## Getting Started

### Option 1: Using VS Code

1. Open this project in VS Code
2. When prompted, click "Reopen in Container" (or press `F1` and select "Dev Containers: Reopen in Container")
3. Wait for the container to build (first time takes a few minutes)
4. Start developing!

### Option 2: Command Palette

1. Open VS Code
2. Press `F1` or `Cmd/Ctrl+Shift+P`
3. Type "Dev Containers: Open Folder in Container"
4. Select this project folder
5. Wait for the container to build

## What's Included

The dev container includes:

### Development Tools
- Python 3.11 with all project dependencies
- pytest for testing
- black for code formatting
- ruff for linting
- mypy for type checking
- ipython for interactive debugging

### VS Code Extensions
- Python language support with Pylance
- Black formatter
- Ruff linter
- GitHub Copilot (if you have access)
- YAML and TOML support

### Configuration
- Auto-formatting on save
- Organized imports on save
- Test discovery configured
- Port 8000 forwarded for API access

## Running the Application

Once inside the dev container:

```bash
# Run the application
uvicorn main:app --reload --host 0.0.0.0 --port 8000

# Or use the task runner (F1 -> Tasks: Run Task)
```

## Running Tests

```bash
# Run all tests
pytest -v

# Run with coverage
pytest --cov=. --cov-report=html

# Run specific test
pytest test_main.py::test_name -v
```

## Environment Variables

The dev container sets default environment variables in `docker-compose.yml`:
- `XML_DIR=/workspace/data`
- `DB_PATH=/workspace/database.db`

You can override these by creating a `.env` file in the workspace root.

## Persisted Data

The following are persisted across container rebuilds:
- Bash history (in `/commandhistory/.bash_history`)
- Python packages (in `/home/vscode/.local`)
- Your workspace files (in `/workspace`)

## Troubleshooting

### Container fails to build
- Ensure Docker Desktop is running
- Check Docker has enough resources allocated (4GB RAM minimum)
- Try rebuilding: `F1` -> "Dev Containers: Rebuild Container"

### Port already in use
- Stop any local services running on port 8000
- Or change the port in `.devcontainer/devcontainer.json`

### Permission issues
- The container runs as user `vscode` (UID 1000)
- If you have permission issues, rebuild the container

## Customization

You can customize the dev container by editing:
- `.devcontainer/devcontainer.json` - VS Code settings and extensions
- `.devcontainer/Dockerfile` - System packages and tools
- `.devcontainer/docker-compose.yml` - Environment variables and volumes

## More Information

- [VS Code Dev Containers Documentation](https://code.visualstudio.com/docs/devcontainers/containers)
- [Dev Container Specification](https://containers.dev/)
