#!/bin/bash
read -s -p "BPM password: " BPM_PASS
echo
export BPM_PASS
docker-compose "$@"
