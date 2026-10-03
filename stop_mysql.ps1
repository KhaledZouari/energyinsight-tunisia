$ErrorActionPreference = 'Stop'
$clientBinary = Join-Path $PSScriptRoot '.tools\mysql-8.4.11-winx64\bin\mysqladmin.exe'
$clientConfig = Join-Path $PSScriptRoot '.mysql\admin.cnf'
if (-not (Test-Path -LiteralPath $clientConfig)) { throw 'Configuration administrateur locale absente.' }
& $clientBinary "--defaults-extra-file=$clientConfig" shutdown
if ($LASTEXITCODE -ne 0) { throw 'Arrêt MySQL échoué.' }
