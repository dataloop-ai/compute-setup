# Compute Setup Configuration Guide

This guide explains how to configure the compute setup for your Kubernetes cluster. Follow the step-by-step instructions below to fill in each configuration field.

---

## Table of Contents

1. [Overview](#overview)
2. [Prerequisites](#prerequisites)
3. [Quick Start](#quick-start)
4. [Configuration Fields Reference](#configuration-fields-reference)
   - [Organization Settings](#1-organization-settings)
   - [Cluster Settings](#2-cluster-settings)
   - [Authentication](#3-authentication)
   - [Registry Settings](#4-registry-settings)
   - [Network Settings](#5-network-settings)
   - [Volumes](#6-volumes)
   - [Plugins](#7-plugins)
   - [Node Pools](#8-node-pools)
   - [Default Resources](#9-default-resources)
   - [Security Context](#10-security-context)
   - [Output Settings](#11-output-settings)
5. [Running the Script](#running-the-script)
6. [Multiple Namespaces](#multiple-namespaces)
7. [Troubleshooting](#troubleshooting)

---

## Overview

The compute setup script connects your Kubernetes cluster, enabling you to run FaaS (Functions as a Service) workloads. The configuration is stored in a JSON file that you customize for your environment.

---

## Prerequisites

Before you begin, make sure you have:

- [ ] **Organization ID** - Found in your console
- [ ] **Kubernetes cluster** with API access
- [ ] **Service Account** with appropriate permissions in your cluster
- [ ] **Python 3.8+** installed
- [ ] **dtlpy SDK** installed (`pip install dtlpy`)

---

## Quick Start

1. Copy the template file:
   ```bash
   cp configs/config-template.json configs/config-myenv.json
   ```

2. Edit the new file with your values (see field reference below)

3. Run the setup:
   ```bash
   python compute_setup.py --config configs/config-myenv.json
   ```

---

## Configuration Fields Reference

### 1. Organization Settings

```json
"organization": {
  "orgId": "c263bc74-fa70-456e-a319-b93c81db264b",
  "env": "rc"
}
```

| Field | Required | Description | How to Find |
|-------|----------|-------------|-------------|
| `orgId` | ✅ Yes | Your Dataloop organization ID | Go to Dataloop Console → Settings → Organization → Copy the ID |
| `env` | ✅ Yes | Dataloop environment | Use `rc` for staging, `prod` for production |

**Example values for `env`:**
- `rc` - Release Candidate (staging/testing)
- `prod` - Production environment
- `dev` - Development environment

---

### 2. Cluster Settings

```json
"cluster": {
  "name": "my-company-faas-aws",
  "endpoint": "https://ABC123.gr7.us-east-1.eks.amazonaws.com",
  "kubernetesVersion": "1.29",
  "provider": "aws",
  "defaultNamespace": "faas"
}
```

| Field | Required | Description | How to Find |
|-------|----------|-------------|-------------|
| `name` | ✅ Yes | A unique name for this cluster configuration | Choose a descriptive name (e.g., `company-env-faas-provider`) |
| `endpoint` | ✅ Yes | Kubernetes API server URL | See instructions below |
| `kubernetesVersion` | ✅ Yes | Your cluster's Kubernetes version | Run `kubectl version --short` |
| `provider` | ✅ Yes | Cloud provider | `aws`, `gcp`, or `azure` |
| `defaultNamespace` | ✅ Yes | Namespace for FaaS workloads | Usually `faas` - must exist in your cluster |
| `serviceAccountName` | No | Service account for pods | Defaults to `faas` (must exist in the namespace) |

**How to find your cluster endpoint:**

For **AWS EKS**:
```bash
aws eks describe-cluster --name YOUR_CLUSTER_NAME --query "cluster.endpoint" --output text
```

For **GCP GKE**:
```bash
gcloud container clusters describe YOUR_CLUSTER_NAME --zone YOUR_ZONE --format="get(endpoint)"
# Add https:// prefix to the result
```

For **Azure AKS**:
```bash
az aks show --resource-group YOUR_RG --name YOUR_CLUSTER_NAME --query fqdn --output tsv
# Add https:// prefix to the result
```

Or from your kubeconfig:
```bash
kubectl config view --minify -o jsonpath='{.clusters[0].cluster.server}'
```

---

### 3. Authentication

```json
"authentication": {
  "ca": "LS0tLS1CRUdJTi...(base64 encoded)...",
  "token": "eyJhbGciOiJSUzI1NiIs...(JWT token)..."
}
```

| Field | Required | Description | How to Find |
|-------|----------|-------------|-------------|
| `ca` | ✅ Yes | Base64-encoded cluster CA certificate | See instructions below |
| `token` | ✅ Yes | Service account JWT token | See instructions below |

**How to get the CA certificate (base64 encoded):**

```bash
# From kubeconfig
kubectl config view --raw --minify -o jsonpath='{.clusters[0].cluster.certificate-authority-data}'

# Or from a secret (if using a service account)
kubectl get secret <secret-name> -n <namespace> -o jsonpath='{.data.ca\.crt}'
```

**How to get the service account token:**

First, create a service account and secret (if not exists):
```bash
# Create service account
kubectl create serviceaccount faas -n faas

# Create a long-lived token secret
cat <<EOF | kubectl apply -f -
apiVersion: v1
kind: Secret
metadata:
  name: faas
  namespace: faas
  annotations:
    kubernetes.io/service-account.name: faas
type: kubernetes.io/service-account-token
EOF
```

Then get the token:
```bash
kubectl get secret faas -n faas -o jsonpath='{.data.token}' | base64 --decode
```

---

### 4. Registry Settings

```json
"registry": {
  "domain": "hub.dataloop.ai",
  "faasFolder": "customerhub",
  "bootstrapFolder": "customerhub"
}
```

| Field | Required | Description | Default Value |
|-------|----------|-------------|---------------|
| `domain` | ✅ Yes | Container registry domain | `hub.dataloop.ai` |
| `faasFolder` | ✅ Yes | Folder/repository for FaaS images | `customerhub` |
| `bootstrapFolder` | ✅ Yes | Folder/repository for bootstrap images | `customerhub` |

**Common registry domains:**
- Dataloop: `hub.dataloop.ai`
- Docker Hub: `docker.io`
- AWS ECR: `123456789.dkr.ecr.us-east-1.amazonaws.com`
- GCP GCR: `gcr.io`
- Azure ACR: `myregistry.azurecr.io`

---

### 5. Network Settings

```json
"network": {
  "internalRequestsUrl": null,
  "environmentVariables": [
    {"name": "HTTP_PROXY", "value": "http://proxy.company.com:8080"},
    {"name": "NO_PROXY", "value": "localhost,127.0.0.1,.company.com"}
  ]
}
```

| Field | Required | Description |
|-------|----------|-------------|
| `internalRequestsUrl` | No | Internal URL for requests (set to `null` if not needed) |
| `environmentVariables` | No | List of environment variables to inject into all pods |

**Common environment variables:**

For corporate proxies:
```json
"environmentVariables": [
  {"name": "HTTP_PROXY", "value": "http://proxy.company.com:8080"},
  {"name": "HTTPS_PROXY", "value": "http://proxy.company.com:8080"},
  {"name": "NO_PROXY", "value": "localhost,127.0.0.1,.svc.cluster.local,.company.com"}
]
```

For custom settings:
```json
"environmentVariables": [
  {"name": "LINK_ITEM_URL_OVERRIDE", "value": "http://localhost:5500,file://path"}
]
```

---

### 6. Volumes

```json
"volumes": [
  {
    "name": "shared-data",
    "mountPath": "/data",
    "hostPath": {
      "path": "/mnt/shared-data",
      "type": "DirectoryOrCreate"
    }
  }
]
```

Each volume must include `name` and `mountPath`, and should define **exactly one** volume source: `hostPath`, `persistentVolumeClaim`, `emptyDir`, `configMap`, `secret`, or `nfs`.

| Field | Required | Description |
|-------|----------|-------------|
| `name` | ✅ Yes | Unique name for the volume |
| `mountPath` | ✅ Yes | Path where volume will be mounted in pods |
| `subPath` | No | Mount a sub-path inside the volume |
| `readOnly` | No | Mount as read-only |
| `hostPath.path` | For hostPath | Path on the node filesystem |
| `hostPath.type` | For hostPath | HostPath type (e.g. `Directory`, `DirectoryOrCreate`, `File`, `FileOrCreate`) |
| `persistentVolumeClaim.claimName` | For PVC | Existing PVC name |
| `emptyDir` | For emptyDir | EmptyDir volume (use `{}` for defaults) |
| `configMap.name` | For configMap | ConfigMap name |
| `configMap.items[]` | Optional | Map keys to file paths |
| `secret.secretName` | For secret | Secret name |
| `secret.items[]` | Optional | Map keys to file paths |
| `nfs.server` | For NFS | NFS server IP address / hostname |
| `nfs.path` | For NFS | Path on the NFS server |

**Example (recommended): hostPath volume**
```json
{
  "name": "project-data",
  "mountPath": "/mnt/project",
  "readOnly": false,
  "hostPath": {
    "path": "/mnt/project",
    "type": "DirectoryOrCreate"
  }
}
```

**Example: hostPath with subPath**
```json
{
  "name": "shared-data",
  "mountPath": "/data",
  "subPath": "team-a",
  "hostPath": {
    "path": "/mnt/shared-data",
    "type": "Directory"
  }
}
```

**Example: persistentVolumeClaim**
```json
{
  "name": "pvc-data",
  "mountPath": "/data",
  "persistentVolumeClaim": {
    "claimName": "shared-pvc"
  }
}
```

**Example: configMap**
```json
{
  "name": "app-config",
  "mountPath": "/etc/app",
  "readOnly": true,
  "configMap": {
    "name": "my-config",
    "items": [
      { "key": "config.json", "path": "config.json" }
    ]
  }
}
```

**Example: secret**
```json
{
  "name": "app-secret",
  "mountPath": "/etc/secret",
  "readOnly": true,
  "secret": {
    "secretName": "my-secret",
    "items": [
      { "key": "token", "path": "token" }
    ]
  }
}
```

**Example: NFS volume**
```json
{
  "name": "nfs-data",
  "mountPath": "/mnt/nfs",
  "nfs": {
    "server": "192.168.1.100",
    "path": "/exports/project"
  }
}
```

**Example: No volumes needed**
```json
"volumes": []
```

---

### 7. Plugins

```json
"plugins": [
  {"name": "monitoring"},
  {"name": "scaler"}
]
```

The following plugins are supported. For Dataloop compute setup, **`monitoring`** and **`scaler`** are **mandatory**.

| Plugin | Description | Required |
|--------|-------------|-------------|
| `monitoring` | Enables metrics and monitoring | ✅ Yes |
| `scaler` | Enables auto-scaling of services | ✅ Yes |

**Minimal setup:**
```json
"plugins": [
  {"name": "monitoring"},
  {"name": "scaler"}
]
```

**With external monitoring:**
```json
"plugins": [
  {
    "name": "monitoring",
    "useExternalResources": true,
    "config": {
      "port": "9090",
      "namespace": "monitoring",
      "serviceName": "prometheus"
    }
  },
  {"name": "scaler"}
]
```

---

### 8. Node Pools

```json
"nodePools": [
  {
    "name": "general-pool",
    "isDlTypeDefault": true,
    "dlTypes": ["regular-xs", "regular-s", "regular-m"],
    "tolerations": [],
    "description": "Default pool for general workloads",
    "nodeSelector": {},
    "preemptible": false
  }
]
```

| Field | Required | Description |
|-------|----------|-------------|
| `name` | ✅ Yes | Unique name for the node pool |
| `isDlTypeDefault` | ✅ Yes | Set to `true` for the default pool |
| `dlTypes` | ✅ Yes | List of Dataloop instance types (see table below) |
| `tolerations` | No | Kubernetes tolerations for tainted nodes |
| `description` | No | Human-readable description |
| `nodeSelector` | No | Kubernetes node selector labels |
| `preemptible` | No | Whether to use preemptible/spot instances |

**Valid `dlTypes` values:**

| Category | Values | Description |
|----------|--------|-------------|
| CPU Regular | `regular-xs`, `regular-s`, `regular-m`, `regular-l` | Standard CPU instances |
| CPU High Memory | `highmem-xs`, `highmem-s`, `highmem-m`, `highmem-l` | High memory instances |
| GPU T4 | `gpu-t4`, `gpu-t4-m` | NVIDIA T4 GPU instances |
| GPU A100 | `gpu-a100-s`, `gpu-a100-4g`, `gpu-a100-4g-m` | NVIDIA A100 GPU instances |

**Example: General + GPU pools**
```json
"nodePools": [
  {
    "name": "general-pool",
    "isDlTypeDefault": true,
    "dlTypes": ["regular-xs", "regular-s", "regular-m", "regular-l"],
    "tolerations": [],
    "description": "Default pool for CPU workloads",
    "nodeSelector": {},
    "preemptible": false
  },
  {
    "name": "gpu-pool",
    "isDlTypeDefault": false,
    "dlTypes": ["gpu-t4", "gpu-a100-s"],
    "tolerations": [
      {"key": "nvidia.com/gpu", "operator": "Exists", "effect": "NoSchedule"}
    ],
    "description": "GPU pool for ML workloads",
    "nodeSelector": {"gpu": "true"},
    "preemptible": true
  }
]
```

**Example: With tolerations for tainted nodes**
```json
"tolerations": [
  {
    "key": "dedicated",
    "operator": "Equal",
    "value": "faas",
    "effect": "NoSchedule"
  }
]
```

---

### 9. Default Resources

```json
"defaultResources": {
  "requests": {
    "cpu": "10m",
    "memory": "200Mi"
  },
  "limits": {
    "cpu": "1500m",
    "memory": "2G"
  }
}
```

| Field | Description | Example Values |
|-------|-------------|----------------|
| `requests.cpu` | Minimum CPU requested | `10m`, `100m`, `500m`, `1`, `2` |
| `requests.memory` | Minimum memory requested | `128Mi`, `256Mi`, `512Mi`, `1Gi` |
| `limits.cpu` | Maximum CPU allowed | `500m`, `1`, `2`, `4` |
| `limits.memory` | Maximum memory allowed | `512Mi`, `1G`, `2G`, `4Gi` |

**Understanding CPU values:**
- `1000m` = 1 CPU core
- `500m` = 0.5 CPU core
- `100m` = 0.1 CPU core

**Understanding memory values:**
- `Mi` = Mebibytes (1 Mi = 1,048,576 bytes)
- `Gi` = Gibibytes (1 Gi = 1,073,741,824 bytes)
- `M` = Megabytes (1 M = 1,000,000 bytes)
- `G` = Gigabytes (1 G = 1,000,000,000 bytes)

---

### 10. Security Context

```json
"securityContext": {}
```

Leave empty `{}` for default security settings, or configure:

```json
"securityContext": {
  "runAsUser": 1000,
  "runAsGroup": 1000,
  "fsGroup": 1000,
  "runAsNonRoot": true
}
```

| Field | Description |
|-------|-------------|
| `runAsUser` | User ID to run containers as |
| `runAsGroup` | Group ID to run containers as |
| `fsGroup` | Group ID for volume ownership |
| `runAsNonRoot` | Prevent running as root |

---

### 11. Output Settings

```json
"output": {
  "base64ConfigFile": "base64_config.txt"
}
```

| Field | Description |
|-------|-------------|
| `base64ConfigFile` | Filename for the generated base64-encoded configuration |

**Tip:** Use different filenames for different namespaces:
- `base64_config_faas.txt`
- `base64_config_dev.txt`
- `base64_config_prod.txt`

---

## Running the Script

### Basic Usage

```bash
# Using default config.json in the same directory
python compute_setup.py

# Using a specific config file
python compute_setup.py --config configs/config-faas.json

# Short form
python compute_setup.py -c configs/config-prod.json
```

### What the Script Does

1. **Loads** your configuration file
2. **Validates** required fields
3. **Encodes** the configuration to Base64
4. **Creates** the compute in Dataloop
5. **Sets** it as the default driver for your organization

---

## Multiple Namespaces

To manage multiple namespaces, create separate config files:

```
configs/
├── config-template.json   # Template (don't edit)
├── config-dev.json        # Development namespace
├── config-staging.json    # Staging namespace
├── config-prod.json       # Production namespace
└── config-gpu.json        # GPU workloads namespace
```

Run for each namespace:
```bash
python compute_setup.py --config configs/config-dev.json
python compute_setup.py --config configs/config-prod.json
```

---

## Troubleshooting

### Common Errors

| Error | Cause | Solution |
|-------|-------|----------|
| `Missing required values: organization.orgId` | Organization ID not set | Add your org ID from Dataloop console |
| `cluster.endpoint must start with http://` | Invalid endpoint URL | Ensure URL starts with `https://` |
| `Config file not found` | Wrong file path | Check the file path and try again |
| `Invalid JSON` | Syntax error in config | Validate JSON at jsonlint.com |

### Validation Checklist

Before running the script, verify:

- [ ] `orgId` is a valid UUID from Dataloop
- [ ] `endpoint` starts with `https://`
- [ ] `token` is a valid JWT (starts with `eyJ`)
- [ ] `ca` is base64-encoded (if required)
- [ ] `defaultNamespace` exists in your cluster
- [ ] `serviceAccountName` exists in the namespace
- If you omit `cluster.serviceAccountName`, it defaults to `faas`.
- [ ] JSON syntax is valid (no trailing commas)

### Getting Help

1. Check this documentation
2. Validate your JSON at [jsonlint.com](https://jsonlint.com)
3. Verify Kubernetes access: `kubectl cluster-info`
4. Check service account: `kubectl get sa -n <namespace>`

---

## Example Complete Configuration

```json
{
  "organization": {
    "orgId": "12345678-1234-1234-1234-123456789abc",
    "env": "rc"
  },
  "cluster": {
    "name": "acme-faas-aws-useast1",
    "endpoint": "https://ABC123.gr7.us-east-1.eks.amazonaws.com",
    "kubernetesVersion": "1.29",
    "provider": "aws",
    "defaultNamespace": "faas"
  },
  "authentication": {
    "ca": "LS0tLS1CRUdJTi...",
    "token": "eyJhbGciOiJSUzI1NiIs..."
  },
  "registry": {
    "domain": "hub.dataloop.ai",
    "faasFolder": "customerhub",
    "bootstrapFolder": "customerhub"
  },
  "network": {
    "internalRequestsUrl": null,
    "environmentVariables": []
  },
  "volumes": [],
  "plugins": [
    {"name": "monitoring"},
    {"name": "scaler"}
  ],
  "nodePools": [
    {
      "name": "general-pool",
      "isDlTypeDefault": true,
      "dlTypes": ["regular-xs", "regular-s", "regular-m"],
      "tolerations": [],
      "description": "Default CPU pool",
      "nodeSelector": {},
      "preemptible": false
    }
  ],
  "defaultResources": {
    "requests": {"cpu": "100m", "memory": "256Mi"},
    "limits": {"cpu": "2", "memory": "4Gi"}
  },
  "securityContext": {},
  "output": {
    "base64ConfigFile": "base64_config.txt"
  }
}
```

