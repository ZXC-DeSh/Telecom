param([int]$Port = 8000)
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath (Split-Path -Parent $PSScriptRoot)
$demoPython = Join-Path $PWD '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $demoPython)) { throw 'Сначала установите окружение по README.md' }
if (-not (Test-Path -LiteralPath 'artifacts\model.json')) {
    & $demoPython -m antifraud.generate
    if ($LASTEXITCODE -ne 0) { throw 'Ошибка генерации данных' }
    & $demoPython -m antifraud.train
    if ($LASTEXITCODE -ne 0) { throw 'Ошибка обучения' }
}
Write-Host "Интерфейс: http://127.0.0.1:$Port/"
Write-Host "Документация API: http://127.0.0.1:$Port/docs"
& $demoPython -m uvicorn antifraud.api:create_app --factory --host 127.0.0.1 --port $Port --reload
