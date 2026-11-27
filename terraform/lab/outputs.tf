output "images_url" {
  description = "IAM-signed image API. POST /images returns a presigned S3 upload URL."
  value       = "${aws_apigatewayv2_api.images.api_endpoint}/images"
}

output "function_name" {
  value = aws_lambda_function.images.function_name
}

output "rds_address" {
  value = aws_db_instance.lab.address
}

output "image_bucket" {
  value = aws_s3_bucket.images.bucket
}

output "vpc_id" {
  value = aws_vpc.lab.id
}
