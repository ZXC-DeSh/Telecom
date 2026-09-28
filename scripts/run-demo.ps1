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
if (-not $env:ANTIFRAUD_OPERATOR_KEY) { $env:ANTIFRAUD_OPERATOR_KEY = & $demoPython -c 'import secrets; print(secrets.token_urlsafe(32))' }
if (-not $env:ANTIFRAUD_ADMIN_KEY) { $env:ANTIFRAUD_ADMIN_KEY = & $demoPython -c 'import secrets; print(secrets.token_urlsafe(32))' }
if (-not $env:ANTIFRAUD_ORG_KEYS_JSON) {
    $demoOrgKey = & $demoPython -c 'import secrets; print(secrets.token_urlsafe(32))'
    $env:ANTIFRAUD_ORG_KEYS_JSON = @{ demo_hospital = $demoOrgKey } | ConvertTo-Json -Compress
}
& $demoPython -m antifraud.seed_demo
if ($LASTEXITCODE -ne 0) { throw 'Ошибка загрузки демонстрационных данных' }
Write-Host "Swagger: http://127.0.0.1:$Port/docs"
Write-Host 'Ключи находятся в переменных ANTIFRAUD_OPERATOR_KEY, ANTIFRAUD_ADMIN_KEY и ANTIFRAUD_ORG_KEYS_JSON этого процесса.'
Write-Host 'Для проверки в другом терминале установите свои ключи в обоих терминалах до запуска.'
& $demoPython -m uvicorn antifraud.api:create_app --factory --host 127.0.0.1 --port $Port
