# Deployment Guide

## Local Development

```bash
pip install -r requirements-dev.txt
uvicorn src.api.main:app --reload --port 8000
```

## Docker Compose

```bash
cp .env.example .env
# Fill in your API keys in .env
docker-compose up -d
```

Services will be available at:
- Agents API: http://localhost:8000
- API Gateway: http://localhost:8080
- ChromaDB: http://localhost:8001

## Kubernetes

### Prerequisites
- kubectl configured for your cluster
- Docker images pushed to registry

### Deploy

```bash
kubectl apply -f infrastructure/kubernetes/namespace.yaml

# Create secrets
kubectl create secret generic agi-secrets \
  --namespace=agi-system \
  --from-literal=openai-api-key=$OPENAI_API_KEY \
  --from-literal=anthropic-api-key=$ANTHROPIC_API_KEY

kubectl apply -f infrastructure/kubernetes/deployment.yaml
kubectl apply -f infrastructure/kubernetes/service.yaml
```

### Monitor rollout

```bash
kubectl rollout status deployment/agi-system -n agi-system
```

## Terraform (AWS)

```bash
cd infrastructure/terraform
terraform init
terraform plan -var="db_username=admin" -var="db_password=secret"
terraform apply
```

## CI/CD

The `.github/workflows/deploy.yml` pipeline:
1. Runs tests on every push/PR
2. Builds and pushes Docker images on merge to `main`
3. Deploys to Kubernetes with rollout verification
