param(
    [string]$Source = (Get-Location).Path,
    [string]$Destination = (Join-Path $env:USERPROFILE ".codex/plugins/codex-game-studios")
)

$ErrorActionPreference = "Stop"

if (-not (Test-Path -LiteralPath (Join-Path $Source ".codex-plugin/plugin.json"))) {
    throw "Source does not look like a Codex Game Studios plugin root: $Source"
}

New-Item -ItemType Directory -Force -Path (Split-Path -Parent $Destination) | Out-Null
if (Test-Path -LiteralPath $Destination) {
    Remove-Item -Recurse -Force -LiteralPath $Destination
}

Copy-Item -Recurse -Force -LiteralPath $Source -Destination $Destination

[ordered]@{
    installed = $true
    destination = $Destination
    nextStep = "Restart Codex or enable the local plugin if your Codex build requires manual plugin activation."
} | ConvertTo-Json -Depth 3
