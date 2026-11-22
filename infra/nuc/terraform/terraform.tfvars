# Non-secret facts about the home lab. Secrets come from GitHub (see README.md), never from this file.
proxmox_endpoint   = "https://192.168.1.101:8006/"
node_name          = "myproxmox"
template_vm_id     = 9000 # ubuntu-2404-cloud
vm_datastore       = "lab-thin"
snippets_datastore = "nas" # NFS v3, 192.168.1.15:/volume1/CoHostBackup
bridge             = "vmbr0"
gateway            = "192.168.1.254"
dns_servers        = ["192.168.1.254", "1.1.1.1"]

# Never managed by this configuration. 200 = "control" (hand-made, runs the GitHub runner).
protected_vm_ids = [100, 101, 102, 200, 9000]

lab_ip_range = {
  prefix = "192.168.1."
  first  = 201
  last   = 220
}

lab = {
  vm_id     = 210
  name      = "lab"
  ipv4_cidr = "192.168.1.210/24"
  cores     = 2
  memory_mb = 4096
  disk_gb   = 40
}
