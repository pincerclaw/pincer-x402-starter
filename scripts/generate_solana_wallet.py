#!/usr/bin/env python3
"""
快速生成 Solana 測試錢包
這個腳本會生成一個新的 Solana 錢包並顯示所有需要的資訊
"""

import base58  # type: ignore
from solders.keypair import Keypair

print("🔑 正在生成 Solana 測試錢包...")
print("=" * 60)

# 生成新的 keypair
keypair = Keypair()

# 獲取公鑰（地址）
address = str(keypair.pubkey())

# 獲取私鑰（Base58 格式）
private_key_bytes = bytes(keypair)
private_key_base58 = base58.b58encode(private_key_bytes).decode('ascii')

print("\n✅ 錢包已生成！\n")

print("📍 Solana 地址 (公鑰):")
print(f"   {address}\n")

print("🔐 私鑰 (Base58 格式):")
print(f"   {private_key_base58}\n")

print("=" * 60)
print("\n📝 複製以下內容到 .env 文件：\n")

print(f"SVM_ADDRESS={address}")
print(f"SVM_PRIVATE_KEY={private_key_base58}")
print(f"TREASURY_SVM_ADDRESS={address}")
print(f"TREASURY_SVM_PRIVATE_KEY={private_key_base58}")

print("\n" + "=" * 60)
print("\n🪙 下一步：獲取測試 SOL")
print("   訪問: https://faucet.solana.com/")
print(f"   輸入你的地址: {address}")
print("   點擊 'Request Airdrop' 獲取 1-2 SOL\n")

print("✅ 完成後運行: uv run python scripts/init_ledger.py")
print("=" * 60)
