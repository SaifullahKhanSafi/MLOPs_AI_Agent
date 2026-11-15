param([switch]$Deploy)
$ErrorActionPreference = 'Stop'
Set-Location (Split-Path $PSScriptRoot -Parent)

function Run-Checked {
    param([string]$Program, [string[]]$Arguments)
    & $Program @Arguments
    if ($LASTEXITCODE -ne 0) { throw "Command failed: $Program $Arguments" }
}

if (-not (Test-Path .venv/Scripts/python.exe)) {
    Run-Checked python @('-m', 'venv', '.venv')
}
$env:Path = "$PWD\.venv\Scripts;$env:Path"
Run-Checked python @('-m', 'pip', 'install', '-e', '.[dev]')
Run-Checked python @('scripts/bootstrap.py')
Run-Checked docker @('compose', '--parallel', '1', 'up', '-d', '--build', '--wait', '--wait-timeout', '900')
Run-Checked dvc @('repro')
Run-Checked python @('-m', 'ruff', 'check', '.')
Run-Checked python @('-m', 'pytest', '-q')
if ($Deploy) {
    # The -Deploy switch explicitly requests the reviewed namespace-scoped operation.
    Run-Checked python @('scripts/deploy.py', '--confirm')
}
Write-Host 'Pipeline is ready. Run python -m agent.main for the conversational interface.'
Write-Host 'MLflow: http://localhost:5000 | Airflow: http://localhost:8080'
