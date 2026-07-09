provider "kubernetes" {
  config_path    = var.kubeconfig_path
  config_context = var.kube_context
}

provider "helm" {
  kubernetes = {
    config_path    = var.kubeconfig_path
    config_context = var.kube_context
  }
}

resource "kubernetes_namespace_v1" "finora" {
  metadata {
    name = var.namespace
    labels = {
      "pod-security.kubernetes.io/enforce" = "restricted"
    }
  }
}

resource "kubernetes_secret_v1" "finora" {
  metadata {
    name      = "finora-secrets"
    namespace = kubernetes_namespace_v1.finora.metadata[0].name
  }
  data = { "api-key" = var.api_key }
  type = "Opaque"
}

resource "helm_release" "finora" {
  name        = "finora-${var.deployment_color}"
  namespace   = kubernetes_namespace_v1.finora.metadata[0].name
  chart       = "${path.module}/../../helm/finora"
  atomic      = true
  wait        = true
  timeout     = 900
  max_history = 10
  values = [yamlencode({
    image      = { repository = var.image_repository, tag = var.image_tag }
    deployment = { color = var.deployment_color }
    gpu = {
      enabled      = var.enable_gpu
      count        = var.gpu_count
      nodeSelector = var.enable_gpu ? { "finora.io/accelerator" = "nvidia" } : {}
      tolerations = var.enable_gpu ? [{
        key = "nvidia.com/gpu", operator = "Exists", effect = "NoSchedule"
      }] : []
    }
    secretName     = kubernetes_secret_v1.finora.metadata[0].name
    serviceMonitor = { enabled = true }
  })]
  depends_on = [kubernetes_secret_v1.finora]
}

resource "aws_eks_node_group" "gpu" {
  count           = var.enable_gpu && var.eks_cluster_name != null ? 1 : 0
  cluster_name    = var.eks_cluster_name
  node_group_name = "finora-gpu"
  node_role_arn   = var.eks_gpu_node_role_arn
  subnet_ids      = var.eks_subnet_ids
  instance_types  = ["g5.xlarge"]
  ami_type        = "AL2_x86_64_GPU"
  scaling_config {
    desired_size = 1
    min_size     = 0
    max_size     = 5
  }
  labels = { "finora.io/accelerator" = "nvidia" }
  taint {
    key    = "nvidia.com/gpu"
    value  = "true"
    effect = "NO_SCHEDULE"
  }
  update_config { max_unavailable = 1 }
}
