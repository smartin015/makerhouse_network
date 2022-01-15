#!/bin/bash

echo "Ensure usage: create_secrets.sh <user> <pass>"
read

kubectl create secret generic ddns-hover-secret \
  --from-literal=username=$1 \
  --from-literal=password=$2

