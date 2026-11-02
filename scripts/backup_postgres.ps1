$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Root
python scripts/backup_postgres.py
if ($LASTEXITCODE -ne 0) { throw 'PostgreSQL backup failed.' }
