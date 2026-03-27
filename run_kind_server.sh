# Start KIND cluster
kind create cluster --config k8s/kind-config.yaml

# Apply example ingress deployment
kubectl apply -f https://kind.sigs.k8s.io/examples/ingress/deploy-ingress-nginx.yaml

# Verify Ingress controller pods are starting
echo "Waiting briefly for Ingress controller namespace ..."
kubectl wait --namespace ingress-nginx \
  --for=condition=ready pod \
  --selector=app.kubernetes.io/component=controller \
  --timeout=180s

# Load images into KIND
kind load docker-image blindmuaddib/music-translator:0.0.6
kind load docker-image blindmuaddib/align-endpoint:1.1
kind load docker-image blindmuaddib/separate-endpoint:1
kind load docker-image blindmuaddib/f0-endpoint:1

# Apply Kubernetes YAML files
kubectl apply -f k8s/worker-deployment.yaml
kubectl apply -f k8s/persistent-volumes.yaml
kubectl apply -f k8s/persistent-volumes-claims.yaml
kubectl apply -f k8s/html-config.yaml
kubectl apply -f k8s/nginx-config.yaml
kubectl apply -f k8s/redis-deployment.yaml
kubectl apply -f k8s/main-deployment.yaml
kubectl apply -f k8s/demucs-deployment.yaml
kubectl apply -f k8s/mfa-deployment.yaml
kubectl apply -f k8s/f0-deployment.yaml
kubectl apply -f k8s/nginx-deployment.yaml
kubectl apply -f k8s/redis-service.yaml
kubectl apply -f k8s/main-service.yaml
kubectl apply -f k8s/demucs-service.yaml
kubectl apply -f k8s/mfa-service.yaml
kubectl apply -f k8s/f0-service.yaml
kubectl apply -f k8s/nginx-service.yaml
kubectl apply -f k8s/tls-secret.yaml
kubectl apply -f k8s/ingress.yaml

# Wait for pods to become ready (add logic as needed)
echo "Waiting for deployments to be ready ..."
kubectl wait --for=condition=available deployment/translator-deployment --timeout=300s
kubectl wait --for=condition=available deployment/translator-worker --timeout=300s
kubectl wait --for=condition=available deployment/mfa-deployment --timeout=300s
kubectl wait --for=condition=available deployment/demucs-deployment --timeout=300s
kubectl wait --for=condition=available deployment/f0-deployment --timeout=300s
kubectl wait --for=condition=available deployment/redis --timeout=300s
kubectl wait --for=condition=available deployment/nginx-deployment --timeout=300s

echo "Waiting for Ingress to be ready ..."
kubectl wait --namespace ingress --for=condition=ready musictranslator-ingress --timeout=120s

echo "Deployments and Ingress ready. Running tests ..."

# Run integration tests
pytest -v tests/test_integration.py
