#!/bin/bash

# Start KIND cluster
kind create cluster --config config.yaml

# # Build Docker images
# podman build -f musictranslator.Dockerfile -t music-translator:latest --format docker
# podman build -f musictranslator/align-endpoint.Dockerfile -t mfa-wrapper:latest --format docker
# podman build -f musictranslator/separate-endpoint.Dockerfile -t demucs-wrapper:latest --format docker

# Load images into KIND
kind load docker-image music-translator:latest
kind load docker-image mfa-wrapper:latest
kind load docker-image demucs-wrapper:latest

# Apply Kubernetes YAML files
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

# Run integration tests
pytest -v tests/test_integration.py

# Ask if logs are requested
read -p "Do you want to check the logs?? (y/n) " yn

if [[ "$yn" == "y" ]]; then
  echo "OK, the cluster will remain running. You can inspect the logs using kubectl logs <pod-name> -n default"
else
  echo "Deleting cluster then exiting..."
  kind delete cluster
fi
