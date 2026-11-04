param(
    [string]$Root = (Get-Location).Path
)

$ErrorActionPreference = "Stop"

function Test-AnyFile {
    param([string]$Path, [string[]]$Patterns)
    if (-not (Test-Path -LiteralPath $Path)) { return $false }
    foreach ($pattern in $Patterns) {
        if (Get-ChildItem -Recurse -File -LiteralPath $Path -Filter $pattern -ErrorAction SilentlyContinue | Select-Object -First 1) {
            return $true
        }
    }
    return $false
}

$designPath = Join-Path $Root "design"
$docsPath = Join-Path $Root "docs"
$productionPath = Join-Path $Root "production"
$srcPath = Join-Path $Root "src"
$prototypePath = Join-Path $Root "prototypes"

$hasConcept = Test-Path -LiteralPath (Join-Path $Root "design/gdd/game-concept.md")
$hasDesignDocs = Test-AnyFile $designPath @("*.md")
$hasArchitecture = Test-AnyFile (Join-Path $docsPath "architecture") @("*.md", "*.yaml", "*.yml")
$hasProduction = Test-AnyFile $productionPath @("*.md", "*.yaml", "*.yml", "*.txt")
$hasSource = Test-AnyFile $srcPath @("*.gd", "*.cs", "*.cpp", "*.h", "*.hpp", "*.rs", "*.py", "*.js", "*.ts", "*.tsx")
$hasPrototypes = Test-Path -LiteralPath $prototypePath -PathType Container

$engine = "unknown"
if (Test-Path -LiteralPath (Join-Path $Root "project.godot")) { $engine = "godot" }
elseif (Test-Path -LiteralPath (Join-Path $Root "Assets")) { $engine = "unity" }
elseif (Get-ChildItem -File -LiteralPath $Root -Filter "*.uproject" -ErrorAction SilentlyContinue | Select-Object -First 1) { $engine = "unreal" }

$stage = "empty"
$recommended = "brainstorm"
if ($hasSource) {
    $stage = "implementation"
    $recommended = "automation-gate"
} elseif ($hasProduction) {
    $stage = "production-planning"
    $recommended = "sprint-plan"
} elseif ($hasArchitecture) {
    $stage = "architecture"
    $recommended = "create-epics"
} elseif ($hasDesignDocs -or $hasConcept) {
    $stage = "design"
    $recommended = "create-architecture"
} elseif ($hasPrototypes) {
    $stage = "prototype"
    $recommended = "project-stage-detect"
}

[ordered]@{
    stage = $stage
    recommendedSkill = $recommended
    engine = $engine
    evidence = [ordered]@{
        hasConcept = $hasConcept
        hasDesignDocs = $hasDesignDocs
        hasArchitecture = $hasArchitecture
        hasProduction = $hasProduction
        hasSource = $hasSource
        hasPrototypes = $hasPrototypes
    }
} | ConvertTo-Json -Depth 5
