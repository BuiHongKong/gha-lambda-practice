output "hello_url" {
  description = "IAM-signed GET /hello URL."
  value       = "${aws_apigatewayv2_api.hello.api_endpoint}/hello"
}

output "function_name" {
  value = aws_lambda_function.hello.function_name
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
