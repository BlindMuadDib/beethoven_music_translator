#!/bin/bash

# Start KIND cluster
kind create cluster --config config.yaml

# Build Docker images
# podman build -f musictranslator.Dockerfile -t music-translator:latest --format docker
# podman build -f align-endpoint.Dockerfile -t mfa-wrapper:latest --format docker
# podman build -f separate-endpoint.Dockerfile -t demucs-wrapper:latest --format docker

# Install the NGINX Ingress Controller
kubectl apply -f https://kind.sigs.k8s.io/examples/ingress/deploy-ingress-nginx.yaml
# kubectl apply -f https://raw.githubusercontent.com/kubernetes/ingress-nginx/main/deploy/static/provider/kind/deploy.yaml
# Wait for it to become ready
kubectl wait --namespace ingress-nginx \
  --for=condition=ready pod \
  --selector=app.kubernetes.io/component=controller \
  --timeout=120s

# Load images into KIND
kind load docker-image docker.io/blindmuaddib/music-translator:0.0.5
kind load docker-image docker.io/blindmuaddib/separate-endpoint:1
kind load docker-image docker.io/blindmuaddib/align-endpoint:1

# Apply Kubernetes YAML files
kubectl apply -f musictranslator/k8s/tls-secret.yaml
kubectl apply -f musictranslator/k8s/html-config.yaml
kubectl apply -f musictranslator/k8s/ingress.yaml
kubectl apply -f musictranslator/k8s/nginx-config.yaml
kubectl apply -f musictranslator/k8s/nginx-deployment.yaml
kubectl apply -f musictranslator/k8s/nginx-service.yaml
kubectl apply -f musictranslator/k8s/persistent-volumes.yaml
kubectl apply -f musictranslator/k8s/persistent-volumes-claims.yaml
kubectl apply -f musictranslator/k8s/main-deployment.yaml
kubectl apply -f musictranslator/k8s/main-service.yaml
kubectl apply -f musictranslator/k8s/demucs-deployment.yaml
kubectl apply -f musictranslator/k8s/demucs-service.yaml
kubectl apply -f musictranslator/k8s/mfa-deployment.yaml
kubectl apply -f musictranslator/k8s/mfa-service.yaml

# Wait for pods to become ready (add logic as needed)
sleep 20

# Run behave tests
# behave

# Ask if logs are requested
read -p "Do you want the cluster to remain active?? (y/n) " yn

if [[ "$yn" == "y" ]]; then
  echo "OK, the cluster will remain active. You can inspect the logs using kubectl logs <pod-name> -n default"
else
  echo "Deleting cluster then exiting..."
  kind delete cluster
fi
