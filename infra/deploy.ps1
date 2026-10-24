# Windows variant of deploy.sh: AWS CLI on Windows, Docker Engine inside WSL (Ubuntu-24.04).
# Usage (from the repo root): powershell -File infra/deploy.ps1 [-Stack kampan] [-Region us-east-1]
param([string]$Stack = "kampan", [string]$Region = "us-east-1", [string]$Distro = "Ubuntu-24.04")
$ErrorActionPreference = "Stop"
$env:WSL_UTF8 = "1"

function Check($what) { if ($LASTEXITCODE -ne 0) { throw "$what failed (exit $LASTEXITCODE)" } }

$account = aws sts get-caller-identity --query Account --output text; Check "sts"
$registry = "$account.dkr.ecr.$Region.amazonaws.com"
$root = (Get-Location).Path
$wslRoot = "/mnt/" + $root.Substring(0, 1).ToLower() + ($root.Substring(2) -replace '\\', '/')

aws ecr describe-repositories --repository-names kampan --region $Region 2>$null | Out-Null
if ($LASTEXITCODE -ne 0) {
  aws ecr create-repository --repository-name kampan --image-scanning-configuration scanOnPush=true --region $Region | Out-Null
  Check "ecr create"
}

wsl.exe -d $Distro -- bash -lc "cd '$wslRoot' && docker build -t kampan:latest ."; Check "docker build"
aws ecr get-login-password --region $Region | wsl.exe -d $Distro -- docker login --username AWS --password-stdin $registry; Check "docker login"
wsl.exe -d $Distro -- docker tag kampan:latest "$registry/kampan:latest"; Check "docker tag"
wsl.exe -d $Distro -- docker push "$registry/kampan:latest"; Check "docker push"
$digest = aws ecr describe-images --repository-name kampan --image-ids imageTag=latest --query "imageDetails[0].imageDigest" --output text --region $Region; Check "describe-images"

aws cloudformation deploy --stack-name $Stack --template-file infra/template.yaml --capabilities CAPABILITY_IAM --region $Region --parameter-overrides "ImageUri=$registry/kampan@$digest"; Check "cloudformation deploy"

$outputs = aws cloudformation describe-stacks --stack-name $Stack --region $Region --query "Stacks[0].Outputs" --output json | ConvertFrom-Json
$bucket = ($outputs | Where-Object OutputKey -eq "Bucket").OutputValue
aws s3 sync out/storage/samples "s3://$bucket/samples" --region $Region; Check "s3 sync"
Write-Output ("App: " + ($outputs | Where-Object OutputKey -eq "Url").OutputValue)
Write-Output ("Dashboard: " + ($outputs | Where-Object OutputKey -eq "Dashboard").OutputValue)
