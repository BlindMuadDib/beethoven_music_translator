#!/bin/bash
# # Remove Cilium for a clean slate install next run
# helm uninstall cilium -n kube-system

# Reset the cluster
sudo kubeadm reset -f

# Clean up all old configs
sudo rm -rf /etc/kubernetes/
sudo rm -rf /var/lib/kubelet/
sudo rm -rf /var/lib/etcd/
sudo rm -rf ~/.kube/
sudo rm -rf /etc/cni/net.d

# Restart the container runtime
sudo systemctl restart containerd

# Restart the iptables
sudo iptables -F
sudo iptables -X
sudo iptables -Z
sudo iptables -P INPUT ACCEPT
sudo iptables -P FORWARD ACCEPT
sudo iptables -P OUTPUT ACCEPT
