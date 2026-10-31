<#
.SYNOPSIS
    Downly Launcher Uninstaller
.DESCRIPTION
    Removes the Downly command from the Windows User PATH environment variable.
#>

[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$projectRoot = Split-Path -Parent $scriptDir
$binDir = Join-Path $projectRoot "bin"

Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "         Downly Command-Line Launcher Uninstaller           " -ForegroundColor White
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""

$userPath = [Environment]::GetEnvironmentVariable("Path", "User")
if ([string]::IsNullOrWhiteSpace($userPath)) {
    Write-Host "[i] User PATH is empty. Nothing to uninstall." -ForegroundColor Gray
    return
}

$pathEntries = $userPath -split ';' | Where-Object { $_ -ne "" -and $_ -ne $binDir }
$newPath = $pathEntries -join ';'
[Environment]::SetEnvironmentVariable("Path", $newPath, "User")
Write-Host "[+] Removed '$binDir' from User PATH environment variable." -ForegroundColor Green

# Broadcast WM_SETTINGCHANGE
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
} catch {}

Write-Host "[+] Uninstallation complete. 'Downly' command unregistered." -ForegroundColor Green
Write-Host ""

