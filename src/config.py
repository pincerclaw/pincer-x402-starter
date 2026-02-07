"""Centralized configuration management for Pincer x402 demo.

Loads all configuration from environment variables with sensible defaults.
"""

import os
from typing import Literal

from dotenv import load_dotenv
from pydantic import Field
from pydantic_settings import BaseSettings

# Load environment variables from .env file
load_dotenv()


class Config(BaseSettings):
    """Main configuration class for all services."""

    # Network Configuration
    evm_network: str = Field(default="eip155:84532", description="Base Sepolia")
    evm_address: str = Field(default="", description="EVM wallet address")
    evm_private_key: str = Field(default="", description="EVM private key")

    svm_network: str = Field(
        default="solana:EtWTRABZaYq6iMfeYKouRu166VU2xqa1", description="Solana Devnet"
    )
    svm_address: str = Field(default="", description="Solana wallet address")
    svm_private_key: str = Field(default="", description="Solana private key")
    solana_rpc_url: str = Field(default="https://api.devnet.solana.com", description="Solana RPC endpoint")

    # EVM RPC URL
    evm_rpc_url: str = Field(default="https://sepolia.base.org", description="EVM RPC endpoint")

    # Pincer Treasury Configuration
    treasury_evm_address: str = Field(default="", description="Treasury EVM address")
    treasury_evm_private_key: str = Field(default="", description="Treasury EVM private key")
    treasury_svm_address: str = Field(default="", description="Treasury Solana address")
    treasury_svm_private_key: str = Field(default="", description="Treasury Solana private key")

    # Service URLs and Ports
    resource_host: str = Field(default="0.0.0.0")
    resource_port: int = Field(default=4021)
    resource_url: str = Field(default="http://localhost:4021")

    pincer_host: str = Field(default="0.0.0.0")
    pincer_port: int = Field(default=4022)
    pincer_url: str = Field(default="http://localhost:4022")

    merchant_host: str = Field(default="0.0.0.0")
    merchant_port: int = Field(default=4023)
    merchant_url: str = Field(default="http://localhost:4023")



    # Webhook Security
    webhook_secret: str = Field(
        default="change_me_in_production",
        description="Shared secret for HMAC webhook signatures",
    )

    # Database
    database_path: str = Field(default="./pincer.db")

    # Logging
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = Field(default="INFO")
    log_format: Literal["json", "text"] = Field(default="json")

    # Payment Configuration
    content_price_usd: float = Field(default=0.10, description="Price for paywalled content")

    # USDC Token Addresses
    evm_usdc_address: str = Field(
        default="0x036CbD53842c5426634e7929541eC2318f3dCF7e",
        description="Base Sepolia USDC address",
    )

    # Sponsor Campaign Configuration (JSON source)
    sponsor_data_path: str = Field(default="src/data/campaigns.json")

    class Config:
        env_file = ".env"
        case_sensitive = False


# Global config instance
config = Config()


def validate_config_for_service(service: Literal["resource", "pincer", "merchant", "agent"]) -> None:
    """Validate that required configuration is present for a specific service.

    Args:
        service: The service name to validate configuration for.

    Raises:
        ValueError: If required configuration is missing.
    """
    errors = []

    if service in ["resource", "agent"]:
        if not config.evm_address and not config.svm_address:
            errors.append("Either EVM_ADDRESS or SVM_ADDRESS must be set")
        if not config.evm_private_key and not config.svm_private_key:
            errors.append("Either EVM_PRIVATE_KEY or SVM_PRIVATE_KEY must be set")

    if service == "pincer":
        if not config.treasury_evm_address and not config.treasury_svm_address:
            errors.append(
                "Either TREASURY_EVM_ADDRESS or TREASURY_SVM_ADDRESS must be set for Pincer service"
            )
        if not config.treasury_evm_private_key and not config.treasury_svm_private_key:
            errors.append(
                "Either TREASURY_EVM_PRIVATE_KEY or TREASURY_SVM_PRIVATE_KEY must be set for Pincer service"
            )

    if errors:
        error_msg = f"Configuration errors for {service} service:\n" + "\n".join(f"  - {e}" for e in errors)
        raise ValueError(error_msg)
