#!/usr/bin/env python3
"""
compute_setup.py
----------------
Script to create and configure Dataloop compute from a Kubernetes cluster.

This script:
1. Loads configuration from a JSON config file
2. Builds and validates the cluster configuration
3. Encodes it to Base64 and saves to file
4. Creates a Dataloop compute using the dtlpy SDK
5. Sets the compute as the default driver for your organization

Usage Examples:
    # Using default config.json in the same directory
    python compute_setup.py

    # Using a specific namespace config file
    python compute_setup.py --config configs/config-faas.json
    python compute_setup.py --config configs/config-prod.json
    python compute_setup.py -c configs/config-dev.json

    # List available config files
    python compute_setup.py --list

For detailed configuration help, see README.md
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List

import dtlpy as dl
import pkg_resources

# Script directory and default paths
SCRIPT_DIR = Path(__file__).parent
DEFAULT_CONFIG_FILE = SCRIPT_DIR / "config.json"
CONFIGS_DIR = SCRIPT_DIR / "configs"

MIN_DTLpy_VERSION = "1.115.44"


def validate_dtlpy_version() -> None:
    """Fail fast if the installed dtlpy SDK is older than required."""
    current = getattr(dl, "__version__", "0.0.0")
    if pkg_resources.parse_version(current) < pkg_resources.parse_version(MIN_DTLpy_VERSION):
        raise RuntimeError(
            f"dtlpy SDK version {current} is too old. "
            f"Minimum required version is {MIN_DTLpy_VERSION}. "
            f"Please upgrade: pip install \"dtlpy>={MIN_DTLpy_VERSION}\""
        )


def list_available_configs() -> List[Path]:
    """List all available config files in the configs directory."""
    configs = []
    
    # Check main config.json
    if DEFAULT_CONFIG_FILE.exists():
        configs.append(DEFAULT_CONFIG_FILE)
    
    # Check configs directory
    if CONFIGS_DIR.exists():
        for config_file in sorted(CONFIGS_DIR.glob("config-*.json")):
            if "template" not in config_file.name:
                configs.append(config_file)
    
    return configs


def print_available_configs() -> None:
    """Print available configuration files."""
    configs = list_available_configs()
    
    print("\n📁 Available Configuration Files:")
    print("=" * 50)
    
    if not configs:
        print("  No config files found.")
        print(f"\n  Create a config file in: {CONFIGS_DIR}/")
        print("  Or copy the template: configs/config-template.json")
        return
    
    for config_path in configs:
        try:
            with open(config_path, "r") as f:
                cfg = json.load(f)
            namespace = cfg.get("cluster", {}).get("defaultNamespace", "unknown")
            cluster_name = cfg.get("cluster", {}).get("name", "unknown")
            env = cfg.get("organization", {}).get("env", "unknown")
            
            print(f"\n  📄 {config_path.relative_to(SCRIPT_DIR)}")
            print(f"     Cluster: {cluster_name}")
            print(f"     Namespace: {namespace}")
            print(f"     Environment: {env}")
        except (json.JSONDecodeError, KeyError):
            print(f"\n  📄 {config_path.relative_to(SCRIPT_DIR)} (invalid or incomplete)")
    
    print("\n" + "=" * 50)
    print("\nUsage:")
    print(f"  python {Path(__file__).name} --config <config-file>")
    print(f"\nExample:")
    if configs:
        example = configs[0].relative_to(SCRIPT_DIR)
        print(f"  python {Path(__file__).name} --config {example}")


def load_config(config_path: str) -> Dict[str, Any]:
    """Load configuration from JSON file."""
    with open(config_path, "r") as f:
        return json.load(f)


def build_compute_config(cfg: Dict[str, Any]) -> Dict[str, Any]:
    """Build the compute configuration dictionary from loaded config."""
    cluster = cfg["cluster"]
    auth = cfg["authentication"]
    registry = cfg.get("registry") or {}
    network = cfg["network"]
    metadata = cfg.get("metadata") or {}

    registry_domain = registry.get("domain", "hub.dataloop.ai")
    registry_faas_folder = registry.get("faasFolder", "customerhub")
    registry_bootstrap_folder = registry.get("bootstrapFolder", "customerhub")

    config: Dict[str, Any] = {
        "authentication": {
            "ca": auth.get("ca", ""),
            "token": auth["token"],
        },
        "config": {
            "endpoint": cluster["endpoint"],
            "kubernetesVersion": cluster["kubernetesVersion"],
            "name": cluster["name"],
            "nodePools": cfg["nodePools"],
            "metadata": metadata,
            "settings": {"defaultNamespace": cluster["defaultNamespace"]},
            "deploymentConfiguration": {
                "volumes": cfg.get("volumes", []),
                "serviceAccountName": cluster.get("serviceAccountName", "faas"),
                "securityContext": cfg.get("securityContext", {}),
                "registry": {
                    "domain": registry_domain,
                    "faasFolder": registry_faas_folder,
                    "bootstrapFolder": registry_bootstrap_folder,
                },
                "defaultResources": cfg.get("defaultResources", {}),
                "internalRequestsUrl": network.get("internalRequestsUrl"),
                "environmentVariables": network.get("environmentVariables", []),
            },
            "plugins": cfg.get("plugins", []),
            "provider": cluster["provider"],
        },
    }
    return config


def validate_config(cfg: Dict[str, Any], compute_cfg: Dict[str, Any]) -> None:
    """Validate that required fields are present and correctly formatted."""
    auth = compute_cfg.get("authentication", {})
    conf = compute_cfg.get("config", {})
    org_id = cfg.get("organization", {}).get("orgId", "")

    missing = []
    if not auth.get("token"):
        missing.append("authentication.token")
    if not conf.get("endpoint"):
        missing.append("cluster.endpoint")
    if not org_id or org_id in ("{{org-id}}", "<REPLACE: Your Dataloop Organization ID>", "YOUR_ORG_ID_HERE"):
        missing.append("organization.orgId")

    if missing:
        raise ValueError(
            "Missing required values in config file:\n  - "
            + "\n  - ".join(missing)
            + "\n\nPlease edit your config file and re-run."
            + "\nSee README.md for detailed instructions."
        )

    # Validate endpoint format
    endpoint: str = conf["endpoint"]
    if not (endpoint.startswith("http://") or endpoint.startswith("https://")):
        raise ValueError("cluster.endpoint must start with http:// or https://")

    # Warnings for optional but recommended fields
    if not auth.get("ca"):
        print("⚠️  Warning: authentication.ca is empty. Set it if your cluster requires a CA certificate.")
    if not conf.get("deploymentConfiguration", {}).get("volumes"):
        print("⚠️  Warning: No volumes defined. Add volumes if your workloads need storage.")

    # Validate metadata (optional)
    if "metadata" in cfg and cfg.get("metadata") is not None and not isinstance(cfg.get("metadata"), dict):
        raise ValueError("metadata must be an object (JSON dict) when provided")

    metadata = cfg.get("metadata") or {}
    serve_agent_service_type = metadata.get("serveAgentServiceType")
    if serve_agent_service_type is not None:
        allowed_service_types = {"ClusterIP", "LoadBalancer"}
        if serve_agent_service_type not in allowed_service_types:
            raise ValueError(
                "Invalid metadata.serveAgentServiceType: "
                f"{serve_agent_service_type}. Allowed values: {sorted(allowed_service_types)}"
            )

    # Validate mandatory plugins
    plugins = cfg.get("plugins", [])
    plugin_names = {p.get("name") for p in plugins if isinstance(p, dict)}
    mandatory_plugins = {"monitoring", "scaler"}
    missing_plugins = sorted(mandatory_plugins - plugin_names)
    if missing_plugins:
        raise ValueError(
            "Missing mandatory plugins in config file:\n  - "
            + "\n  - ".join(f"plugins: {name}" for name in missing_plugins)
            + "\n\nPlease add them under the top-level 'plugins' array."
            + "\nSee README.md → Plugins for examples."
        )

    # Validate nodePools.dlTypes values
    allowed_dl_types = {
        "regular-xs", "regular-s", "regular-m", "regular-l",
        "highmem-xs", "highmem-s", "highmem-m", "highmem-l",
        "gpu-t4", "gpu-t4-m",
        "gpu-a100-s", "gpu-a100-4g", "gpu-a100-4g-m",
    }
    invalid_dl_types_by_pool: List[str] = []
    for idx, pool in enumerate(cfg.get("nodePools", [])):
        if not isinstance(pool, dict):
            continue
        pool_name = pool.get("name") or f"nodePools[{idx}]"
        dl_types = pool.get("dlTypes", [])
        if not isinstance(dl_types, list):
            invalid_dl_types_by_pool.append(f"{pool_name}: dlTypes must be an array")
            continue
        invalid = [t for t in dl_types if not isinstance(t, str) or t not in allowed_dl_types]
        if invalid:
            invalid_dl_types_by_pool.append(f"{pool_name}: invalid dlTypes: {invalid}")

    if invalid_dl_types_by_pool:
        allowed_list = ", ".join(sorted(allowed_dl_types))
        raise ValueError(
            "Invalid nodePools.dlTypes values:\n  - "
            + "\n  - ".join(invalid_dl_types_by_pool)
            + "\n\nAllowed values:\n  - "
            + allowed_list
            + "\n\nSee README.md → Node Pools for examples."
        )


def encode_config_to_base64(compute_cfg: Dict[str, Any], output_file: str) -> str:
    """Encode configuration to Base64 and save to file."""
    json_str = json.dumps(compute_cfg, indent=2)
    b64 = base64.b64encode(json_str.encode("utf-8")).decode("utf-8")
    with open(output_file, "w") as f:
        f.write(b64)
    return b64


def create_compute(config_file_path: str, org_id: str):
    """Create compute via Dataloop SDK from a Base64-encoded config file."""
    print("⏳ Creating compute...")
    compute = dl.computes.create_from_config_file(
        config_file_path=config_file_path,
        org_id=org_id
    )
    print(f"✅ Compute created: {getattr(compute, 'name', '<unknown>')}")
    return compute


def set_default_driver(compute_name: str, org_id: str, update_existing_services: bool = False) -> None:
    """Set the created compute as the default driver for the organization."""
    print("⏳ Setting compute as default driver...")
    dl.service_drivers.set_default(
        service_driver_id=compute_name,
        org_id=org_id,
        update_existing_services=update_existing_services,
    )
    print("🎉 Compute has been successfully set as default driver.")


def main(config_path: str) -> None:
    """Main execution flow."""
    validate_dtlpy_version()

    # Load configuration
    print(f"\n📂 Loading configuration from: {config_path}")
    cfg = load_config(config_path)

    org = cfg["organization"]
    org_id = org["orgId"]
    dataloop_env = org.get("env", "rc")
    output_file = cfg.get("output", {}).get("base64ConfigFile", "base64_config.txt")
    cluster_name = cfg.get("cluster", {}).get("name", "unknown")
    namespace = cfg.get("cluster", {}).get("defaultNamespace", "unknown")

    # Print configuration summary
    print("\n" + "=" * 50)
    print("📋 Configuration Summary")
    print("=" * 50)
    print(f"  Cluster:    {cluster_name}")
    print(f"  Namespace:  {namespace}")
    print(f"  Provider:   {cfg.get('cluster', {}).get('provider', 'unknown')}")
    print(f"  Environment: {dataloop_env}")
    print("=" * 50)

    # Set Dataloop environment
    dl.setenv(dataloop_env)
    print(f"\n📦 Dataloop SDK version: {dl.__version__}")

    # Build compute configuration
    print("\n📋 Building configuration...")
    compute_cfg = build_compute_config(cfg)

    # Validate configuration
    print("🔍 Validating configuration...")
    validate_config(cfg, compute_cfg)

    # Encode and save to file
    print(f"\n💾 Encoding configuration to {output_file}...")
    b64 = encode_config_to_base64(compute_cfg, output_file)
    print(f"✅ Base64 config saved (length={len(b64)} chars)")

    # Create compute
    print("\n🚀 Creating Dataloop compute...")
    compute = create_compute(output_file, org_id)

    # Set as default driver
    print("\n⚙️  Configuring default driver...")
    set_default_driver(
        compute_name=getattr(compute, "name", ""),
        org_id=org_id,
        update_existing_services=False
    )

    print("\n" + "=" * 50)
    print("✅ Setup completed successfully!")
    print(f"   Cluster: {cluster_name}")
    print(f"   Namespace: {namespace}")
    print("=" * 50)


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Create and configure Dataloop compute from a Kubernetes cluster.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s                                    # Use default config.json
  %(prog)s --config configs/config-faas.json  # Use specific config file
  %(prog)s -c configs/config-prod.json        # Short form
  %(prog)s --list                             # List available configs

For detailed configuration help, see README.md
        """
    )
    
    parser.add_argument(
        "--config", "-c",
        type=str,
        default=str(DEFAULT_CONFIG_FILE),
        metavar="FILE",
        help="Path to JSON config file (default: config.json)"
    )
    
    parser.add_argument(
        "--list", "-l",
        action="store_true",
        help="List all available configuration files"
    )
    
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    
    # Handle --list flag
    if args.list:
        print_available_configs()
        sys.exit(0)
    
    # Run main setup
    try:
        main(args.config)
    except FileNotFoundError as e:
        print(f"\n❌ Config file not found: {e.filename}")
        print("\nAvailable options:")
        print(f"  1. Create {DEFAULT_CONFIG_FILE}")
        print(f"  2. Copy template: cp configs/config-template.json configs/config-myenv.json")
        print(f"  3. Specify existing file: python {Path(__file__).name} --config <path>")
        print(f"\nRun with --list to see available config files")
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"\n❌ Invalid JSON in config file: {e}")
        print("\nTip: Validate your JSON at https://jsonlint.com")
        sys.exit(1)
    except ValueError as e:
        print(f"\n❌ Configuration Error:\n{e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        print("\n📝 Troubleshooting tips:")
        print("  • Ensure organization.orgId is set and valid")
        print("  • Ensure cluster.endpoint is a valid HTTPS URL")
        print("  • Ensure authentication.token is provided")
        print("  • Verify network/proxy settings if required")
        print("  • See README.md for detailed help")
        raise
