# Flask PowerShell Runner Script
# This script mimics the "Python: Flask" configuration from launch.json

# Set working directory to the project root
# Adjust this path if you're running the script from elsewhere
$workspaceFolder = "d:\_LUKY\DiscogsApp"
Set-Location $workspaceFolder

# Set environment variables (same as in launch.json)
$env:FLASK_APP = "server/app.py"
$env:FLASK_DEBUG = "1"

# Check if .env file exists and load it
$envFile = Join-Path $workspaceFolder "server\.env"
if (Test-Path $envFile) {
    Get-Content $envFile | ForEach-Object {
        if ($_ -match "^\s*([^#][^=]+)=(.*)$") {
            $key = $matches[1].Trim()
            $value = $matches[2].Trim()
            # Remove quotes if present
            if ($value -match '^"(.*)"$' -or $value -match "^'(.*)'$") {
                $value = $matches[1]
            }
            # Set environment variable
            [Environment]::SetEnvironmentVariable($key, $value, "Process")
            Write-Host "Set environment variable: $key"
        }
    }
}

# Run Flask with the same arguments as in launch.json
Write-Host "Starting Flask application..."
python -m flask run --no-debugger --no-reload --host=0.0.0.0