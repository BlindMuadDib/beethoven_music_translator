#!/bin/bash
#
# # Function to ask for log check and handle input
# ask_remain_running() {
#   read -p "Do you want to keep the cluster running?? (y/n) " yn
#   case "$yn" in
#     [yY])
#       echo "OK, the cluster will remain running."
#       ;;
#     [nN])
#       echo "Deleting the cluster then exiting..."
#       sudo ~/projects/Music-Translation-for-and-by-Deaf/utils/_teardown_production_kube.sh
#       exit 0;;
#     *)
#       ask_remain_running
#       ;;
#   esac
# }
#
# # 1. Initialize the cluster with config
# sudo kubeadm init --config k8s/kubeadm-config.yaml --ignore-preflight-errors=Swap
#
# # 2. Set up the kubeconfig
# mkdir -p ~/.kube
# sudo cp -i /etc/kubernetes/admin.conf ~/.kube/config
# sudo chown $(id -u):$(id -g) ~/.kube/config
#
# # 3. (CRITICAL) Untaint the control-plane node to allow scheduling
# # This is only for single-node setups!
# kubectl taint nodes --all node-role.kubernetes.io/control-plane-
#
# # Install Cilium to the cluster
# cilium install --version 1.17.8
# # 4. Install the Gateway API Custom Resource Definitions (CRDs)
# kubectl apply -f https://github.com/kubernetes-sigs/gateway-api/releases/download/v1.1.0/standard-install.yaml

#
# # 6. Install Cilium
# # Hubble for UI
# # Operators must be 1 because single-node
# helm upgrade cilium cilium/cilium --version 1.17.8 \
#   --namespace kube-system \
#   --create-namespace \
#   --set kubeProxyReplacement=true \
#   --set ingressController.enabled=false \
#   --set gatewayAPI.enabled=true \
#   --set gatewayAPI.hostNetwork.enabled=true \
#   --set hubble.relay.enabled=true \
#   --set hubble.ui.enabled=true \
#   --set operator.replicas=1

# 6. Apply Kubernetes YAML files
kubectl apply -f k8s/persistent-volumes.yaml
kubectl apply -f k8s/persistent-volumes-claims.yaml
kubectl apply -f k8s/tls-secret.yaml
kubectl apply -f k8s/auth-deployment.yaml
kubectl apply -f k8s/worker-deployment.yaml
kubectl apply -f k8s/redis-deployment.yaml
kubectl apply -f k8s/main-deployment.yaml
kubectl apply -f k8s/demucs-deployment.yaml
kubectl apply -f k8s/mfa-deployment.yaml
kubectl apply -f k8s/harmonic-deployment.yaml
kubectl apply -f k8s/beethoven-deployment.yaml
kubectl apply -f k8s/drums-deployment.yaml
kubectl apply -f k8s/auth-service.yaml
kubectl apply -f k8s/redis-service.yaml
kubectl apply -f k8s/main-service.yaml
kubectl apply -f k8s/demucs-service.yaml
kubectl apply -f k8s/mfa-service.yaml
kubectl apply -f k8s/harmonic-service.yaml
kubectl apply -f k8s/beethoven-service.yaml
kubectl apply -f k8s/drums-service.yaml
kubectl apply -f k8s/ingress.yaml
kubectl apply -f k8s/ingress-auth.yaml
kubectl apply -f k8s/auth-rewrite.yaml

# # Wait for pods to become ready (add logic as needed)
# echo "Waiting for deployments to be ready ..."
# kubectl wait --for=condition=available deployment/auth-server-deployment --timeout=300s
# kubectl wait --for=condition=available deployment/translator-deployment --timeout=300s
# kubectl wait --for=condition=available deployment/translator-worker --timeout=300s
# kubectl wait --for=condition=available deployment/mfa-deployment --timeout=300s
# kubectl wait --for=condition=available deployment/demucs-deployment --timeout=300s
# kubectl wait --for=condition=available deployment/harmonic-deployment --timeout=300s
# kubectl wait --for=condition=available deployment/redis --timeout=300s
# kubectl wait --for=condition=available deployment/beethoven-deployment --timeout=300s
# kubectl wait --for=condition=available deployment/drums-deployment --timeout=300s
#
# echo "Waiting for Ingress controller to assign an address to the Ingress rules..."
# kubectl wait --namespace default \
#   --for=jsonpath='{.status.loadBalancer.ingress}' \
#   ingress/musictranslator-ingress \
#   --timeout=120s
#
# kubectl wait --namespace default \
#   --for=jsonpath='{.status.loadBalancer.ingress}' \
#   ingress/musictranslator-auth-ingress \
#   --timeout=120s
#
# echo "Deployments and Ingress ready. Running tests ..."
#
# # 8. Run integration tests
# pytest -v tests/test_integration.py
#
# # Ask if logs are requested
# ask_remain_running

