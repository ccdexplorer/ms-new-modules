#!/bin/bash

# Start docker daemon
service docker start

# Wait for docker to be ready
timeout=30
while ! docker info >/dev/null 2>&1; do
    timeout=$((timeout-1))
    if [ $timeout -eq 0 ]; then
        echo "Docker daemon failed to start"
        exit 1
    fi
    sleep 1
done

echo "Docker daemon started"

# Run the python script
python3 /home/code/main.py