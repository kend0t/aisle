variable "project_id" {
  description = "The Google Cloud Project ID where resources will be provisioned."
  type        = string
}

variable "region" {
  description = "The Google Cloud region for services, bucket, and Firestore."
  type        = string
  default     = "asia-southeast1"
}

variable "bucket_name" {
  description = "Name for the Google Cloud Storage bucket. If empty, defaults to 'aisle-interaction-clips-<project_id>'."
  type        = string
  default     = ""
}

variable "service_account_name" {
  description = "The ID of the service account for the backend service."
  type        = string
  default     = "aisle-backend-sa"
}

variable "generate_key_file" {
  description = "Whether to automatically generate and save a service account JSON key to secrets/aisle-key.json."
  type        = bool
  default     = true
}

variable "key_output_path" {
  description = "Path where the service account JSON key will be saved."
  type        = string
  default     = "../secrets/aisle-key.json"
}

variable "clip_retention_days" {
  description = "Number of days before interaction video clips are auto-deleted from Cloud Storage (0 to disable)."
  type        = number
  default     = 7
}
