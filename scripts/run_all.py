#!/usr/bin/env python3
import os
import subprocess
import time


def run_service(name, cmd, env=None):
    print(f"🚀 Starting {name}...")
    my_env = os.environ.copy()
    if env:
        my_env.update(env)
    return subprocess.Popen(cmd, env=my_env)

def main():
    services = []
    try:
        # 1. Start Pincer Faciltator
        services.append(run_service("Pincer Facilitator", ["uv", "run", "python", "src/pincer/server.py"]))
        
        # 2. Wait for Facilitator to start
        time.sleep(2)
        
        # 3. Start Resource Server
        services.append(run_service("Resource Server", ["uv", "run", "python", "src/resource/server.py"]))
        
        # 4. Start Merchant Server
        services.append(run_service("Merchant Server", ["uv", "run", "python", "src/merchant/server.py"]))
        
        print("\n✅ All services started. Press Ctrl+C to stop all.\n")
        
        while True:
            time.sleep(1)
            
    except KeyboardInterrupt:
        print("\n🛑 Stopping all services...")
        for s in services:
            s.terminate()
        for s in services:
            s.wait()
        print("Done.")

if __name__ == "__main__":
    main()
