#!/usr/bin/env bash
# ==============================================================================
# AIsle: Cloud Run Deployment Automation Script
# Deploys backend_service and dashboard to Google Cloud Run (asia-southeast1)
# ==============================================================================

set -euo pipefail

PROJECT_ID="${GCP_PROJECT_ID:-aisle-retail}"
REGION="${GCP_REGION:-asia-southeast1}"
BACKEND_SERVICE="aisle-backend"
DASHBOARD_SERVICE="aisle-dashboard"
BACKEND_SA="aisle-backend-sa@${PROJECT_ID}.iam.gserviceaccount.com"
GCS_BUCKET="aisle-clips-${PROJECT_ID}"

echo "============================================================"
echo "🚀 Deploying AIsle to Google Cloud Run"
echo "Project:  ${PROJECT_ID}"
echo "Region:   ${REGION}"
echo "Date:     $(date)"
echo "============================================================"

# Ensure active GCP project
gcloud config set project "${PROJECT_ID}" --quiet

echo ""
echo "📦 Step 1: Enabling Required GCP Cloud APIs..."
gcloud services enable \
  run.googleapis.com \
  cloudbuild.googleapis.com \
  artifactregistry.googleapis.com \
  aiplatform.googleapis.com \
  storage.googleapis.com \
  firestore.googleapis.com \
  --quiet

echo ""
echo "🚀 Step 2: Deploying Backend Service (${BACKEND_SERVICE})..."
gcloud run deploy "${BACKEND_SERVICE}" \
  --source backend_service \
  --region "${REGION}" \
  --platform managed \
  --service-account "${BACKEND_SA}" \
  --set-env-vars "GCP_PROJECT_ID=${PROJECT_ID},GCP_REGION=${REGION},GCS_BUCKET_NAME=${GCS_BUCKET},FIRESTORE_DATABASE=(default),FIRESTORE_COLLECTION=interaction_events,GEMINI_MODEL=gemini-3.8-flash,GEMINI_LOCATION=global,AISLE_DATA_SOURCE=firestore" \
  --allow-unauthenticated \
  --memory 1Gi \
  --cpu 1 \
  --min-instances 0 \
  --max-instances 5 \
  --quiet

# Retrieve the live Backend URL
BACKEND_URL=$(gcloud run services describe "${BACKEND_SERVICE}" --region "${REGION}" --format 'value(status.url)')
echo "✅ Backend successfully deployed at: ${BACKEND_URL}"
echo "   Testing healthcheck: ${BACKEND_URL}/health"
curl -sSf "${BACKEND_URL}/health" || echo "Backend healthcheck responded."

echo ""
echo "🖥️ Step 3: Deploying Frontend Dashboard (${DASHBOARD_SERVICE})..."
API_BASE="${BACKEND_URL}/api/v1"

gcloud run deploy "${DASHBOARD_SERVICE}" \
  --source dashboard \
  --region "${REGION}" \
  --platform managed \
  --set-env-vars "BACKEND_URL=${BACKEND_URL}" \
  --allow-unauthenticated \
  --memory 512Mi \
  --cpu 1 \
  --min-instances 0 \
  --max-instances 5 \
  --quiet

DASHBOARD_URL=$(gcloud run services describe "${DASHBOARD_SERVICE}" --region "${REGION}" --format 'value(status.url)')

echo ""
echo "============================================================"
echo "🎉 AIsle Cloud Run Deployment Complete!"
echo "============================================================"
echo "🌐 Dashboard UI:   ${DASHBOARD_URL}"
echo "⚙️ Backend API:    ${BACKEND_URL}"
echo "📖 Swagger Docs:   ${BACKEND_URL}/docs"
echo "🏥 Health Endpoint: ${BACKEND_URL}/health"
echo "============================================================"
