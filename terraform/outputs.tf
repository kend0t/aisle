output "project_id" {
  description = "The GCP Project ID."
  value       = var.project_id
}

output "region" {
  description = "The GCP region."
  value       = var.region
}

output "storage_bucket_name" {
  description = "The name of the Google Cloud Storage bucket."
  value       = google_storage_bucket.video_clips.name
}

output "storage_bucket_uri" {
  description = "The gs:// URI of the storage bucket."
  value       = "gs://${google_storage_bucket.video_clips.name}"
}

output "firestore_database" {
  description = "The Firestore database name."
  value       = google_firestore_database.database.name
}

output "service_account_email" {
  description = "Email of the generated service account."
  value       = google_service_account.backend_sa.email
}

output "credentials_file_path" {
  description = "Path where the service account JSON key is saved (if generated)."
  value       = var.generate_key_file ? abspath("${path.module}/${var.key_output_path}") : "Key file generation was skipped."
}

output "backend_env_snippet" {
  description = "Copy-pasteable environment configuration for backend_service/.env"
  value       = <<-EOT
    # Paste into backend_service/.env
    GCP_PROJECT_ID=${var.project_id}
    GCP_REGION=${var.region}
    GCS_BUCKET_NAME=${google_storage_bucket.video_clips.name}
    FIRESTORE_DATABASE=(default)
    FIRESTORE_COLLECTION=interaction_events
    GEMINI_MODEL=gemini-1.5-flash-002
    GOOGLE_APPLICATION_CREDENTIALS=${var.generate_key_file ? abspath("${path.module}/${var.key_output_path}") : ""}
    HOST=0.0.0.0
    PORT=8000
    ENVIRONMENT=development
    LOG_LEVEL=INFO
  EOT
}
