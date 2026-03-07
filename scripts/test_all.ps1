Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
$PSNativeCommandUseErrorActionPreference = $true

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$backendRoot = Join-Path $repoRoot "backend"
$composeFile = Join-Path $repoRoot "infra/docker-compose.test.yml"
$venvPython = Join-Path $backendRoot ".venv\Scripts\python.exe"
$pythonExe = if (Test-Path $venvPython) { $venvPython } else { "python" }
$lockFiles = @(
    (Join-Path $repoRoot ".finos_prompt_engine.lock"),
    (Join-Path $backendRoot ".finos_prompt_engine.lock")
)

function Set-DeterministicEnv {
    param(
        [Parameter(Mandatory = $true)][string]$Name,
        [Parameter(Mandatory = $true)][string]$Value
    )
    Set-Item -Path "Env:$Name" -Value $Value
}

function Invoke-Checked {
    param(
        [Parameter(Mandatory = $true)][string]$Command,
        [Parameter()][string[]]$Arguments = @()
    )
    & $Command @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Command failed (exit=$LASTEXITCODE): $Command $($Arguments -join ' ')"
    }
}

Set-DeterministicEnv -Name "DEBUG" -Value "false"
Set-DeterministicEnv -Name "SECRET_KEY" -Value "test-secret-key"
Set-DeterministicEnv -Name "JWT_SECRET" -Value "test-jwt-secret"
Set-DeterministicEnv -Name "FIELD_ENCRYPTION_KEY" -Value "0123456789abcdef0123456789abcdef"
Set-DeterministicEnv -Name "DATABASE_URL" -Value "postgresql+asyncpg://financeops_test:testpassword@localhost:5433/financeops_test"
Set-DeterministicEnv -Name "TEST_DATABASE_URL" -Value "postgresql+asyncpg://financeops_test:testpassword@localhost:5433/financeops_test"
Set-DeterministicEnv -Name "REDIS_URL" -Value "redis://localhost:6380/0"
Set-DeterministicEnv -Name "TEST_REDIS_URL" -Value "redis://localhost:6380/0"

$exitCode = 0
Push-Location $repoRoot
try {
    Write-Host "Stopping test containers..."
    Invoke-Checked -Command "docker" -Arguments @("compose", "-f", $composeFile, "down")

    Write-Host "Removing stale lock files..."
    foreach ($lockFile in $lockFiles) {
        Remove-Item -Force $lockFile -ErrorAction Ignore
    }

    Write-Host "Clearing pytest cache..."
    Push-Location $backendRoot
    try {
        Invoke-Checked -Command $pythonExe -Arguments @("-m", "pytest", "--cache-clear", "--collect-only", "-q")
    }
    finally {
        Pop-Location
    }

    Write-Host "Starting test containers..."
    Invoke-Checked -Command "docker" -Arguments @("compose", "-f", $composeFile, "up", "-d")

    Write-Host "Waiting for database readiness..."
    Push-Location $backendRoot
    try {
        Invoke-Checked -Command $pythonExe -Arguments @("tests/utils/wait_for_db.py", "--url", $env:TEST_DATABASE_URL, "--timeout", "30")

        Write-Host "Applying migrations..."
        Invoke-Checked -Command $pythonExe -Arguments @("-m", "alembic", "upgrade", "head")

        Write-Host "Running pytest..."
        Invoke-Checked -Command $pythonExe -Arguments @("-m", "pytest", "-q")
    }
    finally {
        Pop-Location
    }
}
catch {
    $exitCode = 1
    Write-Error $_
}
finally {
    Write-Host "Stopping test containers..."
    docker compose -f $composeFile down | Out-Host
    Pop-Location
}

exit $exitCode
