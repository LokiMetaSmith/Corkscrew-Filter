<#
.SYNOPSIS
    Deploys or repairs Podman on Windows, resolving WSL/Hyper-V corruption.

.DESCRIPTION
    This script will:
    1. Check if Podman is installed. If not, install it using winget.
    2. Forcefully remove any existing Podman machines to resolve corruption.
    3. Shut down WSL to release any locks.
    4. Unregister any lingering Podman WSL distributions.
    5. Re-initialize and start a fresh Podman machine.
    6. Verify functionality.
#>

Write-Host "Starting Podman deployment and repair process..." -ForegroundColor Cyan

# 1. Check Winget availability
$wingetAvailable = [bool](Get-Command "winget" -ErrorAction SilentlyContinue)
if (!$wingetAvailable) {
    Write-Warning "winget is not available on this system. You may need to install it from the Microsoft Store."
}

# 2. Check and Install Podman
$podmanInstalled = [bool](Get-Command "podman" -ErrorAction SilentlyContinue)

if (!$podmanInstalled) {
    Write-Host "Podman is not installed. Attempting to install via winget..." -ForegroundColor Yellow

    if ($wingetAvailable) {
        Write-Host "Searching for Podman..."
        $searchResult = winget search podman
        $podmanId = $null

        if ($searchResult) {
            foreach ($line in $searchResult) {
                if ($line -match "Podman") {
                    $parts = $line -split '\s{2,}'
                    foreach ($part in $parts) {
                        if ($part -match "RedHat\.Podman") {
                            $podmanId = $part
                            break
                        }
                    }
                    if ($podmanId) { break }
                }
            }
        }

        if (!$podmanId) {
            Write-Host "Could not extract specific ID, using generic 'podman'."
            $podmanId = "podman"
        }

        Write-Host "Installing Podman ($podmanId)..."
        winget install --id $podmanId --exact --accept-package-agreements --accept-source-agreements

        # Refresh environment variables for the current session
        $env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")

        if (!(Get-Command "podman" -ErrorAction SilentlyContinue)) {
            Write-Error "Failed to install Podman or it is not in the PATH. Please install it manually."
            exit 1
        }
    } else {
        Write-Error "Podman is not installed and winget is not available. Please install Podman manually."
        exit 1
    }
} else {
    Write-Host "Podman is already installed." -ForegroundColor Green
}

# 3. Stop and remove existing Podman machines
Write-Host "Cleaning up existing Podman machines..." -ForegroundColor Yellow
if (Get-Command "podman" -ErrorAction SilentlyContinue) {
    $machines = podman machine list --format "{{.Name}}" 2>$null
    if ($LASTEXITCODE -eq 0 -and $machines) {
        foreach ($machine in $machines) {
            $machineName = $machine.Trim()
            if (![string]::IsNullOrEmpty($machineName)) {
                Write-Host "Removing Podman machine: $machineName"
                podman machine stop $machineName 2>$null
                podman machine rm -f $machineName 2>$null
            }
        }
    } else {
        Write-Host "Attempting to remove default Podman machines..."
        podman machine stop default 2>$null
        podman machine rm -f default 2>$null
        podman machine stop podman-machine-default 2>$null
        podman machine rm -f podman-machine-default 2>$null
    }
}

# 4. Shut down WSL
Write-Host "Shutting down WSL to clear locks..." -ForegroundColor Yellow
wsl --shutdown

# 5. Dynamically find and unregister leftover Podman WSL distributions
Write-Host "Checking for lingering Podman WSL distributions..." -ForegroundColor Yellow
$wslList = wsl --list --quiet 2>$null
if ($wslList) {
    # Remove carriage returns and null characters (UTF-16 encoding artifacts)
    $distros = $wslList -split "`n" | ForEach-Object { $_ -replace "`r", "" -replace "`0", "" } | Where-Object { $_ -ne "" }

    foreach ($distro in $distros) {
        if ($distro -match "podman") {
            Write-Host "Unregistering lingering WSL distribution: $distro" -ForegroundColor Yellow
            wsl --unregister $distro 2>$null
        }
    }
}

# 6. Initialize and start a fresh Podman machine
Write-Host "Initializing a fresh Podman machine..." -ForegroundColor Cyan
podman machine init
if ($LASTEXITCODE -ne 0) {
    Write-Error "Failed to initialize Podman machine."
    exit 1
}

Write-Host "Starting Podman machine..." -ForegroundColor Cyan
podman machine start
if ($LASTEXITCODE -ne 0) {
    Write-Error "Failed to start Podman machine."
    exit 1
}

# 7. Verify functionality
Write-Host "Verifying Podman installation and machine status..." -ForegroundColor Cyan
podman info

if ($LASTEXITCODE -eq 0) {
    Write-Host "Podman successfully deployed and repaired!" -ForegroundColor Green
} else {
    Write-Error "Podman info failed. There may still be issues."
    exit 1
}
