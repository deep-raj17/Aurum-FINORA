variable "kubeconfig_path" {
  type      = string
  sensitive = true
}

variable "kube_context" {
  type    = string
  default = null
}

variable "namespace" {
  type    = string
  default = "finora"
}

variable "image_repository" {
  type = string
}

variable "image_tag" {
  type = string
}

variable "api_key" {
  type      = string
  sensitive = true
}

variable "deployment_color" {
  type    = string
  default = "blue"
  validation {
    condition     = contains(["blue", "green"], var.deployment_color)
    error_message = "deployment_color must be blue or green"
  }
}

variable "enable_gpu" {
  type    = bool
  default = false
}

variable "gpu_count" {
  type    = number
  default = 1
}

variable "eks_cluster_name" {
  type    = string
  default = null
}

variable "eks_gpu_node_role_arn" {
  type    = string
  default = null
}

variable "eks_subnet_ids" {
  type    = list(string)
  default = []
}
