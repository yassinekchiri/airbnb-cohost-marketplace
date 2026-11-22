variable "proxmox_endpoint" {
  description = "Proxmox VE API URL"
  type        = string
}

variable "node_name" {
  description = "Proxmox node that hosts the lab"
  type        = string
}

variable "template_vm_id" {
  description = "Cloud-init template to clone (read only, never modified)"
  type        = number
}

variable "vm_datastore" {
  description = "Storage for VM disks and the cloud-init drive"
  type        = string
}

variable "snippets_datastore" {
  description = "Proxmox storage (NFS, content 'snippets' enabled) that holds cloud-init user-data"
  type        = string
}

variable "snippets_dir" {
  description = "Path of that storage's snippets/ directory as seen by Terraform (inside the tf.sh container)"
  type        = string
  default     = "/nas/snippets"
}

variable "bridge" {
  type = string
}

variable "gateway" {
  type = string
}

variable "dns_servers" {
  type = list(string)
}

variable "protected_vm_ids" {
  description = "VM ids Terraform must never manage: existing guests, the hand-made control VM and the template"
  type        = list(number)
}

variable "lab" {
  description = "The disposable lab VM"
  type = object({
    vm_id     = number
    name      = string
    ipv4_cidr = string # e.g. 192.168.1.210/24
    cores     = number
    memory_mb = number
    disk_gb   = number
  })

  validation {
    condition     = can(cidrhost(var.lab.ipv4_cidr, 0))
    error_message = "lab.ipv4_cidr must look like 192.168.1.210/24."
  }
}

variable "lab_ip_range" {
  description = "Last octet range of 192.168.1.x reserved for Terraform guests (201-220; .200 is the control VM)"
  type = object({
    prefix = string
    first  = number
    last   = number
  })
}

variable "admin_user" {
  description = "Login user created by cloud-init (sudo, docker group)"
  type        = string
  default     = "cohost"
}

variable "ssh_authorized_keys" {
  description = "Public SSH keys for admin_user, one per line (GitHub variable NUC_LAB_SSH_AUTHORIZED_KEYS). Empty = console only."
  type        = string
  default     = ""
}

variable "tailscale_auth_key" {
  description = "Optional Tailscale auth key (GitHub secret NUC_LAB_TAILSCALE_AUTHKEY). Empty = Tailscale installed but not joined."
  type        = string
  default     = ""
  sensitive   = true
}
