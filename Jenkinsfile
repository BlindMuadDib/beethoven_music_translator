pipeline {
    agent any

    stages {
        stage('Checkout') {
            steps {
                git branch: 'main', url: 'https://github.com/BlindMuadDib/Music-Translation-for-and-by-Deaf.git'
            }
        }
        stage('Set up environment') {
            steps {
                sh 'python -m venv venv'
                sh 'source venv/bin/activate && pip install -r requirements.txt'
                sh 'mkdir -p tools'
                sh 'curl -Lo tools/kind https://kind.sigs.k8s.io/dl/v0.20.0/kind-linux-amd64'
                sh 'chmod +x tools/kind'
                sh 'curl -o tools/kubectl -LO "https://dl.k8s.io/release/$(curl -L -s https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl"'
                sh 'chmod +x tools/kubectl'
                withEnv(['PATH+EXTRA=$WORKSPACE/tools']) {
                    sh 'echo "PATH is now: $PATH"'
                    sh '$WORKSPACE/tools/kind --version'
                    sh '$WORKSPACE/tools/kubectl version --client'
                }
            }
        }
        stage('Start KIND and Deploy') {
            steps {
                sh '$WORKSPACE/tools/kind create cluster --config k8s/kind-config.yaml --wait 5m'
                sh '$WORKSPACE/tools/kubectl apply -f https://kind.sigs.k8s.io/examples/ingress/deploy-ingress-nginx.yaml'
                sh '$WORKSPACE/tools/kubectl wait --namespace ingress-nginx --for=condition=ready pod --selector=app.kubernetes.io/component=controller --timeout=120s'
                sh '$WORKSPACE/tools/kubectl apply -f k8s/worker-deployment.yaml'
                sh '$WORKSPACE/tools/kubectl apply -f k8s/persistent-volumes.yaml'
                sh '$WORKSPACE/tools/kubectl apply -f k8s/persistent-volumes-claims.yaml'
                sh '$WORKSPACE/tools/kubectl apply -f k8s/html-config.yaml'
                sh '$WORKSPACE/tools/kubectl apply -f k8s/nginx-config.yaml'
                sh '$WORKSPACE/tools/kubectl apply -f k8s/redis-deployment.yaml'
                sh '$WORKSPACE/tools/kubectl apply -f k8s/main-deployment.yaml'
                sh '$WORKSPACE/tools/kubectl apply -f k8s/demucs-deployment.yaml'
                sh '$WORKSPACE/tools/kubectl apply -f k8s/mfa-deployment.yaml'
                sh '$WORKSPACE/tools/kubectl apply -f k8s/nginx-deployment.yaml'
                sh '$WORKSPACE/tools/kubectl apply -f k8s/redis-service.yaml'
                sh '$WORKSPACE/tools/kubectl apply -f k8s/main-service.yaml'
                sh '$WORKSPACE/tools/kubectl apply -f k8s/demucs-service.yaml'
                sh '$WORKSPACE/tools/kubectl apply -f k8s/mfa-service.yaml'
                sh '$WORKSPACE/tools/kubectl apply -f k8s/nginx-service.yaml'
                sh '$WORKSPACE/tools/kubectl apply -f k8s/ingress.yaml'
                sh '$WORKSPACE/tools/kubectl wait --for=condition=available deployment/translator-deployment --timeout=300s'
                sh '$WORKSPACE/tools/kubectl wait --for=condition=available deployment/translator-worker --timeout=300s'
                sh '$WORKSPACE/tools/kubectl wait --for=condition=available deployment/redis --timeout=300s'
                sh '$WORKSPACE/tools/kubectl wait --for=condition=available deployment/nginx-deployment --timeout=300s'
                sh '$WORKSPACE/tools/kubectl wait --for=condition=available deployment/demucs-deployment --timeout=600s'
                sh '$WORKSPACE/tools/kubectl wait --for=condition=available deployment/mfa-deployment --timeout=600s'
            }
        }
        stage('Run Tests') {
            steps {
                sh 'source venv/bin/activate' // Ensure virtual environment is active
                sh 'pytest'
            }
        }
        stage('Teardown') {
            steps {
                sh 'kind delete cluster'
            }
        }
    }
}
