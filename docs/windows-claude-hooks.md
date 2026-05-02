# Windows Claude Hook Note

This repository keeps the original `.claude/settings.json` portable. It does
not hardcode a local Git Bash path.

On Windows, Claude Code hooks require a working `bash` command. If `bash`
resolves to an unconfigured WSL shim, install Git for Windows and make sure Git
Bash appears before the WSL shim on your PATH, or adjust your local Claude Code
settings outside the published template.

Do not commit machine-specific absolute paths to the shared template.
