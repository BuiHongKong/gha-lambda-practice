terraform {
  required_version = ">= 1.10.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.70"
    }
  }

  # Bucket name comes from bootstrap output:
  # terraform init -backend-config="bucket=<state_bucket>"
  backend "s3" {
    key          = "lab/terraform.tfstate"
    region       = "ap-southeast-1"
    encrypt      = true
    use_lockfile = true
  }
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project = "gha-lambda-practice"
    }
  }
}
