param(
    [string]$Root = (Get-Location).Path
)

$ErrorActionPreference = "Stop"
$issues = New-Object System.Collections.Generic.List[string]
$warnings = New-Object System.Collections.Generic.List[string]

function Test-MarkdownSection {
    param([string]$Path, [string]$Section)
    $content = Get-Content -Raw -LiteralPath $Path
    return ($content -match "(?m)^#{1,6}\s+$([regex]::Escape($Section))\b")
}

$gddPath = Join-Path $Root "design/gdd"
if (Test-Path -LiteralPath $gddPath) {
    Get-ChildItem -File -LiteralPath $gddPath -Filter "*.md" | ForEach-Object {
        foreach ($section in @("Overview", "Goals", "Mechanics", "Edge Cases")) {
            if (-not (Test-MarkdownSection $_.FullName $section)) {
                $warnings.Add("GDD may be missing section '$section': $($_.FullName)")
            }
        }
    }
}

$jsonRoots = @("assets", "data", "src")
foreach ($relative in $jsonRoots) {
    $path = Join-Path $Root $relative
    if (Test-Path -LiteralPath $path) {
        Get-ChildItem -Recurse -File -LiteralPath $path -Filter "*.json" | ForEach-Object {
            try {
                Get-Content -Raw -LiteralPath $_.FullName | ConvertFrom-Json | Out-Null
            } catch {
                $issues.Add("Invalid JSON: $($_.FullName)")
            }
        }
    }
}

$srcPath = Join-Path $Root "src"
$testsPath = Join-Path $Root "tests"
$sourcePatterns = @("*.gd", "*.cs", "*.cpp", "*.h", "*.hpp", "*.rs", "*.py", "*.js", "*.ts", "*.tsx")
$hasSourceFiles = $false
if (Test-Path -LiteralPath $srcPath) {
    foreach ($pattern in $sourcePatterns) {
        if (Get-ChildItem -Recurse -File -LiteralPath $srcPath -Filter $pattern -ErrorAction SilentlyContinue | Select-Object -First 1) {
            $hasSourceFiles = $true
            break
        }
    }
}
if ($hasSourceFiles -and -not (Test-Path -LiteralPath $testsPath)) {
    $warnings.Add("Source directory exists but tests directory is missing")
}

$result = [ordered]@{
    verdict = if ($issues.Count -eq 0) { if ($warnings.Count -eq 0) { "PASS" } else { "CONCERNS" } } else { "BLOCKED" }
    issues = @($issues)
    warnings = @($warnings)
}

$result | ConvertTo-Json -Depth 5
if ($issues.Count -gt 0) { exit 1 }
