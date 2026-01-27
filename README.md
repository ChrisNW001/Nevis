# Nevis

**Master AI Assistant that connects everything.**

Nevis is a central orchestration layer that integrates and coordinates multiple AI services, tools, and projects.

## Features

- Unified interface for multiple AI backends
- Integration hub for connecting various services
- Extensible plugin architecture
- Async-first design

## Installation

```bash
# Clone the repository
git clone https://github.com/YOUR_USERNAME/Nevis.git
cd Nevis

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install in development mode
pip install -e ".[dev]"
```

## Usage

```bash
# Run the assistant
nevis

# Or run directly
python -m nevis.main
```

## Configuration

Copy `.env.example` to `.env` and configure your settings:

```bash
cp .env.example .env
```

## Project Structure

```
Nevis/
├── src/nevis/
│   ├── core/           # Core assistant logic
│   ├── integrations/   # Service integrations
│   └── main.py         # Entry point
├── tests/              # Test suite
└── pyproject.toml      # Project configuration
```

## Development

```bash
# Run tests
pytest

# Run linter
ruff check src/

# Format code
ruff format src/
```

## License

MIT
