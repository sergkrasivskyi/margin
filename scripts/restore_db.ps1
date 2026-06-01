param(
    [Parameter(Mandatory = $true)]
    [string]$BackupPath,
    [string]$ContainerName = "margin_research_postgres",
    [string]$DbName = "margin_research",
    [string]$DbUser = "margin_user"
)

$ErrorActionPreference = "Stop"

if (!(Test-Path $BackupPath)) {
    throw "Backup file not found: $BackupPath"
}

Write-Warning "Restore can overwrite existing data in $DbName."
$confirm = Read-Host "Type YES to continue"
if ($confirm -ne "YES") {
    Write-Host "Restore cancelled."
    exit 1
}

Write-Host "Restoring from $BackupPath"
Get-Content -Raw $BackupPath | docker exec -i $ContainerName psql -U $DbUser -d $DbName
Write-Host "Restore completed."

