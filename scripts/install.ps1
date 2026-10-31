<#
.SYNOPSIS
    Downly Launcher Installer
.DESCRIPTION
    Registers the Downly command in the Windows User PATH environment variable
    so Downly can be launched from anywhere by typing 'Downly'.
#>

[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$projectRoot = Split-Path -Parent $scriptDir
$binDir = Join-Path $projectRoot "bin"

if (-not (Test-Path $binDir)) {
    New-Item -ItemType Directory -Path $binDir -Force | Out-Null
}

Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "          Downly Command-Line Launcher Installer            " -ForegroundColor White
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""

# 1. Update Windows User Environment PATH
$userPath = [Environment]::GetEnvironmentVariable("Path", "User")
if ([string]::IsNullOrWhiteSpace($userPath)) {
    $userPath = ""
}

$pathEntries = $userPath -split ';' | Where-Object { $_ -ne "" }

if ($pathEntries -notcontains $binDir) {
    Write-Host "[*] Adding '$binDir' to User PATH environment variable..." -ForegroundColor Yellow
    $newPath = ($pathEntries + $binDir) -join ';'
    [Environment]::SetEnvironmentVariable("Path", $newPath, "User")
    Write-Host "[+] Successfully registered in Windows User PATH." -ForegroundColor Green
} else {
    Write-Host "[i] '$binDir' is already registered in User PATH." -ForegroundColor Gray
}

# 2. Update Current Session PATH
if (($env:Path -split ';') -notcontains $binDir) {
    $env:Path = "$binDir;$env:Path"
    Write-Host "[+] Updated active session PATH." -ForegroundColor Green
}

# 3. Broadcast WM_SETTINGCHANGE to notify Windows Explorer & Terminal apps
try {
    $definition = @"
using System;
using System.Runtime.InteropServices;
public class EnvNotifier {
    [DllImport("user32.dll", SetLastError = true, CharSet = CharSet.Auto)]
    public static extern IntPtr SendMessageTimeout(
        IntPtr hWnd,
        uint Msg,
        UIntPtr wParam,
        string lParam,
        uint fuFlags,
        uint uTimeout,
        out UIntPtr lpdwResult
    );
}
"@
    if (-not ([System.Management.Automation.PSTypeName]'EnvNotifier').Type) {
        Add-Type -TypeDefinition $definition
    }
    $HWND_BROADCAST = [IntPtr]0xffff
    $WM_SETTINGCHANGE = 0x001A
    $result = [UIntPtr]::Zero
    [EnvNotifier]::SendMessageTimeout($HWND_BROADCAST, $WM_SETTINGCHANGE, [UIntPtr]::Zero, "Environment", 2, 3000, [ref]$result) | Out-Null
    Write-Host "[+] Broadcast environment update to open windows." -ForegroundColor Green
} catch {
    # Non-fatal if broadcast fails
}

Write-Host ""
Write-Host "------------------------------------------------------------" -ForegroundColor DarkGray
Write-Host " Downly is ready! You can now launch it by typing:" -ForegroundColor White
Write-Host "     Downly" -ForegroundColor Cyan
Write-Host " from any Windows Terminal, PowerShell, or Command Prompt." -ForegroundColor White
Write-Host "------------------------------------------------------------" -ForegroundColor DarkGray
Write-Host ""

