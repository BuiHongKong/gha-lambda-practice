data "aws_caller_identity" "current" {}

data "archive_file" "hello" {
  type        = "zip"
  source_file = "${path.module}/../../lambda/hello/handler.py"
  output_path = "${path.module}/build/hello.zip"
}

resource "aws_cloudwatch_log_group" "hello" {
  name              = "/aws/lambda/${local.name}-hello"
  retention_in_days = 14
}

data "aws_iam_policy_document" "lambda_assume" {
  statement {
    effect = "Allow"

    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }

    actions = ["sts:AssumeRole"]
  }
}

resource "aws_iam_role" "lambda" {
  name               = "${local.name}-hello"
  assume_role_policy = data.aws_iam_policy_document.lambda_assume.json
}

data "aws_iam_policy_document" "lambda" {
  statement {
    sid    = "WriteFunctionLogs"
    effect = "Allow"

    actions = [
      "logs:CreateLogStream",
      "logs:PutLogEvents",
    ]

    resources = ["${aws_cloudwatch_log_group.hello.arn}:*"]
  }

  # CreateNetworkInterface does not support resource-level permissions.
  statement {
    sid    = "ManageVpcNetworkInterfaces"
    effect = "Allow"

    actions = [
      "ec2:CreateNetworkInterface",
      "ec2:DescribeNetworkInterfaces",
      "ec2:DeleteNetworkInterface",
      "ec2:AssignPrivateIpAddresses",
      "ec2:UnassignPrivateIpAddresses",
    ]

    resources = ["*"]
  }

  statement {
    sid       = "ListImages"
    effect    = "Allow"
    actions   = ["s3:ListBucket"]
    resources = [aws_s3_bucket.images.arn]
  }

  statement {
    sid       = "ReadImages"
    effect    = "Allow"
    actions   = ["s3:GetObject"]
    resources = ["${aws_s3_bucket.images.arn}/*"]
  }
}

resource "aws_iam_role_policy" "lambda" {
  name   = "${local.name}-hello"
  role   = aws_iam_role.lambda.id
  policy = data.aws_iam_policy_document.lambda.json
}

resource "aws_lambda_function" "hello" {
  function_name = "${local.name}-hello"
  role          = aws_iam_role.lambda.arn
  runtime       = "python3.12"
  handler       = "handler.handler"
  timeout       = 10
  memory_size   = 128

  filename         = data.archive_file.hello.output_path
  source_code_hash = data.archive_file.hello.output_base64sha256

  vpc_config {
    subnet_ids         = [aws_subnet.private[0].id]
    security_group_ids = [aws_security_group.lambda.id]
  }

  environment {
    variables = {
      DB_HOST      = aws_db_instance.lab.address
      DB_PORT      = tostring(aws_db_instance.lab.port)
      DB_NAME      = var.db_name
      DB_USER      = var.db_username
      DB_PASSWORD  = var.db_password
      IMAGE_BUCKET = aws_s3_bucket.images.bucket
    }
  }

  depends_on = [aws_cloudwatch_log_group.hello]
}
