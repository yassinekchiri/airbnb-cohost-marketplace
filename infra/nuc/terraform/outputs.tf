output "lab_vm_id" {
  value = proxmox_virtual_environment_vm.lab.vm_id
}

output "lab_ip" {
  value = local.lab_ip
}

output "lab_ssh" {
  value = "ssh ${var.admin_user}@${local.lab_ip}"
}

output "lab_user_data_snippet" {
  value = "${var.snippets_datastore}:snippets/${local.snippet_name}"
}
