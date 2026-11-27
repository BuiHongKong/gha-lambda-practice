resource "aws_apigatewayv2_api" "images" {
  name          = local.name
  protocol_type = "HTTP"
}

resource "aws_apigatewayv2_integration" "images" {
  api_id                 = aws_apigatewayv2_api.images.id
  integration_type       = "AWS_PROXY"
  integration_uri        = aws_lambda_function.images.invoke_arn
  integration_method     = "POST"
  payload_format_version = "1.0"
}

locals {
  image_routes = {
    create = {
      route_key  = "POST /images"
      source_arn = "/*/POST/images"
    }
    complete = {
      route_key  = "POST /images/{id}/complete"
      source_arn = "/*/POST/images/*/complete"
    }
    list = {
      route_key  = "GET /images"
      source_arn = "/*/GET/images"
    }
    get = {
      route_key  = "GET /images/{id}"
      source_arn = "/*/GET/images/*"
    }
    rename = {
      route_key  = "PATCH /images/{id}"
      source_arn = "/*/PATCH/images/*"
    }
    delete = {
      route_key  = "DELETE /images/{id}"
      source_arn = "/*/DELETE/images/*"
    }
  }
}

resource "aws_apigatewayv2_route" "images" {
  for_each = local.image_routes

  api_id             = aws_apigatewayv2_api.images.id
  route_key          = each.value.route_key
  authorization_type = "AWS_IAM"
  target             = "integrations/${aws_apigatewayv2_integration.images.id}"
}

resource "aws_apigatewayv2_stage" "default" {
  api_id      = aws_apigatewayv2_api.images.id
  name        = "$default"
  auto_deploy = true
}

resource "aws_lambda_permission" "images" {
  for_each = local.image_routes

  statement_id  = "Allow${replace(each.key, "_", "")}"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.images.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.images.execution_arn}${each.value.source_arn}"
}
