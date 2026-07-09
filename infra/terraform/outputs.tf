output "namespace" { value = kubernetes_namespace_v1.finora.metadata[0].name }
output "release_name" { value = helm_release.finora.name }
output "deployment_color" { value = var.deployment_color }
