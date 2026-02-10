"""
Simple Pincer SDK Example.

This script demonstrates how to import and initialize the Pincer SDK client.
It assumes you have a local Pincer server running (e.g. via `docker compose up`).
"""
import asyncio

from pincer_sdk import PincerClient


async def main():
    print("🚀 Initializing Pincer SDK Client...")
    
    # Initialize the client pointing to your Pincer service
    # Default is http://localhost:8000
    try:
        async with PincerClient(base_url="http://localhost:8000") as client:
            print(f"✅ Successfully initialized client: {client}")
            print("   The SDK is correctly installed and ready to use!")
            
            # Example: Check service health (if implemented) or just print config
            print(f"   Base URL: {client.base_url}")
            
    except Exception as e:
        print(f"❌ Error initializing client: {e}")
        print("   Make sure the Pincer service is running if you try to make requests.")

if __name__ == "__main__":
    asyncio.run(main())

