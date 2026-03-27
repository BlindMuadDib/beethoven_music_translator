#!/bin/bash

# This will make the script exit immediately if any commands fail
set -e

# --- Configuration ---
# A name for the test cluster
export KIND_CLUSTER_NAME="musictranslator-test"
# Isolated config to protect bare-metal cluster
export KIND_CONFIG_PATH="${HOME}/.kube/kind-config-${KIND_CLUSTER_NAME}"
export KUBECONFIG="${KIND_CONFIG_PATH}"

# Images to load (Ensure these exist in the local Podman)
IMAGES=(
  "docker.io/blindmuaddib/music-translator:latest"
  "docker.io/blindmuaddib/align-endpoint:1.3"
  "docker.io/blindmuaddib/separate-endpoint:1.2"
  "docker.io/blindmuaddib/harmonic-endpoint:1.0"
  "docker.io/blindmuaddib/beethoven:0.1.1"
  "docker.io/blindmuaddib/drums-endpoint:1.2"
  "docker.io/blindmuaddib/auth-server:1.3"
)

# --- Robust Cleanup & Error Handling ---
# This `trap` command ensures that the 'cleanup' function is called
# one any script exit (EXIT), interrupt (INT), or termination (TERM) signal.
# This guarantees cleanup even if a command fails.
# trap cleanup EXIT INT TERM

# Function to ask for log check and handle input
cleanup() {
  echo -e "\n--- CLEANUP ---"
  echo "Deleting the cluster then exiting..."
  kind delete cluster --name ${KIND_CLUSTER_NAME} --kubeconfig ${KIND_CONFIG_PATH} || true

  echo "Removing isolated kubeconfig file..."
  rm -f ${KIND_CONFIG_PATH}
  echo "Done."
}

# This function runs if any command fails (due to set -e)
catch_error() {
  echo -e "\n❌ TEST SCRIPT FAILED!"
  echo "The cluster is currently paused for debugging."
  echo "You can check logs using:"
  echo "  export KUBECONFIG=${KIND_CONFIG_PATH}"
  echo "  kubectl get pods -A"
  echo ""
  read -p "Press [Enter] to run cleanup and delete the cluster..."
  cleanup
  exit 1
}

# Set the trap
trap 'catch_error' ERR

# --- 1. Infrastructure Setup ---
# Ensure the hostPath directory exists BEFORE creating the cluster
#echo "Ensuring hostPath directory exists at /opt/MTD/shared-data..."
#mkdir -p /opt/MTD/shared-data
#mkdir -p /opt/MTD/shared-data/audio
#mkdir -p /opt/MTD/shared-data/lyrics
#mkdir -p /opt/MTD/shared-data/results
#chmod -R 777 /opt/MTD/shared-data

# Start KIND cluster
echo "Starting KIND cluster '${KIND_CLUSTER_NAME}'..."
# Tell KIND create to *use* the isolated CONFIG path
kind create cluster --name ${KIND_CLUSTER_NAME} --config tests/KIND/kind-config.yaml --kubeconfig ${KIND_CONFIG_PATH}

# --- Verification Step ---
# Verify the new cluster is using the specified subnet before wasting time
# with starting ingress
echo "Verifying Network Isolation..."
API_SVC_IP=$(kubectl get svc kubernetes -o jsonpath='{.spec.clusterIP}')
echo "KIND API Service IP is: $API_SVC_IP"

if [[ $API_SVC_IP == "10.96.0.1" ]]; then
  echo "❌ CRITICAL ERROR: Network isolation failed! KIND is using the default 10.96.0.1 which conflicts with Host Cilium."
  echo "Aborting test to prevent network confusion."
  catch_error
  exit 1
elif [[ $API_SVC_IP == "10.128.0.1" ]]; then
  echo "✅ Network Isolation Confirmed (IP is 10.128.0.1)"
else
  echo "⚠️ Unexpected API IP: $API_SVC_IP (Expected 10.111.0.1), but at least it's not 10.96.0.1."
fi

echo "KUBECONFIG set to: ${KUBECONFIG}"

sleep 5

echo "Installing NGINX Ingress Controller for KIND..."
kubectl apply -f https://raw.githubusercontent.com/kubernetes/ingress-nginx/main/deploy/static/provider/kind/deploy.yaml

echo "Waiting for NGINX Ingress Controller to be ready..."
kubectl wait --for=condition=ready pod -n ingress-nginx -l app.kubernetes.io/component=controller --timeout=300s
echo "NGINX Ingress Controller is ready."

# --- 2. Load Images (Podman Support) ---
echo "Loading images from Podman..."
for img in "${IMAGES[@]}"; do
  echo " - $img"
  # Load images with a pipe to avoid creating large temp files on disk
  podman save $img | kind load image-archive /dev/stdin --name ${KIND_CLUSTER_NAME}
done

# --- 3. Deploy "Stub" Infrastructure ---

