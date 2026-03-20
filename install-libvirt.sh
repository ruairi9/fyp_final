#!/bin/bash

# Install libvirt and vagrant-libvirt plugin for FYP cluster

set -e

echo "========================================"
echo "Installing KVM/libvirt for FYP Cluster"
echo "========================================"
echo ""

# Install libvirt and dependencies
echo "Step 1: Installing libvirt and KVM..."
sudo apt update
sudo apt install -y \
    qemu-kvm \
    libvirt-daemon-system \
    libvirt-clients \
    bridge-utils \
    virtinst \
    virt-manager \
    libvirt-dev \
    ruby-dev \
    gcc \
    make

# Add user to libvirt groups
echo "Step 2: Adding user to libvirt groups..."
sudo usermod -aG libvirt $USER
sudo usermod -aG kvm $USER

# Start and enable libvirt
echo "Step 3: Starting libvirt service..."
sudo systemctl start libvirtd
sudo systemctl enable libvirtd

# Install vagrant-libvirt plugin
echo "Step 4: Installing vagrant-libvirt plugin..."
vagrant plugin install vagrant-libvirt

# Verify installation
echo ""
echo "========================================"
echo "Verifying Installation..."
echo "========================================"

# Check KVM
if [ -e /dev/kvm ]; then
    echo "✓ KVM is available"
else
    echo "✗ KVM is not available"
fi

# Check libvirt
if systemctl is-active --quiet libvirtd; then
    echo "✓ libvirtd is running"
else
    echo "✗ libvirtd is not running"
fi

# Check vagrant plugin
if vagrant plugin list | grep -q vagrant-libvirt; then
    echo "✓ vagrant-libvirt plugin is installed"
else
    echo "✗ vagrant-libvirt plugin is not installed"
fi

echo ""
echo "========================================"
echo "Installation Complete!"
echo "========================================"
echo ""
echo "IMPORTANT: You need to log out and log back in"
echo "for the group membership changes to take effect."
echo ""
echo "After logging back in:"
echo "1. cd ~/fyp-cluster"
echo "2. cp Vagrantfile-libvirt Vagrantfile"
echo "3. vagrant up"
echo ""
