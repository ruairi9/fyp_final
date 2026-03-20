# -*- mode: ruby -*-
# vi: set ft=ruby :

# FYP 5-Server K3s Cluster - KVM/libvirt Version
# This creates 5 separate Ubuntu VMs using KVM (faster on Linux)

Vagrant.configure("2") do |config|
  # Base box for all VMs
  config.vm.box = "generic/ubuntu2204"  # Better for libvirt
  
  # Disable automatic box update checking
  config.vm.box_check_update = false

  # VM 1: Control Plane Server
  config.vm.define "control-plane" do |control|
    control.vm.hostname = "control-plane"
    control.vm.network "private_network", ip: "192.168.121.10"
    
    control.vm.provider "libvirt" do |lv|
      lv.memory = "2048"
      lv.cpus = 2
      lv.driver = "kvm"
    end
    
    control.vm.provision "shell", inline: <<-SHELL
      # Install K3s server
      curl -sfL https://get.k3s.io | INSTALL_K3S_VERSION="v1.28.5+k3s1" sh -s - server \
        --node-name control-plane \
        --disable traefik \
        --disable servicelb \
        --bind-address=0.0.0.0 \
        --advertise-address=192.168.121.10 \
        --node-taint node-role.kubernetes.io/control-plane:NoSchedule \
        --node-label="node-role=control-plane" \
        --tls-san=192.168.121.10 \
        --tls-san=control-plane
      
      # Wait for K3s to be ready
      sleep 10
      
      # Copy token for workers
      sudo cat /var/lib/rancher/k3s/server/node-token > /vagrant/k3s-token.txt
      sudo cat /etc/rancher/k3s/k3s.yaml > /vagrant/k3s.yaml
      
      # Replace localhost with actual IP in kubeconfig
      sudo sed -i 's/127.0.0.1/192.168.121.10/g' /vagrant/k3s.yaml
      
      echo "Control Plane Ready!"
      kubectl get nodes
    SHELL
  end

  # VM 2: Worker Node A - Development & Integration
  config.vm.define "worker-dev" do |worker|
    worker.vm.hostname = "worker-dev-integration"
    worker.vm.network "private_network", ip: "192.168.121.20"
    
    worker.vm.provider "libvirt" do |lv|
      lv.memory = "2048"
      lv.cpus = 2
      lv.driver = "kvm"
    end
    
    worker.vm.provision "shell", inline: <<-SHELL
      # Wait for control plane to be ready
      until [ -f /vagrant/k3s-token.txt ]; do
        echo "Waiting for control plane..."
        sleep 5
      done
      
      K3S_TOKEN=$(cat /vagrant/k3s-token.txt)
      
      # Install K3s agent
      curl -sfL https://get.k3s.io | INSTALL_K3S_VERSION="v1.28.5+k3s1" K3S_URL=https://192.168.121.10:6443 K3S_TOKEN=$K3S_TOKEN sh -s - agent \
        --node-name worker-dev-integration \
        --node-label="node-role=development" \
        --node-label="node-role=integration" \
        --node-label="environment=dev"
      
      echo "Development Worker Ready!"
    SHELL
  end

  # VM 3: Worker Node B - Production
  config.vm.define "worker-prod" do |worker|
    worker.vm.hostname = "worker-production"
    worker.vm.network "private_network", ip: "192.168.121.30"
    
    worker.vm.provider "libvirt" do |lv|
      lv.memory = "4096"
      lv.cpus = 2
      lv.driver = "kvm"
    end
    
    worker.vm.provision "shell", inline: <<-SHELL
      until [ -f /vagrant/k3s-token.txt ]; do
        echo "Waiting for control plane..."
        sleep 5
      done
      
      K3S_TOKEN=$(cat /vagrant/k3s-token.txt)
      
      curl -sfL https://get.k3s.io | INSTALL_K3S_VERSION="v1.28.5+k3s1" K3S_URL=https://192.168.121.10:6443 K3S_TOKEN=$K3S_TOKEN sh -s - agent \
        --node-name worker-production \
        --node-label="node-role=production" \
        --node-label="node-role=load-testing" \
        --node-label="node-role=security-testing" \
        --node-label="environment=prod"
      
      echo "Production Worker Ready!"
    SHELL
  end

  # VM 4: Worker Node C - CI/CD
  config.vm.define "worker-cicd" do |worker|
    worker.vm.hostname = "worker-cicd"
    worker.vm.network "private_network", ip: "192.168.121.40"
    worker.vm.network "forwarded_port", guest: 30080, host: 30080  # Jenkins
    
    worker.vm.provider "libvirt" do |lv|
      lv.memory = "3072"
      lv.cpus = 2
      lv.driver = "kvm"
    end
    
    worker.vm.provision "shell", inline: <<-SHELL
      until [ -f /vagrant/k3s-token.txt ]; do
        echo "Waiting for control plane..."
        sleep 5
      done
      
      K3S_TOKEN=$(cat /vagrant/k3s-token.txt)
      
      curl -sfL https://get.k3s.io | INSTALL_K3S_VERSION="v1.28.5+k3s1" K3S_URL=https://192.168.121.10:6443 K3S_TOKEN=$K3S_TOKEN sh -s - agent \
        --node-name worker-cicd \
        --node-label="node-role=cicd" \
        --node-label="environment=cicd"
      
      echo "CI/CD Worker Ready!"
    SHELL
  end

  # VM 5: Worker Node D - Registry & Monitoring
  config.vm.define "worker-monitoring" do |worker|
    worker.vm.hostname = "worker-registry-monitoring"
    worker.vm.network "private_network", ip: "192.168.121.50"
    worker.vm.network "forwarded_port", guest: 5000, host: 5000    # Registry
    worker.vm.network "forwarded_port", guest: 30030, host: 30030  # Grafana
    worker.vm.network "forwarded_port", guest: 30090, host: 30090  # Prometheus
    
    worker.vm.provider "libvirt" do |lv|
      lv.memory = "3072"
      lv.cpus = 2
      lv.driver = "kvm"
    end
    
    worker.vm.provision "shell", inline: <<-SHELL
      until [ -f /vagrant/k3s-token.txt ]; do
        echo "Waiting for control plane..."
        sleep 5
      done
      
      K3S_TOKEN=$(cat /vagrant/k3s-token.txt)
      
      curl -sfL https://get.k3s.io | INSTALL_K3S_VERSION="v1.28.5+k3s1" K3S_URL=https://192.168.121.10:6443 K3S_TOKEN=$K3S_TOKEN sh -s - agent \
        --node-name worker-registry-monitoring \
        --node-label="node-role=registry-monitoring" \
        --node-label="environment=monitoring"
      
      echo "Registry & Monitoring Worker Ready!"
      echo ""
      echo "========================================="
      echo "FYP 5-Server Cluster Setup Complete!"
      echo "========================================="
      echo "Control Plane: 192.168.121.10"
      echo "Worker Dev:    192.168.121.20"
      echo "Worker Prod:   192.168.121.30"
      echo "Worker CI/CD:  192.168.121.40"
      echo "Worker Monitor: 192.168.121.50"
      echo ""
      echo "Kubeconfig saved to: ./k3s.yaml"
      echo ""
      echo "To use kubectl from your host:"
      echo "export KUBECONFIG=./k3s.yaml"
      echo "kubectl get nodes"
    SHELL
  end
end
