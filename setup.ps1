param(
    [switch]$Yes
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Test-Command {
    param([string]$Name)
    $null -ne (Get-Command $Name -ErrorAction SilentlyContinue)
}

function Ask-YesNo {
    param(
        [string]$Question,
        [bool]$Default = $true
    )
    if ($Yes) {
        return $true
    }
    $suffix = if ($Default) { "[Y/n]" } else { "[y/N]" }
    $answer = Read-Host "$Question $suffix"
    if ([string]::IsNullOrWhiteSpace($answer)) {
        return $Default
    }
    return $answer.Trim().ToLowerInvariant().StartsWith("y")
}

function Add-UserPath {
    param([string]$Directory)
    $current = [Environment]::GetEnvironmentVariable("Path", "User")
    $parts = @()
    if (-not [string]::IsNullOrWhiteSpace($current)) {
        $parts = @($current -split ";" | Where-Object { -not [string]::IsNullOrWhiteSpace($_) })
    }
    $normalizedParts = @($parts | ForEach-Object { $_.TrimEnd("\") })
    $normalizedDirectory = $Directory.TrimEnd("\")
    if ($normalizedParts -contains $normalizedDirectory) {
        return
    }
    $newPath = if ($parts.Count -gt 0) { ($parts + $Directory) -join ";" } else { $Directory }
    [Environment]::SetEnvironmentVariable("Path", $newPath, "User")
    $env:Path = [Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [Environment]::GetEnvironmentVariable("Path", "User")
}

$repoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $repoRoot

Write-Host "NightShift setup"
Write-Host "Repo: $repoRoot"

if (-not (Test-Command "python")) {
    throw "Python was not found on PATH. Install Python 3.11+ and rerun setup.ps1."
}

$pythonVersion = python -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"
Write-Host "Python: $pythonVersion"

Write-Host "Installing NightShift in editable mode..."
python -m pip install -e .

$scriptsDir = python -c "import sysconfig; print(sysconfig.get_path('scripts', scheme='nt_user') or sysconfig.get_path('scripts'))"
$pathParts = $env:Path -split ";" | Where-Object { -not [string]::IsNullOrWhiteSpace($_) }
if ($pathParts -notcontains $scriptsDir) {
    if (Ask-YesNo "Add Python scripts directory to your user PATH so 'nightshift' works in new terminals? $scriptsDir") {
        Add-UserPath $scriptsDir
        $persistedUserPath = [Environment]::GetEnvironmentVariable("Path", "User")
        if (($persistedUserPath -split ";" | ForEach-Object { $_.TrimEnd("\") }) -contains $scriptsDir.TrimEnd("\")) {
            Write-Host "Added to user PATH: $scriptsDir"
        } else {
            Write-Host "Tried to add PATH entry, but it was not visible in the persisted user PATH."
            Write-Host "Manual command:"
            Write-Host "[Environment]::SetEnvironmentVariable('Path', [Environment]::GetEnvironmentVariable('Path','User') + ';$scriptsDir', 'User')"
        }
    } else {
        Write-Host "Skipped PATH update. You can still run: python -m nightshift.cli"
    }
} else {
    Write-Host "PATH already includes Python scripts directory."
}

if (Test-Command "nightshift") {
    Write-Host "NightShift CLI is available:"
    nightshift --help | Select-Object -First 5
} else {
    Write-Host "NightShift CLI is not visible in this shell yet. Open a new terminal or run: python -m nightshift.cli --help"
}

if (Test-Command "ollama") {
    Write-Host "Ollama is installed:"
    ollama --version
} else {
    Write-Host "Ollama was not found."
    if (Test-Command "winget") {
        if (Ask-YesNo "Install Ollama with winget now?") {
            winget install --id Ollama.Ollama -e
        } else {
            Write-Host "Skipped Ollama install. Install later from https://ollama.com/download"
        }
    } else {
        Write-Host "winget was not found. Install Ollama from https://ollama.com/download"
    }
}

Write-Host ""
Write-Host "Setup complete."
Write-Host "Validate this repo with: nightshift validate"
Write-Host "Start the dashboard with: nightshift web"
