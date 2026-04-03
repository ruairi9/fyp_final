terraform {
  required_providers {
    libvirt = {
      source  = "dmacvicar/libvirt"
      version = "~> 0.7"
    }
  }
}

# ── Provider ────────────────────────────────────────────────
provider "libvirt" {
  uri = "qemu:///system"
}

# ── Variables ───────────────────────────────────────────────
variable "cluster_name" {
  description = "Name of the K3s cluster"
  default     = "fyp-cluster"
}

variable "base_image" {
  description = "Base Ubuntu cloud image for all VMs"
  default     = "/var/lib/libvirt/images/ubuntu-22.04-base.qcow2"
}

variable "k3s_version" {
  description = "K3s version to install"
  default     = "v1.28.5+k3s1"
}

variable "network_cidr" {
  description = "Network CIDR for the cluster"
  default     = "192.168.121.0/24"
}

# ── Network ─────────────────────────────────────────────────
resource "libvirt_network" "cluster_network" {
  name      = "${var.cluster_name}-network"
  mode      = "nat"
  addresses = [var.network_cidr]
  autostart = true

  dns {
    enabled = true
  }
}

# ── Base disk images ─────────────────────────────────────────
resource "libvirt_volume" "control_plane_disk" {
  name           = "${var.cluster_name}-control-plane.qcow2"
  base_volume_id = libvirt_volume.base_image.id
  size           = 64424509440  # 60GB
  format         = "qcow2"
}

resource "libvirt_volume" "worker_dev_disk" {
  name           = "${var.cluster_name}-worker-dev.qcow2"
  base_volume_id = libvirt_volume.base_image.id
  size           = 64424509440
  format         = "qcow2"
}

resource "libvirt_volume" "worker_prod_disk" {
  name           = "${var.cluster_name}-worker-prod.qcow2"
  base_volume_id = libvirt_volume.base_image.id
  size           = 64424509440
  format         = "qcow2"
}

resource "libvirt_volume" "worker_cicd_disk" {
  name           = "${var.cluster_name}-worker-cicd.qcow2"
  base_volume_id = libvirt_volume.base_image.id
  size           = 64424509440
  format         = "qcow2"
}

resource "libvirt_volume" "worker_monitoring_disk" {
  name           = "${var.cluster_name}-worker-monitoring.qcow2"
  base_volume_id = libvirt_volume.base_image.id
  size           = 64424509440
  format         = "qcow2"
}

resource "libvirt_volume" "base_image" {
  name   = "ubuntu-22.04-base.qcow2"
  source = var.base_image
  format = "qcow2"
}

# ── Cloud-init configs ───────────────────────────────────────
resource "libvirt_cloudinit_disk" "control_plane_init" {
  name      = "${var.cluster_name}-control-plane-init.iso"
  user_data = <<-EOF
    #cloud-config
    hostname: control-plane
    users:
      - name: vagrant
        sudo: ALL=(ALL) NOPASSWD:ALL
        shell: /bin/bash
        ssh_authorized_keys:
          - ${file("~/.ssh/id_rsa.pub")}
    package_update: true
    packages:
      - curl
      - git
    runcmd:
      - curl -sfL https://get.k3s.io | INSTALL_K3S_VERSION=${var.k3s_version} sh -
      - systemctl enable k3s
  EOF
}

resource "libvirt_cloudinit_disk" "worker_init" {
  for_each  = toset(["worker-dev", "worker-prod", "worker-cicd", "worker-monitoring"])
  name      = "${var.cluster_name}-${each.key}-init.iso"
  user_data = <<-EOF
    #cloud-config
    hostname: ${each.key}
    users:
      - name: vagrant
        sudo: ALL=(ALL) NOPASSWD:ALL
        shell: /bin/bash
        ssh_authorized_keys:
          - ${file("~/.ssh/id_rsa.pub")}
    package_update: true
    packages:
      - curl
      - git
    runcmd:
      - curl -sfL https://get.k3s.io | INSTALL_K3S_VERSION=${var.k3s_version} K3S_URL=https://192.168.121.10:6443 K3S_TOKEN=$(cat /var/lib/rancher/k3s/server/node-token) sh -
  EOF
}

# ── Virtual Machines ─────────────────────────────────────────

