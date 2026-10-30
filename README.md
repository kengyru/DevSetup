# DevSetup

DevSetup is a Windows desktop application for scanning, exporting, comparing and restoring developer environments.

## Features

- Scan installed developer tools and applications.
- Export environment configuration to .setup files.
- Compare saved environments with the current machine.
- Restore selected applications through winget.
- Backup VS Code extensions.
- Scan global Python and npm packages.
- Scan Git configuration.
- Scan safe user environment variables.
- Detect WSL distributions.
- Windows Terminal settings detection.

## Tech Stack

- Python
- PySide6
- Qt
- Windows Package Manager (winget)
- WSL

## Installation

1. Clone the repository.
2. Create a virtual environment:

   python -m venv .venv

3. Activate it:

   .venv\Scripts\activate

4. Install dependencies:

   pip install -r requirements.txt

5. Run:

   python main.py

## Platform

Windows only.

## Security

DevSetup does not store passwords, API keys, tokens or other secrets in exported setup files. Restoring applications uses locally controlled package identifiers.
