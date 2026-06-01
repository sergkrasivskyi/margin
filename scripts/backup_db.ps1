param(
    [string]$ContainerName = "margin_research_postgres",
    [string]$DbName = "margin_research",
    [string]$DbUser = "margin_user"
)

$ErrorActionPreference = "Stop"
$backupDir = Join-Path $PSScriptRoot "..\data\backups"
New-Item -ItemType Directory -Path $backupDir -Force | Out-Null

$timestamp = Get-Date -Format "yyyy-MM-dd_HH-mm"
$backupFile = Join-Path $backupDir "backup_$timestamp.sql"

Write-Host "Creating backup: $backupFile"
docker exec -t $ContainerName pg_dump -U $DbUser -d $DbName > $backupFile
Write-Host "Backup created."

