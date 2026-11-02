param([Parameter(Mandatory=$true)][string]$BackupFile)
$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Root
python scripts/restore_postgres.py $BackupFile
if ($LASTEXITCODE -ne 0) { throw 'PostgreSQL restore failed or was cancelled.' }
