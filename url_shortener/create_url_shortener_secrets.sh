#!/bin/bash
kubectl create secret generic url-shortener-config --from-literal=sheet_key=$1
