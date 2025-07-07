# Load Testing with Locust

This project contains load testing scripts for simulating real user behavior on our application. We use [Locust](https://locust.io/), an open-source load testing tool that allows you to define user behavior in Python code and generate realistic, concurrent traffic. It's ideal for identifying performance bottlenecks, validating scalability, and establishing performance baselines.

## System Requirements

- macOS (tested on macOS 15+)
- Python 3.8 or newer
- `pip` (or `pip3`) package manager
- Optional: [Homebrew](https://brew.sh/) for installing Python easily

## Installation

1. **Clone this repository**:

   ```bash
   bash
   git clone https://github.com/kidspassport/to-do
   cd load-tests
   ```

2. **(Optional) Create a virtual environment**:

  ```bash
  python3 -m venv venv
  source venv/bin/activate
  ```

1. **Install dependencies**:
  pip install -r requirements.txt

2. For more information, see the official Locust installation guide: <https://docs.locust.io/en/stable/installation.html>

## Development

Tools available for develompent are:

- [ipython](https://pypi.org/project/ipython/)
- [flake8](https://pypi.org/project/flake8/)

### Recommended VSCode Marketplace Extensions

- [pylance](https://marketplace.visualstudio.com/items?itemName=ms-python.vscode-pylance)
- [flake8](https://marketplace.visualstudio.com/items?itemName=ms-python.flake8)
- [mypy type checker](https://marketplace.visualstudio.com/items?itemName=ms-python.mypy-type-checker)
- [autopep8 formatter](https://marketplace.visualstudio.com/items?itemName=ms-python.autopep8) -> can set `"editor.defaultFormatter": "ms-python.autopep8"` directive under python settigns
