terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.0"
    }
  }
}

provider "aws" {
  region = "eu-central-1" # Frankfurt is usually good for Bulgaria
}

resource "random_id" "bucket_suffix" {
  byte_length = 4
}

resource "aws_s3_bucket" "spesti_data" {
  bucket = "spesti-grocery-data-${random_id.bucket_suffix.hex}"
  
  tags = {
    Name        = "Spesti Grocery Data"
    Environment = "Production"
  }
}

# Allow public access settings
resource "aws_s3_bucket_public_access_block" "public_access" {
  bucket = aws_s3_bucket.spesti_data.id

  block_public_acls       = false
  block_public_policy     = false
  ignore_public_acls      = false
  restrict_public_buckets = false
}

# Attach public read policy so the frontend can retrieve the products.json
resource "aws_s3_bucket_policy" "public_read" {
  bucket = aws_s3_bucket.spesti_data.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid       = "PublicReadGetObject"
        Effect    = "Allow"
        Principal = "*"
        Action    = [
          "s3:GetObject"
        ]
        Resource  = "${aws_s3_bucket.spesti_data.arn}/*"
      },
    ]
  })

  depends_on = [aws_s3_bucket_public_access_block.public_access]
}

# Configure CORS so the frontend web app can fetch the JSON data without errors
resource "aws_s3_bucket_cors_configuration" "cors" {
  bucket = aws_s3_bucket.spesti_data.id

  cors_rule {
    allowed_headers = ["*"]
    allowed_methods = ["GET", "HEAD"]
    allowed_origins = ["*"] # Update this to limit to specific frontend domains if necessary
    expose_headers  = ["ETag"]
    max_age_seconds = 3000
  }
}

# Output the URL to the bucket
output "bucket_name" {
  description = "The name of the bucket"
  value       = aws_s3_bucket.spesti_data.id
}

output "bucket_domain_name" {
  description = "Domain name of the bucket"
  value       = aws_s3_bucket.spesti_data.bucket_regional_domain_name
}

output "products_json_url" {
  description = "Direct URL to the products JSON data (once uploaded)"
  value       = "https://${aws_s3_bucket.spesti_data.bucket_regional_domain_name}/products.json"
}

# --- Lambda IAM Role ---
resource "aws_iam_role" "lambda_exec_role" {
  name = "spesti_lambda_exec_role_${random_id.bucket_suffix.hex}"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action    = "sts:AssumeRole"
        Principal = {
          Service = "lambda.amazonaws.com"
        }
        Effect    = "Allow"
      }
    ]
  })
}

# Allow Lambda to write to the S3 bucket
resource "aws_iam_policy" "lambda_s3_policy" {
  name        = "spesti_lambda_s3_policy_${random_id.bucket_suffix.hex}"
  description = "Allows Lambda to upload products.json to the Spesti bucket"
  policy      = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = [
          "s3:PutObject",
          "s3:PutObjectAcl"
        ]
        Resource = "${aws_s3_bucket.spesti_data.arn}/*"
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "lambda_s3_attach" {
  role       = aws_iam_role.lambda_exec_role.name
  policy_arn = aws_iam_policy.lambda_s3_policy.arn
}

# Attach basic execution role so Lambda can write CloudWatch logs
resource "aws_iam_role_policy_attachment" "lambda_basic_execution" {
  role       = aws_iam_role.lambda_exec_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

# --- Lambda Function ---
resource "aws_lambda_function" "spesti_daily_job" {
  function_name = "spesti-data-pipeline-${random_id.bucket_suffix.hex}"
  role          = aws_iam_role.lambda_exec_role.arn
  handler       = "lambda_function.lambda_handler"
  runtime       = "python3.10"
  timeout       = 300
  memory_size   = 512

  # The zip file containing our python script
  filename         = "lambda_deployment.zip"
  source_code_hash = filebase64sha256("lambda_deployment.zip")
  
  environment {
    variables = {
      BUCKET_NAME = aws_s3_bucket.spesti_data.id
    }
  }
}

# --- EventBridge (CloudWatch Events) Rule ---
resource "aws_cloudwatch_event_rule" "daily_trigger" {
  name                = "spesti-daily-update-${random_id.bucket_suffix.hex}"
  description         = "Triggers the Spesti Lambda function daily at 1:00 AM UTC"
  schedule_expression = "cron(0 1 * * ? *)"
}

resource "aws_cloudwatch_event_target" "trigger_lambda" {
  rule      = aws_cloudwatch_event_rule.daily_trigger.name
  target_id = "SpestiPipelineLambda"
  arn       = aws_lambda_function.spesti_daily_job.arn
}

resource "aws_lambda_permission" "allow_eventbridge" {
  statement_id  = "AllowExecutionFromEventBridge"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.spesti_daily_job.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.daily_trigger.arn
}
