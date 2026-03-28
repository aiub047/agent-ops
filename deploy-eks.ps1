<#
.SYNOPSIS
    Build, tag, push a Docker image to ECR and roll out a new version on EKS.

.DESCRIPTION
    Automates the full deployment pipeline:
      1. Builds the Docker image from the current directory.
      2. Tags it for the ECR repository.
      3. Pushes the image to ECR.
      4. Updates the running Kubernetes deployment with the new image.

.PARAMETER Version
    The version suffix appended to the image tag (e.g. "1", "2", "1.0.3").
    The resulting tag will be "vX" where X is this value.

.PARAMETER SkipBuild
    Skip the docker build step (useful when the image is already built locally).

.PARAMETER DryRun
    Print the commands that would be executed without actually running them.

.EXAMPLE
    .\deploy-eks.ps1 -Version 3

.EXAMPLE
    .\deploy-eks.ps1 -Version 1.2.0 -DryRun

.EXAMPLE
    .\deploy-eks.ps1 -Version 5 -SkipBuild
#>

[CmdletBinding(SupportsShouldProcess)]
param (
    [Parameter(Mandatory = $true, HelpMessage = "Version number/string for the image tag (e.g. 3 → agent-ops:v3)")]
    [ValidateNotNullOrEmpty()]
    [string] $Version,

    [switch] $SkipBuild,

    [switch] $DryRun
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

# ── Configuration ─────────────────────────────────────────────────────────────
$ImageName       = "agent-ops"
$Tag             = "v$Version"
$AwsAccountId    = "314630006302"
$AwsRegion       = "us-east-1"
$EcrRepo         = "$AwsAccountId.dkr.ecr.$AwsRegion.amazonaws.com/$ImageName"
$FullImage       = "${EcrRepo}:${Tag}"
$K8sDeployment   = "agent-ops"
$K8sContainer    = "agent-ops"

# ── Helpers ───────────────────────────────────────────────────────────────────
function Invoke-Step {
    <#
    .SYNOPSIS
        Run a shell command, honouring the -DryRun flag.
    #>
    param (
        [string]   $Description,
        [string[]] $Cmd
    )

    $cmdLine = $Cmd -join " "
    Write-Host ""
    Write-Host "► $Description" -ForegroundColor Cyan
    Write-Host "  $cmdLine"     -ForegroundColor DarkGray

    if ($DryRun) {
        Write-Host "  [DRY RUN] Skipped." -ForegroundColor Yellow
        return
    }

    & $Cmd[0] $Cmd[1..($Cmd.Length - 1)]

    if ($LASTEXITCODE -ne 0) {
        Write-Error "Command failed with exit code ${LASTEXITCODE}: $cmdLine"
        exit $LASTEXITCODE
    }
}

# ── Main ──────────────────────────────────────────────────────────────────────
Write-Host "==========================================" -ForegroundColor Green
Write-Host " agent-ops  →  EKS deployment" -ForegroundColor Green
Write-Host "  Image : $FullImage" -ForegroundColor Green
if ($DryRun)   { Write-Host "  Mode  : DRY RUN (no changes)" -ForegroundColor Yellow }
if ($SkipBuild){ Write-Host "  Build : SKIPPED"              -ForegroundColor Yellow }
Write-Host "==========================================" -ForegroundColor Green

# Step 1 – Authenticate Docker with ECR
# The pipe requires a real shell invocation; PowerShell native piping won't
# pass a raw string to docker login's --password-stdin correctly.
$loginCmd = "aws ecr get-login-password --region $AwsRegion | docker login --username AWS --password-stdin $AwsAccountId.dkr.ecr.$AwsRegion.amazonaws.com"
Write-Host ""
Write-Host "► Authenticating Docker with ECR" -ForegroundColor Cyan
Write-Host "  $loginCmd" -ForegroundColor DarkGray
if ($DryRun) {
    Write-Host "  [DRY RUN] Skipped." -ForegroundColor Yellow
} else {
    cmd /c $loginCmd
    if ($LASTEXITCODE -ne 0) {
        Write-Error "ECR login failed."
        exit $LASTEXITCODE
    }
}

# Step 2 – Build
if (-not $SkipBuild) {
    Invoke-Step "Building Docker image  ${ImageName}:${Tag}" @(
        "docker", "build", "-t", "${ImageName}:${Tag}", "."
    )
}

# Step 3 – Tag
Invoke-Step "Tagging  ${ImageName}:${Tag}  →  $FullImage" @(
    "docker", "tag", "${ImageName}:${Tag}", $FullImage
)

# Step 4 – Push
Invoke-Step "Pushing image to ECR" @(
    "docker", "push", $FullImage
)

# Step 5 – Roll out on EKS
Invoke-Step "Updating Kubernetes deployment '$K8sDeployment' (container: $K8sContainer)" @(
    "kubectl", "set", "image",
    "deployment/$K8sDeployment",
    "${K8sContainer}=${FullImage}"
)

# Step 6 – Wait for rollout
Invoke-Step "Waiting for rollout to complete" @(
    "kubectl", "rollout", "status", "deployment/$K8sDeployment"
)

Write-Host ""
Write-Host "OK  Deployment of $FullImage completed successfully." -ForegroundColor Green


