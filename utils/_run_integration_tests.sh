#!/bin/bash

# This will make the script exit immediately if any commands fail during setup
set -e

# --- Configuration ---
export KIND_CLUSTER_NAME="musictranslator-test"
export KIND_CONFIG_PATH="${HOME}/.kube/kind-config-${KIND_CLUSTER_NAME}"
export KUBECONFIG="${KIND_CONFIG_PATH}"

# Images to load from local Podman
IMAGES=(
    "docker.io/blindmuaddib/music-translator:latest"
    "docker.io/blindmuaddib/align-endpoint:1.3"
    "docker.io/blindmuaddib/separate-endpoint:1.2"
    "docker.io/blindmuaddib/harmonic-endpoint:1.0"
    "docker.io/blindmuaddib/beethoven:0.1.3"
    "docker.io/blindmuaddib/auth-server:1.3"
)

# --- Cleanup & Error Handling ---
cleanup() {
    echo -e "\n--- CLEANUP ---"
    echo "Deleting cluster then exiting..."
    kind delete cluster --name ${KIND_CLUSTER_NAME} --kubeconfig ${KIND_CONFIG_PATH} || true
    rm -f ${KIND_CONFIG_PATH}
    echo "Done.
}

catch_error() {
    echo -e "\n❌ TEST SETUP FAILED!"
    echo "The cluster is paused for debugging."
    echo "Run 'kubectl --kubeconfig ${KIND_CONFIG_PATH} get pods -A' to see what's wrong."
    echo "You can also run 'kubectl --kubeconfig ${KIND_CONFIG_PATH} logs -f <pod-name>' to see logs."
    echo ""
    read -p "Press [Enter] to run cleanup and delete the cluster..."
    cleanup
    exit 1
}

# Set the trap for setup errors
trap 'catch_error' ERR

# --- 1. Infrastructure Setup ---
echo "Ensuring hostPath directories exist at /opt/MTD/shared-data..."
mkdir -p /opt/MTD/shared-data/audio
mkdir -p /opt/MTD/shared-data/lyrics
mkdir -p /opt/MTD/shared-data/results
mkdir -p /opt/MTD/shared-data/results
chmod -R 777 /opt/MTD/shared-data

echo "Starting KIND cluster '${KIND_CLUSTER_NAME}'..."
kind create cluster \
    --name ${KIND_CLUSTER_NAME} \
    --config tests/KIND/kind-config.yaml \
    --kubeconfig ${KIND_CONFIG_PATH}

# --- Verification Step ---
echo "Verifying Network Isolation..."
API_SVC_IP=$(kubectl get svc kubernetes -o jsonpath='{spec.clusterIP}')
echo "KIND API Service IP is: $API_SVC_IP"

if [[ $API_SVC_IP == "10.96.0.1" ]]; then
    echo "❌ CRITICAL ERROR: Network isolation failed!"
    echo "KIND is using the default 10.96.0.1."
    catch_error
    exit 1
elif [[ $API_SVC_IP == "10.128.0.1" ]]; then
    echo "✅ Network Isolation Confirmed (IP is 10.128.0.1)"
else
    echo "⚠️ WARNING: Unexpected API IP: $API_SVC_IP (Expected 10.128.0.1)"
fi

sleep 5

echo "Installing NGINX Ingress Controller for KIND..."
kubectl apply -f https://raw.githubusercontent.com/kubernetes/ingress-nginx/main/deploy/static/provider/kind/deploy.yaml

echo "Waiting for Ingress Controller to be ready..."
kubectl wait --for=condition=ready pod -n ingress-nginx -l app.kubernetes.io/component=controller --timeout=300s
echo "NGINX Ingress Controller is ready."

# --- 2. Load Images (Podman Support) ---
echo "Loading images from Podman..."
for img in "${IMAGES[@]}"; do
    echo " -$img"
    podman save "$img" | kind load image-archive /dev/stdin --name ${KIND_CLUSTER_NAME}
done

# --- 3. Deploy "Stub" Infrastructure ---
echo "Deploying Stub Test Database..."
kubectl apply -f tests/KIND/postgres-test.yaml

