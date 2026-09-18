# Sync anki-bot input/output with Google Drive via rclone.
# Requires: rclone on PATH, remote named gdrive (or set ANKI_BOT_RCLONE_REMOTE).

param(
    [Parameter(Mandatory = $true, Position = 0)]
    [ValidateSet("pull", "push-input", "push-output")]
    [string]$Action
)

$ErrorActionPreference = "Stop"
$Remote = if ($env:ANKI_BOT_RCLONE_REMOTE) { $env:ANKI_BOT_RCLONE_REMOTE } else { "gdrive" }

function Require-Rclone {
    if (-not (Get-Command rclone -ErrorAction SilentlyContinue)) {
        Write-Error "rclone not found on PATH. Install from https://rclone.org/downloads/ and run rclone config."
    }
}

Require-Rclone

$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot

switch ($Action) {
    "pull" {
        New-Item -ItemType Directory -Force -Path "output" | Out-Null
        rclone copy "${Remote}:anki-bot/output" ".\output"
        Write-Host "Pulled Drive output to $RepoRoot\output"
    }
    "push-input" {
        if (-not (Test-Path ".\input")) {
            Write-Error "No local input/ folder."
        }
        rclone copy ".\input" "${Remote}:anki-bot/input"
        Write-Host "Pushed local input to Drive."
    }
    "push-output" {
        if (-not (Test-Path ".\output")) {
            Write-Error "No local output/ folder."
        }
        rclone copy ".\output" "${Remote}:anki-bot/output"
        Write-Host "Pushed local output to Drive (upload review edits before 2 AM)."
    }
}
