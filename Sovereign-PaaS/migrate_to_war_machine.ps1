# TRISHULA SOVEREIGN MIGRATION PROTOCOL v2.0
# Mission: Stage -> Scrub -> Verify -> Archive
$SourceDir = "D:\Trishula-Infra"
$StageDir = "D:\Trishula-Stage-Temp"
$ArchiveName = "trishula_logic_salvo.tar.gz"

Write-Host "[*] Initializing Staging Environment..." -ForegroundColor Cyan

# 1. CLEAN STAGE: Start with a fresh directory
if (Test-Path $StageDir) { Remove-Item -Recurse -Force $StageDir }
New-Item -ItemType Directory -Path $StageDir | Out-Null

# 2. SELECTIVE COPY: Only move the logic and Swarm components
Copy-Item -Path "$SourceDir\Sovereign-PaaS" -Destination $StageDir -Recurse
Copy-Item -Path "$SourceDir\Swarm" -Destination $StageDir -Recurse

# 3. THE SCRUB: Recursively delete sensitive patterns
Write-Host "[!] Scrubbing Credentials and Metadata..." -ForegroundColor Yellow
$Patterns = @("*.env", "*key.json", "aegis_leads.csv", ".git")
foreach ($Pattern in $Patterns) {
    Get-ChildItem -Path $StageDir -Filter $Pattern -Recurse | Remove-Item -Force -Recurse
}

# 4. VERIFICATION: Ensure no secrets survived the scrub
Write-Host "[?] Final Security Audit..." -ForegroundColor Cyan
$Leaks = Get-ChildItem -Path "$StageDir\*" -Include $Patterns -Recurse
if ($Leaks.Count -gt 0) {
    Write-Host "[ERROR] CRITICAL LEAK DETECTED. ABORTING SALVO." -ForegroundColor Red
    $Leaks | ForEach-Object { Write-Host " -> Survivor Found: $($_.FullName)" -ForegroundColor Red }
    exit 1
}

# 5. ARCHIVE: Create the sanitized logic salvo
Write-Host "[+] Security Audit Passed. Generating Salvo..." -ForegroundColor Green
tar -cvzf $ArchiveName -C $StageDir .

Write-Host "[SUCCESS] Logic Salvo Ready at: $ArchiveName" -ForegroundColor Green
Write-Host "[NEXT] Transfer to War Machine via SCP/Local Network." -ForegroundColor Cyan