# Control Plane — manages the cluster
resource "libvirt_domain" "control_plane" {
  name   = "${var.cluster_name}_control-plane"
  memory = 2048
  vcpu   = 2

  network_interface {
    network_id     = libvirt_network.cluster_network.id
    addresses      = ["192.168.121.10"]
    wait_for_lease = true
  }

  disk {
    volume_id = libvirt_volume.control_plane_disk.id
  }

  cloudinit = libvirt_cloudinit_disk.control_plane_init.id

  console {
    type        = "pty"
    target_type = "serial"
    target_port = "0"
  }

  graphics {
    type        = "vnc"
    listen_type = "address"
  }
}

# Worker Dev Integration — development workloads
resource "libvirt_domain" "worker_dev" {
  name   = "${var.cluster_name}_worker-dev"
  memory = 2048
  vcpu   = 2

  network_interface {
    network_id     = libvirt_network.cluster_network.id
    addresses      = ["192.168.121.20"]
    wait_for_lease = true
  }

  disk {
    volume_id = libvirt_volume.worker_dev_disk.id
  }

  cloudinit = libvirt_cloudinit_disk.worker_init["worker-dev"].id

  console {
    type        = "pty"
    target_type = "serial"
    target_port = "0"
  }

  graphics {
    type        = "vnc"
    listen_type = "address"
  }
}

# Worker Production — production workloads
resource "libvirt_domain" "worker_prod" {
  name   = "${var.cluster_name}_worker-prod"
  memory = 4096
  vcpu   = 2

  network_interface {
    network_id     = libvirt_network.cluster_network.id
    addresses      = ["192.168.121.30"]
    wait_for_lease = true
  }

  disk {
    volume_id = libvirt_volume.worker_prod_disk.id
  }

  cloudinit = libvirt_cloudinit_disk.worker_init["worker-prod"].id

  console {
    type        = "pty"
    target_type = "serial"
    target_port = "0"
  }

  graphics {
    type        = "vnc"
    listen_type = "address"
  }
}

# Worker CICD — Jenkins pipelines
resource "libvirt_domain" "worker_cicd" {
  name   = "${var.cluster_name}_worker-cicd"
  memory = 3072
  vcpu   = 2

  network_interface {
    network_id     = libvirt_network.cluster_network.id
    addresses      = ["192.168.121.22"]
    wait_for_lease = true
  }

  disk {
    volume_id = libvirt_volume.worker_cicd_disk.id
  }

  cloudinit = libvirt_cloudinit_disk.worker_init["worker-cicd"].id

  console {
    type        = "pty"
    target_type = "serial"
    target_port = "0"
  }

  graphics {
    type        = "vnc"
    listen_type = "address"
  }
}

# Worker Monitoring — Prometheus, Grafana, Loki, Registry
resource "libvirt_domain" "worker_monitoring" {
  name   = "${var.cluster_name}_worker-monitoring"
  memory = 3072
  vcpu   = 2

  network_interface {
    network_id     = libvirt_network.cluster_network.id
    addresses      = ["192.168.121.50"]
    wait_for_lease = true
  }

  disk {
    volume_id = libvirt_volume.worker_monitoring_disk.id
  }

  cloudinit = libvirt_cloudinit_disk.worker_init["worker-monitoring"].id

  console {
    type        = "pty"
    target_type = "serial"
    target_port = "0"
  }

  graphics {
    type        = "vnc"
    listen_type = "address"
  }
}

# ── Outputs ─────────────────────────────────────────────────
output "control_plane_ip" {
  description = "IP address of the control plane node"
  value       = "192.168.121.10"
}

output "worker_dev_ip" {
  description = "IP address of the worker-dev node"
  value       = "192.168.121.20"
}

output "worker_prod_ip" {
  description = "IP address of the worker-prod node"
  value       = "192.168.121.30"
}

output "worker_cicd_ip" {
  description = "IP address of the worker-cicd node"
  value       = "192.168.121.22"
}

output "worker_monitoring_ip" {
  description = "IP address of the worker-monitoring node"
  value       = "192.168.121.50"
}

output "cluster_summary" {
  description = "Summary of the cluster"
  value = {
    cluster_name = var.cluster_name
    nodes        = 5
    k3s_version  = var.k3s_version
    network      = var.network_cidr
  }
}
