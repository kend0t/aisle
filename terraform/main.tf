terraform {
  required_version = ">= 1.5.0"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = ">= 5.0, < 7.0"
    }
    local = {
      source  = "hashicorp/local"
      version = "~> 2.5"
    }
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}

# ------------------------------------------------------------------------------
# 1. Enable Required GCP APIs
# ------------------------------------------------------------------------------
locals {
  required_apis = [
    "aiplatform.googleapis.com", # Vertex AI / Gemini
    "storage.googleapis.com",    # Cloud Storage (Video Clips)
    "firestore.googleapis.com",  # Cloud Firestore (Metrics DB)
    "run.googleapis.com",        # Cloud Run (Backend / Dashboard Hosting)
    "iam.googleapis.com"         # Identity and Access Management
  ]
}

resource "google_project_service" "enabled_apis" {
  for_each           = toset(local.required_apis)
  project            = var.project_id
  service            = each.key
  disable_on_destroy = false
}

# ------------------------------------------------------------------------------
# 2. Google Cloud Storage Bucket for Video Clips
# ------------------------------------------------------------------------------
locals {
  effective_bucket_name = var.bucket_name != "" ? var.bucket_name : "aisle-clips-${var.project_id}"
}

resource "google_storage_bucket" "video_clips" {
  name                        = local.effective_bucket_name
  location                    = var.region
  project                     = var.project_id
  uniform_bucket_level_access = true
  force_destroy               = false

  # Optional auto-deletion to keep storage costs negligible during testing
  dynamic "lifecycle_rule" {
    for_each = var.clip_retention_days > 0 ? [1] : []
    content {
      action {
        type = "Delete"
      }
      condition {
        age = var.clip_retention_days
      }
    }
  }

  depends_on = [google_project_service.enabled_apis]
}

# ------------------------------------------------------------------------------
# 3. Cloud Firestore Database (Native Mode)
# ------------------------------------------------------------------------------
resource "google_firestore_database" "database" {
  project                 = var.project_id
  name                    = "(default)"
  location_id             = var.region
  type                    = "FIRESTORE_NATIVE"
  delete_protection_state = "DELETE_PROTECTION_DISABLED"
  deletion_policy         = "DELETE"

  depends_on = [google_project_service.enabled_apis]
}

# ------------------------------------------------------------------------------
# 4. Service Account & IAM Roles for Backend / Camera Node
# ------------------------------------------------------------------------------
resource "google_service_account" "backend_sa" {
  project      = var.project_id
  account_id   = var.service_account_name
  display_name = "AIsle Backend & Pipeline Service Account"

  depends_on = [google_project_service.enabled_apis]
}

locals {
  backend_roles = [
    "roles/aiplatform.user",     # Call Vertex AI Gemini 1.5
    "roles/storage.objectAdmin", # Read/Write video clips to Cloud Storage
    "roles/datastore.user"       # Read/Write records in Cloud Firestore
  ]
}

resource "google_project_iam_member" "sa_roles" {
  for_each = toset(local.backend_roles)
  project  = var.project_id
  role     = each.key
  member   = "serviceAccount:${google_service_account.backend_sa.email}"
}

# ------------------------------------------------------------------------------
# 5. Service Account Key Generation (for Local Development)
# ------------------------------------------------------------------------------
resource "google_service_account_key" "local_key" {
  count              = var.generate_key_file ? 1 : 0
  service_account_id = google_service_account.backend_sa.name
}

resource "local_file" "service_account_json" {
  count           = var.generate_key_file ? 1 : 0
  content_base64  = google_service_account_key.local_key[0].private_key
  filename        = "${path.module}/${var.key_output_path}"
  file_permission = "0600"
}
