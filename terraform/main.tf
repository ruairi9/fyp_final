terraform {
  required_providers {
    libvirt = {
      source  = "dmacvicar/libvirt"
      version = "~> 0.9"
    }
  }
}

provider "libvirt" {
  uri = "qemu:///system"
}

variable "cluster_name" {
  description = "Name of the K3s cluster"
  default     = "fyp-cluster"
}

variable "k3s_version" {
  description = "K3s version to install"
  default     = "v1.28.5+k3s1"
}

variable "network_cidr" {
  description = "Network CIDR for the cluster"
  default     = "192.168.121.0/24"
}

resource "libvirt_network" "cluster_network" {
  name      = "${var.cluster_name}-network"
  autostart = true
}

resource "libvirt_volume" "base_image" {
  name = "ubuntu-22.04-base.qcow2"
  pool = "default"
}

resource "libvirt_volume" "control_plane_disk" {
  name = "${var.cluster_name}-control-plane.qcow2"
  pool = "default"
}

resource "libvirt_volume" "worker_dev_disk" {
  name = "${var.cluster_name}-worker-dev.qcow2"
  pool = "default"
}

resource "libvirt_volume" "worker_prod_disk" {
  name = "${var.cluster_name}-worker-prod.qcow2"
  pool = "default"
}

resource "libvirt_volume" "worker_cicd_disk" {
  name = "${var.cluster_name}-worker-cicd.qcow2"
  pool = "default"
}

resource "libvirt_volume" "worker_monitoring_disk" {
  name = "${var.cluster_name}-worker-monitoring.qcow2"
  pool = "default"
}

resource "libvirt_cloudinit_disk" "control_plane_init" {
  name      = "${var.cluster_name}-control-plane-init.iso"
  meta_data = jsonencode({ "instance-id" = "control-plane" })
  user_data = <<-EOF
    #cloud-config
    hostname: control-plane
    users:
      - name: vagrant
        sudo: ALL=(ALL) NOPASSWD:ALL
        shell: /bin/bash
    runcmd:
      - curl -sfL https://get.k3s.io | INSTALL_K3S_VERSION=${var.k3s_version} sh -
  EOF
}

resource "libvirt_cloudinit_disk" "worker_dev_init" {
  name      = "${var.cluster_name}-worker-dev-init.iso"
  meta_data = jsonencode({ "instance-id" = "worker-dev" })
  user_data = <<-EOF
    #cloud-config
    hostname: worker-dev-integration
    users:
      - name: vagrant
        sudo: ALL=(ALL) NOPASSWD:ALL
        shell: /bin/bash
    runcmd:
      - curl -sfL https://get.k3s.io | K3S_URL=https://192.168.121.10:6443 K3S_TOKEN=placeholder sh -
  EOF
}

resource "libvirt_cloudinit_disk" "worker_prod_init" {
  name      = "${var.cluster_name}-worker-prod-init.iso"
  meta_data = jsonencode({ "instance-id" = "worker-prod" })
  user_data = <<-EOF
    #cloud-config
    hostname: worker-production
    users:
      - name: vagrant
        sudo: ALL=(ALL) NOPASSWD:ALL
        shell: /bin/bash
    runcmd:
      - curl -sfL https://get.k3s.io | K3S_URL=https://192.168.121.10:6443 K3S_TOKEN=placeholder sh -
  EOF
}

resource "libvirt_cloudinit_disk" "worker_cicd_init" {
  name      = "${var.cluster_name}-worker-cicd-init.iso"
  meta_data = jsonencode({ "instance-id" = "worker-cicd" })
  user_data = <<-EOF
    #cloud-config
    hostname: worker-cicd
    users:
      - name: vagrant
        sudo: ALL=(ALL) NOPASSWD:ALL
        shell: /bin/bash
    runcmd:
      - curl -sfL https://get.k3s.io | K3S_URL=https://192.168.121.10:6443 K3S_TOKEN=placeholder sh -
  EOF
}

resource "libvirt_cloudinit_disk" "worker_monitoring_init" {
  name      = "${var.cluster_name}-worker-monitoring-init.iso"
  meta_data = jsonencode({ "instance-id" = "worker-monitoring" })
  user_data = <<-EOF
    #cloud-config
    hostname: worker-registry-monitoring
    users:
      - name: vagrant
        sudo: ALL=(ALL) NOPASSWD:ALL
        shell: /bin/bash
    runcmd:
      - curl -sfL https://get.k3s.io | K3S_URL=https://192.168.121.10:6443 K3S_TOKEN=placeholder sh -
  EOF
}

resource "libvirt_domain" "control_plane" {
  name   = "${var.cluster_name}_control-plane"
  memory = 2048
  vcpu   = 2
  type   = "kvm"
}

resource "libvirt_domain" "worker_dev" {
  name   = "${var.cluster_name}_worker-dev"
  memory = 2048
  vcpu   = 2
  type   = "kvm"
}

resource "libvirt_domain" "worker_prod" {
  name   = "${var.cluster_name}_worker-prod"
  memory = 4096
  vcpu   = 2
  type   = "kvm"
}

resource "libvirt_domain" "worker_cicd" {
  name   = "${var.cluster_name}_worker-cicd"
  memory = 3072
  vcpu   = 2
  type   = "kvm"
}

resource "libvirt_domain" "worker_monitoring" {
  name   = "${var.cluster_name}_worker-monitoring"
  memory = 3072
  vcpu   = 2
  type   = "kvm"
}

output "cluster_summary" {
  description = "Summary of the fyp-cluster"
  value = {
    cluster_name  = var.cluster_name
    nodes         = 5
    k3s_version   = var.k3s_version
    network       = var.network_cidr
    control_plane = "192.168.121.10"
    worker_dev    = "192.168.121.20"
    worker_prod   = "192.168.121.30"
    worker_cicd   = "192.168.121.22"
    worker_mon    = "192.168.121.50"
  }
}
