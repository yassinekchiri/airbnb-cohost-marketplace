terraform {
  required_version = ">= 1.9.0"

  required_providers {
    proxmox = {
      source  = "bpg/proxmox"
      version = ">= 0.78.0, < 1.0.0"
    }
    local = {
      source  = "hashicorp/local"
      version = "~> 2.5"
    }
  }

  # State lives on the NAS, never in Git. The path is passed at init time by tf.sh:
  #   -backend-config=path=/nas/terraform/nuc-lab/terraform.tfstate
  # (the control VM mounts 192.168.1.15:/volume1/CoHostBackup at /mnt/cohost-nas; tf.sh binds
  # its terraform/nuc-lab sub-directory into the Terraform container).
  backend "local" {}
}

provider "proxmox" {
  endpoint = var.proxmox_endpoint
  # The node uses Proxmox's self-signed certificate. Traffic stays on the LAN (192.168.1.0/24).
  # To verify it instead: commit /etc/pve/pve-root-ca.pem and set SSL_CERT_FILE in tf.sh.
  insecure = true
  # Credentials: PROXMOX_VE_API_TOKEN (format "terraform@pve!provider=<uuid>"), from the
  # GitHub secret of the same name. Never put it in a .tf or .tfvars file.
}
