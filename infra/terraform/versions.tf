terraform {
  required_version = ">= 1.7.0"
  required_providers {
    kubernetes = { source = "hashicorp/kubernetes", version = "~> 2.0" }
    helm       = { source = "hashicorp/helm", version = "~> 3.0" }
    aws        = { source = "hashicorp/aws", version = "~> 6.0" }
  }
}