echo "Creating Secrets..."
kubectl create secret generic auth-server-secrets \
    --from-literal=SECRET_KEY="test_secret_key" \
    --from-literal=SECURITY_PASSWORD_SALT="test_salt" \
    --from-literal=ADMIN_INITIAL_PASSWORD="super-insecure-default-password"

kubectl create secret generic translator-admin.auth-db-cluster.credentials.postgresql.acid.zalan.do \
    --from-literal=username="postgres" \
    --from-literal=password="postgres"

# --- 4. Deploy Application ---
echo "Deploying Application Manifests..."
kubectl apply -f tests/KIND/persistent-volumes.yaml
kubectl apply -f tests/KIND/persistent-volumes-claims.yaml

kubectl apply -f k8s/redis-deployment.yaml
kubectl apply -f k8s/redis-service.yaml
kubectl apply -f k8s/main-deployment.yaml
kubectl apply -f k8s/main-service.yaml
kubectl apply -f k8s/worker-deployment.yaml
kubectl apply -f k8s/demucs-deployment.yaml
kubectl apply -f k8s/demucs-service.yaml
kubectl apply -f k8s/harmonic-deployment.yaml
kubectl apply -f k8s/harmonic-service.yaml
kubectl apply -f k8s/beethoven-deployment.yaml
kubectl apply -f k8s/beethoven-service.yaml
kubectl apply -f k8s/drums-deployment.yaml
kubectl apply -f k8s/drums-service.yaml

kubectl apply -f tests/KIND/auth-deployment_KIND_testing.yaml
kubectl apply -f k8s/auth-service.yaml

# --- 5. Path Auth Server ---
echo "Pathing Auth Server to use Stub DB..."
kubectl set env deployment/auth-server-deployment POSTGRES_HOST=auth-db-test

# --- 6. Configure Ingress ---
echo "Configuring Ingress..."
kubectl apply -f tests/KIND/ingress-auth-reset_KIND_testing.yaml
kubectl apply -f tests/KIND/ingress-auth_KIND_testing.yaml
kubectl apply -f tests/KIND/ingress_KIND_testing.yaml

# --- 7. Wait for Readiness ---
echo "Waiting for deployments to be ready..."
kubectl wait --for=condition=available deployment/auth-server-deployment --timeout=300s
kubectl wait --for=condition=available deployment/translator-deployment --timeout=300s
kubectl wait --for=condition=available deployment/translator-worker --timeout=300s
kubectl wait --for=condition=available deployment/mfa-deployment --timeout=300s
kubectl wait --for=condition=available deployment/demucs-deployment --timeout=300s
kubectl wait --for=condition=available deployment/harmonic-deployment --timeout=300s
kubectl wait --for=condition=available deployment/beethoven-deployment --timeout=300s
kubectl wait --for=condition=available deployment/drums-deployment --timeout=300s
kubectl wait --for=condition=available deployment/redis --timeout=300s

echo "System ready. Starting Tests."

# --- 8. Interactive Integration Testing Loop ---
export TEST_BASE_URL="http://localhost:9000/api"
export TEST_AUTH_URL="http://localhost:9000/auth"

# Disable global trap so the loop can handle failures interactively
trap - ERR

while true; do
    echo -e "\n--- 🧪Starting Integration Tests ---"
    
    set +e
    pytest -v tests/test_integration.py
    TEST_RESULT=$?
    set -e

    if [ $TEST_RESULT -eq 0 ]; then
        echo -e "\n✅ Tests PASSED!"
    else
        echo -e "\n❌ Tests FAILED!"
        echo "The cluster is paused for debugging. Inspect the environment:"
        echo "  kubectl --kubeconfig ${KIND_CONFIG_PATH} get pods -A"
        echo "  kubectl --kubeconfig ${KIND_CONFIG_PATH} logs -f <pod-name>"
    fi

    echo -e "\n-------------------------------------------------"
    read -p "Press [T] to re-run tests, or [Enter] to cleanup and exit: " choice

    case "$choice" in
        t|T)
            echo "🔄 Re-running tests..."
            continue
        ;;
    *)
        echo "🧹 Cleaning up and exiting..."
        cleanup
        exit $TEST_RESULT
        ;;
    esac
done
