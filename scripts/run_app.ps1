# SafeRoute AI — one-command launcher (Windows PowerShell)
# Starts the API + UI using the workspace virtual environment.
#
# Usage (from the workspace root):
#   .\scripts\run_app.ps1
#   .\scripts\run_app.ps1 -Port 8010 -NoBrowser

param(
    [int]$Port = 8000,
    [string]$HostAddr = "127.0.0.1",
    [switch]$NoBrowser
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $root

$py = Join-Path $root ".venv\Scripts\python.exe"
if (-not (Test-Path $py)) {
    Write-Error "Workspace virtual environment not found at $py. Create it first (see README.md)."
}

$args = @("scripts\run_app.py", "--host", $HostAddr, "--port", "$Port")
if ($NoBrowser) { $args += "--no-browser" }

& $py @args
