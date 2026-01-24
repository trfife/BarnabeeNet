#!/bin/bash
# Persistent SSH tunnel for Ollama access from VM
# Run this in the background: nohup ./ollama-tunnel.sh &

while true; do
    echo "$(date): Starting SSH tunnel to VM for Ollama..."
    ssh -N -R 11434:localhost:11434 thom@192.168.86.51
    echo "$(date): Tunnel closed, reconnecting in 5s..."
    sleep 5
done
