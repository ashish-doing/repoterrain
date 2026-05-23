#!/bin/bash
# RepoTerrain — Deploy to Google Cloud Run
# Usage: ./deploy.sh

set -e

PROJECT_ID=${GCP_PROJECT:-"your-gcp-project-id"}
REGION="us-central1"
SERVICE_NAME="repoterrain"
IMAGE="gcr.io/${PROJECT_ID}/${SERVICE_NAME}"

echo "🏔  RepoTerrain — Cloud Run Deploy"
echo "   Project: $PROJECT_ID"
echo "   Region:  $REGION"
echo ""

# Build + push
echo "📦 Building Docker image..."
gcloud builds submit --tag "$IMAGE" .

# Deploy
echo "🚀 Deploying to Cloud Run..."
gcloud run deploy "$SERVICE_NAME" \
  --image "$IMAGE" \
  --platform managed \
  --region "$REGION" \
  --allow-unauthenticated \
  --memory 2Gi \
  --cpu 2 \
  --concurrency 10 \
  --timeout 300 \
  --set-env-vars "GCP_PROJECT=${PROJECT_ID},GCP_LOCATION=${REGION}" \
  --set-secrets "GITLAB_TOKEN=gitlab-token:latest"

echo ""
echo "✅ Deployed! URL:"
gcloud run services describe "$SERVICE_NAME" --region "$REGION" --format "value(status.url)"
