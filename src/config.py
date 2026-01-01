"""Configuration loading for Lavender Ledger."""

import os
from pathlib import Path

import yaml


class ConfigError(Exception):
    """Configuration error."""

    pass


def load_config(config_path: Path = None) -> dict:
    """Load configuration from YAML file.

    Args:
        config_path: Path to config file. Defaults to config.yaml in project root.

    Returns:
        Configuration dictionary with expanded paths.

    Raises:
        ConfigError: If config file is missing or invalid.
    """
    if config_path is None:
        # Look for config.yaml in project root
        project_root = Path(__file__).parent.parent
        config_path = project_root / "config.yaml"

    if not config_path.exists():
        raise ConfigError(
            f"Configuration file not found: {config_path}\n"
            f"Please copy config.example.yaml to config.yaml and customize it."
        )

    with open(config_path) as f:
        config = yaml.safe_load(f)

    # Get project root for resolving relative paths
    project_root = Path(__file__).parent.parent

    # Expand ~ in data_directory and resolve relative paths
    data_dir_raw = config["data_directory"]
    data_dir_raw = os.path.expanduser(data_dir_raw)

    # If relative path, resolve relative to project root
    if not os.path.isabs(data_dir_raw):
        data_dir = str((project_root / data_dir_raw).resolve())
    else:
        data_dir = data_dir_raw

    config["data_directory"] = data_dir

    # Expand ${data_directory} in paths
    config["database_path"] = config["database_path"].replace(
        "${data_directory}", data_dir
    )

    for key in ["staging_path", "archive_path"]:
        config["statements"][key] = config["statements"][key].replace(
            "${data_directory}", data_dir
        )

    # Ensure directories exist
    Path(config["statements"]["staging_path"]).mkdir(parents=True, exist_ok=True)
    Path(config["statements"]["archive_path"]).mkdir(parents=True, exist_ok=True)

    return config


def get_config() -> dict:
    """Get the application configuration.

    This is the main entry point for getting config.
    Caches the config after first load.
    """
    if not hasattr(get_config, "_config"):
        get_config._config = load_config()
    return get_config._config
