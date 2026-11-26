variable "aws_region" {
  description = "Region for the lab stack."
  type        = string
  default     = "ap-southeast-1"
}

variable "mysql_engine_version" {
  description = "MySQL 8.4 minor version. 8.0 is in RDS Extended Support and costs more."
  type        = string
  default     = "8.4.13"
}

variable "db_name" {
  description = "Database name created on the instance."
  type        = string
  default     = "lab"
}

variable "db_username" {
  description = "Master username. Do not use a reserved name such as admin or rdsadmin."
  type        = string
  default     = "labadmin"
}

variable "db_password" {
  description = "Master password. Set TF_VAR_db_password at apply time. Do not commit this value."
  type        = string
  sensitive   = true

  validation {
    condition     = length(var.db_password) >= 12
    error_message = "db_password must be at least 12 characters."
  }
}
