output "eks_cluster_endpoint" {
  description = "EKS cluster API server endpoint"
  value       = module.eks.cluster_endpoint
}

output "rds_endpoint" {
  description = "RDS PostgreSQL endpoint"
  value       = aws_db_instance.main.endpoint
}

output "s3_bucket_name" {
  description = "S3 data bucket name"
  value       = aws_s3_bucket.data.bucket
}
