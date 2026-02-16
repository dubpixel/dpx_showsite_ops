# Sysmon Daily Security Check
# Checks last 24 hours for common compromise indicators
# Run with: powershell -ExecutionPolicy Bypass -File sysmon-daily-check.ps1

$ErrorActionPreference = "SilentlyContinue"
$timeRange = (Get-Date).AddHours(-24)

Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "   SYSMON SECURITY CHECK - LAST 24HR" -ForegroundColor Cyan
Write-Host "========================================`n" -ForegroundColor Cyan

# Check 1: Unsigned Drivers (rootkit indicator)
Write-Host "[*] Checking for unsigned drivers..." -ForegroundColor Yellow
$unsignedDrivers = Get-WinEvent -FilterHashtable @{LogName='Microsoft-Windows-Sysmon/Operational'; ID=6; StartTime=$timeRange} | 
    Where-Object {$_.Message -match "Signed: false"}

if ($unsignedDrivers) {
    Write-Host "    [!] WARNING: Found $($unsignedDrivers.Count) unsigned driver(s)" -ForegroundColor Red
    $unsignedDrivers | ForEach-Object {
        $_.Message -match "ImageLoaded:\s+(.+)" | Out-Null
        Write-Host "        - $($Matches[1])" -ForegroundColor Red
    }
} else {
    Write-Host "    [✓] No unsigned drivers detected" -ForegroundColor Green
}

# Check 2: Suspicious Process Spawns (Office/Browser -> PowerShell/CMD)
Write-Host "`n[*] Checking for suspicious process spawns..." -ForegroundColor Yellow
$suspiciousSpawns = Get-WinEvent -FilterHashtable @{LogName='Microsoft-Windows-Sysmon/Operational'; ID=1; StartTime=$timeRange} | 
    Where-Object {$_.Message -match "(powershell\.exe|cmd\.exe|wscript\.exe)" -and 
                  $_.Message -match "ParentImage.*?(winword\.exe|excel\.exe|powerpnt\.exe|chrome\.exe|firefox\.exe|msedge\.exe)"}

if ($suspiciousSpawns) {
    Write-Host "    [!] WARNING: Found $($suspiciousSpawns.Count) suspicious spawn(s)" -ForegroundColor Red
    $suspiciousSpawns | Select-Object -First 5 | ForEach-Object {
        $_.Message -match "ParentImage:\s+(.+)" | Out-Null
        $parent = $Matches[1]
        $_.Message -match "Image:\s+(.+)" | Out-Null
        $child = $Matches[1]
        Write-Host "        - $parent -> $child" -ForegroundColor Red
    }
    if ($suspiciousSpawns.Count -gt 5) {
        Write-Host "        ... and $($suspiciousSpawns.Count - 5) more" -ForegroundColor Red
    }
} else {
    Write-Host "    [✓] No suspicious process spawns detected" -ForegroundColor Green
}

# Check 3: New Persistence (AutoRun Registry Keys)
Write-Host "`n[*] Checking for new persistence mechanisms..." -ForegroundColor Yellow
$newPersistence = Get-WinEvent -FilterHashtable @{LogName='Microsoft-Windows-Sysmon/Operational'; ID=13; StartTime=$timeRange} | 
    Where-Object {$_.Message -match "\\(Run|RunOnce|RunServices)"}

if ($newPersistence) {
    Write-Host "    [!] WARNING: Found $($newPersistence.Count) new AutoRun key(s)" -ForegroundColor Red
    $newPersistence | Select-Object -First 5 | ForEach-Object {
        $_.Message -match "TargetObject:\s+(.+)" | Out-Null
        Write-Host "        - $($Matches[1])" -ForegroundColor Red
    }
    if ($newPersistence.Count -gt 5) {
        Write-Host "        ... and $($newPersistence.Count - 5) more" -ForegroundColor Red
    }
} else {
    Write-Host "    [✓] No new persistence keys detected" -ForegroundColor Green
}

# Check 4: System Binaries Making Network Connections
Write-Host "`n[*] Checking for unusual network activity..." -ForegroundColor Yellow
$suspiciousNetwork = Get-WinEvent -FilterHashtable @{LogName='Microsoft-Windows-Sysmon/Operational'; ID=3; StartTime=$timeRange} | 
    Where-Object {$_.Message -match "(svchost\.exe|rundll32\.exe|regsvr32\.exe|mshta\.exe)" -and 
                  $_.Message -match "Initiated:\s+true" -and
                  $_.Message -notmatch "DestinationIp:\s+(10\.|172\.(1[6-9]|2[0-9]|3[01])\.|192\.168\.|127\.)"} # Exclude private IPs

if ($suspiciousNetwork) {
    Write-Host "    [!] WARNING: Found $($suspiciousNetwork.Count) suspicious connection(s)" -ForegroundColor Red
    $suspiciousNetwork | Select-Object -First 5 | ForEach-Object {
        $_.Message -match "Image:\s+(.+)" | Out-Null
        $process = $Matches[1]
        $_.Message -match "DestinationIp:\s+([^\r\n]+)" | Out-Null
        $destIP = $Matches[1]
        Write-Host "        - $process -> $destIP" -ForegroundColor Red
    }
    if ($suspiciousNetwork.Count -gt 5) {
        Write-Host "        ... and $($suspiciousNetwork.Count - 5) more" -ForegroundColor Red
    }
} else {
    Write-Host "    [✓] No suspicious network connections detected" -ForegroundColor Green
}

# Check 5: Encoded PowerShell Commands (common evasion)
Write-Host "`n[*] Checking for encoded PowerShell commands..." -ForegroundColor Yellow
$encodedPS = Get-WinEvent -FilterHashtable @{LogName='Microsoft-Windows-Sysmon/Operational'; ID=1; StartTime=$timeRange} | 
    Where-Object {$_.Message -match "powershell.*?(-enc|-encodedcommand|-e\s)"}

if ($encodedPS) {
    Write-Host "    [!] WARNING: Found $($encodedPS.Count) encoded PowerShell command(s)" -ForegroundColor Red
    $encodedPS | Select-Object -First 3 | ForEach-Object {
        $_.Message -match "CommandLine:\s+(.+)" | Out-Null
        $cmdLine = $Matches[1]
        if ($cmdLine.Length -gt 100) { $cmdLine = $cmdLine.Substring(0, 100) + "..." }
        Write-Host "        - $cmdLine" -ForegroundColor Red
    }
    if ($encodedPS.Count -gt 3) {
        Write-Host "        ... and $($encodedPS.Count - 3) more" -ForegroundColor Red
    }
} else {
    Write-Host "    [✓] No encoded PowerShell detected" -ForegroundColor Green
}

# Summary
Write-Host "`n========================================" -ForegroundColor Cyan
$totalIssues = ($unsignedDrivers.Count + $suspiciousSpawns.Count + $newPersistence.Count + $suspiciousNetwork.Count + $encodedPS.Count)

if ($totalIssues -eq 0) {
    Write-Host "   RESULT: All checks passed! ✓" -ForegroundColor Green
} else {
    Write-Host "   RESULT: Found $totalIssues potential issue(s)" -ForegroundColor Red
    Write-Host "   Review details above and investigate" -ForegroundColor Red
}
Write-Host "========================================`n" -ForegroundColor Cyan

# Keep window open
Write-Host "Press any key to exit..." -ForegroundColor Gray
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
