$ErrorActionPreference = 'Stop'
$projectPath = $PSScriptRoot
$serverBinary = Join-Path $projectPath '.tools\mysql-8.4.11-winx64\bin\mysqld.exe'
$dataPath = Join-Path $projectPath '.mysql\data'
if (-not (Test-Path -LiteralPath $serverBinary) -or -not (Test-Path -LiteralPath $dataPath)) {
    throw 'Serveur portable absent : voir README.md pour configurer un autre MySQL.'
}
if (Get-NetTCPConnection -LocalPort 3306 -State Listen -ErrorAction SilentlyContinue) {
    Write-Output 'Le port 3306 est déjà occupé. Vérifier la connexion avec verify_project.py.'
    exit 0
}
$serverArguments = @('--no-defaults','--console','--bind-address=127.0.0.1','--port=3306','--mysqlx=0',
    ('--basedir="'+(Join-Path $projectPath '.tools\mysql-8.4.11-winx64')+'"'),('--datadir="'+$dataPath+'"'))
$serverProcess = Start-Process -FilePath $serverBinary -ArgumentList $serverArguments -WindowStyle Hidden -PassThru `
    -RedirectStandardOutput (Join-Path $projectPath '.mysql\server.stdout.log') `
    -RedirectStandardError (Join-Path $projectPath '.mysql\server.stderr.log')
$serverProcess.Id | Set-Content (Join-Path $projectPath '.mysql\server.pid')
for ($attempt = 0; $attempt -lt 30; $attempt++) {
    Start-Sleep -Seconds 1
    if (Get-NetTCPConnection -LocalPort 3306 -State Listen -ErrorAction SilentlyContinue) {
        Write-Output 'MySQL disponible sur 127.0.0.1:3306.'
        exit 0
    }
}
throw 'MySQL ne démarre pas : consulter .mysql/server.stderr.log.'
