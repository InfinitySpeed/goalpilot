param(
    [string]$Source = '',
    [string]$HostName = 'auto',
    [string]$Provider = '',
    [string]$Target = '',
    [switch]$Doctor,
    [switch]$DryRun,
    [switch]$ManagedPython
)
$ErrorActionPreference = 'Stop'
$runtimeRoot = if ($env:GOALPILOT_RUNTIME_DIR) { $env:GOALPILOT_RUNTIME_DIR } else { Join-Path $env:LOCALAPPDATA 'GoalPilot\runtime' }
$pythonExec = $null
if (-not $ManagedPython) {
    foreach ($candidate in @('python3', 'python')) {
        $command = Get-Command $candidate -ErrorAction SilentlyContinue
        if ($command -and $command.Source -notmatch 'WindowsApps') {
            $found = & $command.Source -c 'import sys; sys.exit(1) if sys.version_info<(3,11) else print(sys.executable)' 2>$null
            if ($LASTEXITCODE -eq 0) { $pythonExec = [string]$found; break }
        }
    }
}
$scratch = Join-Path ([IO.Path]::GetTempPath()) ('goalpilot-' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $scratch | Out-Null
try {
    if (-not $pythonExec) {
        $bin = Join-Path $runtimeRoot 'bin'
        New-Item -ItemType Directory -Force -Path $bin | Out-Null
        $uvCommand = Get-Command uv -ErrorAction SilentlyContinue
        $uvExec = if ($uvCommand) { $uvCommand.Source } else { Join-Path $bin 'uv.exe' }
        if (-not (Test-Path $uvExec)) {
            $installer = Join-Path $scratch 'uv-install.ps1'
            Invoke-WebRequest 'https://astral.sh/uv/install.ps1' -OutFile $installer
            $env:UV_INSTALL_DIR = $bin
            $env:UV_NO_MODIFY_PATH = '1'
            & $installer
            if (-not (Test-Path $uvExec)) { throw 'Managed runtime setup could not install uv.' }
        }
        $env:UV_PYTHON_INSTALL_DIR = Join-Path $runtimeRoot 'python'
        & $uvExec python install 3.12 --quiet
        if ($LASTEXITCODE -ne 0) { throw 'Managed Python installation failed.' }
        $pythonExec = ([string](& $uvExec python find --managed-python 3.12)).Trim()
        if ($LASTEXITCODE -ne 0 -or -not (Test-Path $pythonExec)) { throw 'Managed Python could not be located.' }
    }
    if (-not $Source) {
        $archive = Join-Path $scratch 'source.zip'
        Invoke-WebRequest 'https://github.com/InfinitySpeed/goalpilot/archive/refs/heads/main.zip' -OutFile $archive
        Expand-Archive $archive -DestinationPath (Join-Path $scratch 'source')
        $Source = (Get-ChildItem (Join-Path $scratch 'source') -Directory | Select-Object -First 1).FullName
    }
    $arguments = @('-X', 'utf8', (Join-Path $Source 'install.py'), '--host', $HostName)
    if ($Provider) { $arguments += @('--provider', $Provider) }
    if ($Target) { $arguments += @('--target', $Target) }
    if ($Doctor) { $arguments += '--doctor' }
    if ($DryRun) { $arguments += '--dry-run' }
    $env:PYTHONUTF8 = '1'
    & $pythonExec @arguments
    if ($LASTEXITCODE -ne 0) { throw 'GoalPilot installation or verification failed. See the diagnostic above.' }
} finally {
    Remove-Item -Recurse -Force $scratch
}
