terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
  required_version = ">= 1.5.0"
}

provider "aws" {
  region = var.aws_region
}

# EKS Cluster
module "eks" {
  source          = "terraform-aws-modules/eks/aws"
  version         = "~> 19.0"
  cluster_name    = "agi-system-${var.environment}"
  cluster_version = "1.28"
  vpc_id          = aws_vpc.main.id
  subnet_ids      = aws_subnet.private[*].id

  eks_managed_node_groups = {
    default = {
      min_size     = 2
      max_size     = 10
      desired_size = 3
      instance_types = ["t3.medium"]
    }
  }
}

# RDS PostgreSQL
resource "aws_db_instance" "main" {
  identifier        = "agi-system-${var.environment}"
  engine            = "postgres"
  engine_version    = "15"
  instance_class    = "db.t3.medium"
  allocated_storage = 100
  db_name           = "agi_system"
  username          = var.db_username
  password          = var.db_password
  skip_final_snapshot = var.environment != "production"
  multi_az          = var.environment == "production"

  tags = {
    Environment = var.environment
    Project     = "agi-system"
  }
}

# S3 Bucket
resource "aws_s3_bucket" "data" {
  bucket = "agi-system-${var.environment}-data"

  tags = {
    Environment = var.environment
    Project     = "agi-system"
  }
}

resource "aws_s3_bucket_versioning" "data" {
  bucket = aws_s3_bucket.data.id
  versioning_configuration {
    status = "Enabled"
  }
}

# VPC
resource "aws_vpc" "main" {
  cidr_block           = "10.0.0.0/16"
  enable_dns_hostnames = true
  enable_dns_support   = true

  tags = {
    Name        = "agi-system-${var.environment}"
    Environment = var.environment
  }
}

# Private subnets
resource "aws_subnet" "private" {
  count             = 2
  vpc_id            = aws_vpc.main.id
  cidr_block        = "10.0.${count.index + 1}.0/24"
  availability_zone = data.aws_availability_zones.available.names[count.index]

  tags = {
    Name = "agi-system-private-${count.index + 1}"
  }
}

data "aws_availability_zones" "available" {
  state = "available"
}
