# NUC lab on Proxmox VE: one disposable VM ("lab", id 210) cloned from template 9000.
#
# Not managed here, on purpose: VMs 100, 101, 102, the template 9000 (only read by the clone) and the
# hand-made "control" VM 200 that runs the GitHub runner and this Terraform. A runner must not live
# in a VM it can destroy (docs/DECISIONS.md). `terraform destroy` removes only what is below.

locals {
  ssh_keys = compact([for k in split("\n", var.ssh_authorized_keys) : trimspace(k)])

  lab_ip        = split("/", var.lab.ipv4_cidr)[0]
  lab_ip_octets = split(".", local.lab_ip)

  user_data = templatefile("${path.module}/cloud-init/lab.yaml.tftpl", {
    hostname           = var.lab.name
    admin_user         = var.admin_user
    ssh_keys           = local.ssh_keys
    tailscale_auth_key = var.tailscale_auth_key
    tailscale_hostname = "cohost-${var.lab.name}"
  })

  # The content hash is in the file name: editing cloud-init gives a new snippet, which replaces the
  # VM (cloud-init only runs on first boot). The hash of the whole file is not a secret.
  user_data_hash = substr(nonsensitive(sha256(local.user_data)), 0, 12)
  snippet_name   = "cohost-${var.lab.name}-${local.user_data_hash}.yaml"
}

# Cloud-init user-data, written straight onto the NAS share that Proxmox mounts as storage "nas".
# This avoids the bpg provider's SSH-to-the-node upload (the API cannot upload snippets), so the
# only credential Terraform needs is the API token.
resource "local_file" "lab_user_data" {
  filename             = "${var.snippets_dir}/${local.snippet_name}"
  content              = local.user_data
  file_permission      = "0644"
  directory_permission = "0755"
}

resource "proxmox_virtual_environment_vm" "lab" {
  node_name   = var.node_name
  vm_id       = var.lab.vm_id
  name        = var.lab.name
  description = "CoHost NUC lab. Managed by Terraform (infra/nuc/terraform): manual changes are overwritten, the VM is disposable."
  tags        = ["cohost", "lab", "terraform"]

  on_boot         = true
  started         = true
  stop_on_destroy = true # do not wait for a clean guest shutdown on destroy

  clone {
    vm_id        = var.template_vm_id
    node_name    = var.node_name
    datastore_id = var.vm_datastore
    full         = true
    retries      = 3
  }

  # Disabled on purpose: with the agent on, the provider waits for the guest to report its IPs,
  # which needs VM.GuestAgent.Audit (PVE 9) / VM.Monitor (PVE 8), not in the TerraformProv role.
  # The IP is static, so nothing needs it. qemu-guest-agent is still installed inside the guest.
  agent {
    enabled = false
  }

  operating_system {
    type = "l26"
  }

  cpu {
    cores = var.lab.cores
    type  = "x86-64-v2-AES"
  }

  memory {
    dedicated = var.lab.memory_mb
  }

  scsi_hardware = "virtio-scsi-pci"

  disk {
    datastore_id = var.vm_datastore
    interface    = "scsi0"
    size         = var.lab.disk_gb
    discard      = "on"
    ssd          = true
  }

  network_device {
    bridge = var.bridge
    model  = "virtio"
  }

  serial_device {
    device = "socket"
  }

  vga {
    type = "serial0"
  }

  initialization {
    datastore_id = var.vm_datastore

    dns {
      servers = var.dns_servers
    }

    ip_config {
      ipv4 {
        address = var.lab.ipv4_cidr
        gateway = var.gateway
      }
    }

    user_data_file_id = "${var.snippets_datastore}:snippets/${basename(local_file.lab_user_data.filename)}"
  }

  lifecycle {
    replace_triggered_by = [local_file.lab_user_data]

    precondition {
      condition     = !contains(var.protected_vm_ids, var.lab.vm_id)
      error_message = "lab.vm_id ${var.lab.vm_id} is protected (${join(", ", var.protected_vm_ids)}). Pick another id."
    }
    precondition {
      condition     = var.lab.vm_id != var.template_vm_id
      error_message = "lab.vm_id must not be the template id."
    }
    precondition {
      condition = (
        startswith(local.lab_ip, var.lab_ip_range.prefix) &&
        tonumber(local.lab_ip_octets[3]) >= var.lab_ip_range.first &&
        tonumber(local.lab_ip_octets[3]) <= var.lab_ip_range.last
      )
      error_message = "lab IP ${local.lab_ip} is outside ${var.lab_ip_range.prefix}${var.lab_ip_range.first}-${var.lab_ip_range.last} (.200 is the control VM)."
    }
  }
}
