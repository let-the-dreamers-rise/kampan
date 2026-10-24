#!/usr/bin/env bash
# Build the Lambda image, push it to ECR, deploy the CloudFormation stack and upload the sample clips.
# Needs: AWS CLI v2 with credentials, Docker, Python 3.12 with requirements.txt installed.
# Usage: STACK=kampan AWS_REGION=us-east-1 infra/deploy.sh
set -euo pipefail
STACK="${STACK:-kampan}"
REGION="${AWS_REGION:-us-east-1}"
REPO="${REPO:-kampan}"
ACCOUNT="$(aws sts get-caller-identity --query Account --output text)"
REGISTRY="${ACCOUNT}.dkr.ecr.${REGION}.amazonaws.com"

if [ ! -f app/samples.json ]; then python -m tools.make_samples --out out/storage; fi

aws ecr describe-repositories --repository-names "$REPO" --region "$REGION" >/dev/null 2>&1 \
  || aws ecr create-repository --repository-name "$REPO" --image-scanning-configuration scanOnPush=true \
       --region "$REGION" >/dev/null

docker build --platform linux/amd64 -t "$REPO:latest" .
aws ecr get-login-password --region "$REGION" | docker login --username AWS --password-stdin "$REGISTRY"
docker tag "$REPO:latest" "$REGISTRY/$REPO:latest"
docker push "$REGISTRY/$REPO:latest"
DIGEST="$(aws ecr describe-images --repository-name "$REPO" --image-ids imageTag=latest \
  --query 'imageDetails[0].imageDigest' --output text --region "$REGION")"

aws cloudformation deploy --stack-name "$STACK" --template-file infra/template.yaml \
  --capabilities CAPABILITY_IAM --region "$REGION" \
  --parameter-overrides "ImageUri=$REGISTRY/$REPO@$DIGEST"

out() { aws cloudformation describe-stacks --stack-name "$STACK" --region "$REGION" \
  --query "Stacks[0].Outputs[?OutputKey=='$1'].OutputValue" --output text; }
aws s3 sync out/storage/samples "s3://$(out Bucket)/samples" --region "$REGION"
echo "App: $(out Url)"
echo "Dashboard: $(out Dashboard)"
