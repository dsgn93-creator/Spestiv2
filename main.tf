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