# A. Simple Postgres (Instead of Zalando Operator)
echo "Deploying Stub Test Database..."
kubectl apply -f tests/KIND/postgres-test.yaml

# B. Create Secrets (Matching what Deployment expects)
echo "Creating Secrets..."
# 1. Auth Server Secrets
kubectl create secret generic auth-server-secrets \
  --from-literal=SECRET_KEY="test_secret_key" \
  --from-literal=SECRET_PASSWORD_SALT="test_salt" \
  --from-literal=ADMIN_INITIAL_PASSWORD="super-insecure-default-password"

# 2. Database Credentials (matching the Zalando naming convention referenced in deployment)
kubectl create secret generic translator-admin.auth-db-cluster.credentials.postgresql.acid.zalan.do \
  --from-literal=username="postgres" \
  --from-literal=password="postgres"

# --- Deploy Application ---
echo "Deploying Application Manifests..."
# Apply Kubernetes YAML files
# A. Storage Manifests
kubectl apply -f tests/KIND/persistent-volumes.yaml
kubectl apply -f tests/KIND/persistent-volumes-claims.yaml

# B. Application App Manifests
kubectl apply -f k8s/redis-deployment.yaml
kubectl apply -f k8s/redis-service.yaml
kubectl apply -f k8s/main-deployment.yaml
kubectl apply -f k8s/main-service.yaml
kubectl apply -f k8s/worker-deployment.yaml
kubectl apply -f k8s/demucs-deployment.yaml
kubectl apply -f k8s/demucs-service.yaml
kubectl apply -f k8s/mfa-deployment.yaml
kubectl apply -f k8s/mfa-service.yaml
kubectl apply -f k8s/harmonic-deployment.yaml
kubectl apply -f k8s/harmonic-service.yaml
kubectl apply -f k8s/beethoven-deployment.yaml
kubectl apply -f k8s/beethoven-service.yaml
kubectl apply -f k8s/drums-deployment.yaml
kubectl apply -f k8s/drums-service.yaml

# C. Auth Server (Using the KIND-specific file)
kubectl apply -f tests/KIND/auth-deployment_KIND_testing.yaml
kubectl apply -f k8s/auth-service.yaml

# --- 5. CRITICAL: Path Auth Server ---
# This makes the Auth Server talk to the stub DB, not the production name
echo "Pathing Auth Server to use Stub DB..."
kubectl set env deployment/auth-server-deployment POSTGRES_HOST=auth-db-test

# --- 6. Configure Ingress ---
echo "Configuring Ingress..."
kubectl apply -f tests/KIND/ingress-auth-reset_KIND_testing.yaml
kubectl apply -f tests/KIND/ingress-auth_KIND_testing.yaml
kubectl apply -f tests/KIND/ingress_KIND_testing.yaml

# --- 7. Wait for Readiness ---
echo "Waiting for deployments to be ready ..."
kubectl wait --for=condition=available deployment/auth-server-deployment --timeout=300s
kubectl wait --for=condition=available deployment/translator-deployment --timeout=300s
kubectl wait --for=condition=available deployment/translator-worker --timeout=300s
kubectl wait --for=condition=available deployment/mfa-deployment --timeout=300s
kubectl wait --for=condition=available deployment/demucs-deployment --timeout=300s
kubectl wait --for=condition=available deployment/harmonic-deployment --timeout=300s
kubectl wait --for=condition=available deployment/redis --timeout=300s
kubectl wait --for=condition=available deployment/beethoven-deployment --timeout=300s
kubectl wait --for=condition=available deployment/drums-deployment --timeout=300s

echo "System ready. Starting Tests."

# --- 8. Interactive Integration Testing Loop ---
export TEST_BASE_URL="http://localhost:9000/api"
export TEST_AUTH_URL="http://localhost:9000/auth"

# Disable the global error trap so we can handle test failures interactively
trap - ERR

while true; do
  echo -e "\n--- 🧪 Starting Integration Tests ---"

  # Disable 'set -e' temporarily to capture test failure
  set +e
  pytest -v tests/test_integration.py
  TEST_RESULT=$?
  set -e

  # Check result
  if [ $TEST_RESULT -eq 0 ]; then
    echo "✅ Tests PASSED."
  else
    echo "❌ Tests FAILED."
    echo "The cluster is still running for debugging."
    echo "Use this command to interact with it:"
    echo "  export KUBECONFIG=${KIND_CONFIG_PATH}"
    echo "  kubectl get pods"
    echo "  kubectl logs -l app=auth-server"
  fi

  # Interactive Prompt
  echo -e "\n-----------------------------------------"
  echo "The cluster is still running."
  read -p "Press [T] to re-run tests, or [Enter] to cleanup and exit: " choice

  case "$choice" in
    t|T)
      echo "🔄 Re-running tests..."
      continue
      # Loop continues...
      ;;
    *)
      echo "👋 Proceeding to cleanup..."
      cleanup
      exit $TEST_RESULT
      ;;
  esac
done

