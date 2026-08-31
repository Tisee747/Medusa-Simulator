# Backend deployment

The active server directory is `~/simulator`. The server keeps `.env` outside the upload package, while `simulator.log` and `simulator.pid` are generated only at runtime.

Paste this complete block into PowerShell. It can be run from any directory:

```powershell
$ErrorActionPreference = "Stop"
$Key = "C:\Medusa\ybda-aws-osimapi-intern.pem"
$SourceRoot = "C:\Medusa\Simulator\Backend"
# Fill deployment identity locally; do not commit company-specific values.
$ServerUser = ""
$ServerHost = ""
$Package = "C:\Medusa\simulator_backend.zip"

if (-not (Test-Path -LiteralPath $Key)) { throw "SSH key not found: $Key" }
if (-not (Test-Path -LiteralPath $SourceRoot)) { throw "Backend source not found: $SourceRoot" }
if (-not (Get-Command tar.exe -ErrorAction SilentlyContinue)) { throw "tar.exe not found." }

if (Test-Path -LiteralPath $Package) { Remove-Item -LiteralPath $Package -Force }
tar.exe -a -c -f $Package -C $SourceRoot app requirements.txt start.sh stop.sh restart.sh deploy.sh
if ($LASTEXITCODE -ne 0) { throw "Failed to create deployment package." }

$Remote = "${ServerUser}@${ServerHost}"
scp -i $Key $Package "${Remote}:~/simulator_backend.zip"
Get-Content -Raw -LiteralPath (Join-Path $SourceRoot "deploy.sh") | ssh -i $Key $Remote "tr -d '\r' | bash -s -- ~/simulator_backend.zip"
ssh -i $Key $Remote "curl -fsS http://127.0.0.1:8011/health"
```

`deploy.sh` stops the current process, stages the new package, preserves the existing server `.env`, removes old runtime/cache files, swaps the release directory, deletes the uploaded archive, and starts the backend again. The first run also migrates `~/simulator_alpro` to `~/simulator`.

The deployment identity fields are intentionally blank in this public document. Fill them only in a private local copy before deployment.

