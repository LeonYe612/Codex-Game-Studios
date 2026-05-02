param(
    [string]$Root = (Get-Location).Path
)

$ErrorActionPreference = "Stop"
$issues = New-Object System.Collections.Generic.List[string]
$warnings = New-Object System.Collections.Generic.List[string]

function Test-JsonFile {
    param([string]$Path)
    try {
        Get-Content -Raw -LiteralPath $Path | ConvertFrom-Json | Out-Null
    } catch {
        $issues.Add("Invalid JSON: $Path ($($_.Exception.Message))")
    }
}

function Count-Files {
    param([string]$Path, [string]$Filter = "*")
    if (-not (Test-Path -LiteralPath $Path)) { return 0 }
    return @(Get-ChildItem -Recurse -File -LiteralPath $Path -Filter $Filter).Count
}

$pluginJson = Join-Path $Root ".codex-plugin/plugin.json"
$hooksJson = Join-Path $Root "hooks.json"
$license = Join-Path $Root "LICENSE"
$attribution = Join-Path $Root "ATTRIBUTION.md"
$skills = Join-Path $Root "skills"
$agents = Join-Path $Root "agents"

if (-not (Test-Path -LiteralPath $pluginJson)) { $issues.Add("Missing .codex-plugin/plugin.json") } else { Test-JsonFile $pluginJson }
if (-not (Test-Path -LiteralPath $hooksJson)) { $warnings.Add("Missing hooks.json advisory config") } else { Test-JsonFile $hooksJson }
if (-not (Test-Path -LiteralPath $license)) { $issues.Add("Missing LICENSE") }
if (-not (Test-Path -LiteralPath $attribution)) { $issues.Add("Missing ATTRIBUTION.md") }
if (-not (Test-Path -LiteralPath $skills)) { $issues.Add("Missing skills directory") }
if (-not (Test-Path -LiteralPath $agents)) { $issues.Add("Missing agents directory") }

$skillCount = Count-Files $skills "SKILL.md"
$agentCount = Count-Files $agents "*.md"
if ($skillCount -lt 77) { $warnings.Add("Expected at least 77 Codex skills including core studio skills; found $skillCount") }
if ($agentCount -lt 49) { $issues.Add("Expected at least 49 expert agent reference files; found $agentCount") }

if (Test-Path -LiteralPath $skills) {
    Get-ChildItem -Recurse -File -LiteralPath $skills -Filter "SKILL.md" | ForEach-Object {
        $content = Get-Content -Raw -LiteralPath $_.FullName
        if (-not $content.StartsWith("---")) {
            $issues.Add("Skill missing frontmatter: $($_.FullName)")
        } elseif ($content -notmatch "(?m)^name:\s*") {
            $issues.Add("Skill frontmatter missing name: $($_.FullName)")
        } elseif ($content -notmatch "(?m)^description:\s*") {
            $warnings.Add("Skill frontmatter missing description: $($_.FullName)")
        }
    }
}

$forbiddenPatterns = @(
    ("C:" + "\Users" + "\wanli"),
    ("C:" + "\Program Files" + "\Git")
)
Get-ChildItem -Recurse -File -LiteralPath $Root -Force |
    Where-Object { $_.FullName -notmatch "\\.git\\" } |
    ForEach-Object {
        $text = Get-Content -Raw -LiteralPath $_.FullName -ErrorAction SilentlyContinue
        foreach ($pattern in $forbiddenPatterns) {
            if ($text -like "*$pattern*") {
                $issues.Add("Local path leak '$pattern' in $($_.FullName)")
            }
        }
    }

$result = [ordered]@{
    verdict = if ($issues.Count -eq 0) { "PASS" } else { "BLOCKED" }
    skillCount = $skillCount
    agentCount = $agentCount
    issues = @($issues)
    warnings = @($warnings)
}

$result | ConvertTo-Json -Depth 6
if ($issues.Count -gt 0) { exit 1 }
