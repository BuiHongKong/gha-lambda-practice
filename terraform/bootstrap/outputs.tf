output "state_bucket" {
  description = "Pass this to terraform init -backend-config in terraform/lab."
  value       = aws_s3_bucket.state.bucket
}

output "aws_region" {
  value = var.aws_region
}
