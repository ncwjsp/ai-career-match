#!/usr/bin/env bash
# Deploy the A-07 inference container as a SageMaker Serverless endpoint.
# Owner: M3 (C-06). See docs/integration/DEPLOYMENT.md.
#
# This CREATES BILLABLE AWS RESOURCES (ECR image, S3 object, SageMaker model,
# endpoint config and serverless endpoint). It refuses to run unless
# CONFIRM_PAID_RESOURCES=yes. Create the AWS Budgets alert first.
#
# Required environment:
#   AWS_REGION           e.g. ap-southeast-1
#   RESUME_BUCKET        private bucket; the model goes under models/
#   SAGEMAKER_ROLE_ARN   execution role with sagemaker-execution-policy.json
#   MODEL_DIR            packaged model directory (scripts.package_resume_model)
# Optional:
#   ENDPOINT_NAME (career-resume-inference), MEMORY_MB (2048), MAX_CONCURRENCY (1)
#
# Run from the repository root with AWS credentials already configured.
set -euo pipefail

: "${AWS_REGION:?}" "${RESUME_BUCKET:?}" "${SAGEMAKER_ROLE_ARN:?}" "${MODEL_DIR:?}"
ENDPOINT_NAME="${ENDPOINT_NAME:-career-resume-inference}"
MEMORY_MB="${MEMORY_MB:-2048}"
MAX_CONCURRENCY="${MAX_CONCURRENCY:-1}"

if [ "${CONFIRM_PAID_RESOURCES:-}" != "yes" ]; then
  echo "Refusing: set CONFIRM_PAID_RESOURCES=yes after creating the budget alert." >&2
  exit 2
fi
[ -f "$MODEL_DIR/config.json" ] || { echo "MODEL_DIR has no packaged model." >&2; exit 2; }

ACCOUNT_ID="$(aws sts get-caller-identity --query Account --output text)"
TAG="$(git rev-parse --short HEAD)"
REGISTRY="$ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com"
IMAGE="$REGISTRY/$ENDPOINT_NAME:$TAG"
ARTIFACT="s3://$RESUME_BUCKET/models/$TAG/model.tar.gz"
VERSION="$ENDPOINT_NAME-$TAG"

echo "== ECR image $IMAGE"
aws ecr describe-repositories --region "$AWS_REGION" --repository-names "$ENDPOINT_NAME" >/dev/null 2>&1 \
  || aws ecr create-repository --region "$AWS_REGION" --repository-name "$ENDPOINT_NAME" >/dev/null
aws ecr get-login-password --region "$AWS_REGION" | docker login --username AWS --password-stdin "$REGISTRY"
# SageMaker needs a single-platform Docker v2 manifest, so no provenance index.
docker buildx build --platform linux/amd64 --provenance=false \
  -f ml/resume/Dockerfile -t "$IMAGE" --push .

echo "== Model artifact $ARTIFACT"
ARCHIVE="$(mktemp -d)/model.tar.gz"
tar -czf "$ARCHIVE" -C "$MODEL_DIR" .
aws s3 cp "$ARCHIVE" "$ARTIFACT" --region "$AWS_REGION"

echo "== Model and serverless config $VERSION"
aws sagemaker create-model --region "$AWS_REGION" --model-name "$VERSION" \
  --execution-role-arn "$SAGEMAKER_ROLE_ARN" \
  --primary-container "Image=$IMAGE,ModelDataUrl=$ARTIFACT"
aws sagemaker create-endpoint-config --region "$AWS_REGION" --endpoint-config-name "$VERSION" \
  --production-variants "VariantName=AllTraffic,ModelName=$VERSION,ServerlessConfig={MemorySizeInMB=$MEMORY_MB,MaxConcurrency=$MAX_CONCURRENCY}"

if aws sagemaker describe-endpoint --region "$AWS_REGION" --endpoint-name "$ENDPOINT_NAME" >/dev/null 2>&1; then
  echo "== Updating endpoint $ENDPOINT_NAME"
  aws sagemaker update-endpoint --region "$AWS_REGION" --endpoint-name "$ENDPOINT_NAME" --endpoint-config-name "$VERSION"
else
  echo "== Creating endpoint $ENDPOINT_NAME"
  aws sagemaker create-endpoint --region "$AWS_REGION" --endpoint-name "$ENDPOINT_NAME" --endpoint-config-name "$VERSION"
fi
aws sagemaker wait endpoint-in-service --region "$AWS_REGION" --endpoint-name "$ENDPOINT_NAME"
echo "Ready. Set SAGEMAKER_EMBEDDING_ENDPOINT=$ENDPOINT_NAME on both Railway services."
