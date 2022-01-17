# Troubleshooting

## Prometheus

If prometheus runs out of space, the "prometheus-prometheus-kube-prometheus-prometheus-0" job will crashloop forever with an obscure stack trace. Resizing the volume that prometheus uses is somewhat tricky:

1. go to 192.168.0.4 (the longhorn web ui) to assess how much storage you can assign.
2. `kubectl edit deployment prometheus-kube-prometheus-operator`
    * Set "replicas" to 0. The operator automatically updates other prometheus entities in kubernetes, so if it's running you can't edit replicasets etc. without them immediately being reverted.
3. `kubectl edit statefulset prometheus-prometheus-kube-prometheus-prometheus`
    * Set "replicas" to 0. This generates the pod which binds to the data volume. Longhorn storage *must* be unbound before it can be resized.
4. `vim ~/makerhouse/k3s/k3s-prometheus-stack-values.yaml` 
    * Under prometheus.prometheusSpec.storageSpec.volumeClaimTemplate.spec.resources.requests.storage, change to e.g. "50Gi"
5. `helm upgrade prometheus prometheus-community/kube-prometheus-stack --values k3s-prometheus-stack-values.yaml`
    * Longhorn should indicate the volume is being resized. You can also check with `kubectl describe pvc prometheus-prometheus-prometheus-kube-prometheus-prometheus-0` and look for an event like "External resizer is resizing volume pvc-9da184ed-28f9-48d1-82ea-3e0c0a93cf1d"
    * If the status of the pvc is still "Bound", run `kubectl get pods | grep prometheus` to see whether the prometheus operator or the main prometheus pod is still running for some reason. It should be deletable with `kubectl delete pod &lt;foo>` if the deployment and statefulset are both set to 0 replicas. 

If you want to delete unneeded metrics:

* `curl -X POST -g 'http://localhost:9090/api/v1/admin/tsdb/delete_series?match[]=a_bad_metric&match[]={region="mistake"}'`
    * See [https://www.robustperception.io/deleting-time-series-from-prometheus](https://www.robustperception.io/deleting-time-series-from-prometheus) 
* `curl -X POST -g 'http://prometheus:9090/api/v1/admin/tsdb/delete_series?match[]={instance="192.168.1.5:6443"}'`
    * Deletes all metrics for a particular target/instance. 
* `curl -X POST -g [http://prometheus:9090/api/v1/admin/tsdb/clean_tombstones](http://prometheus:9090/api/v1/admin/tsdb/clean_tombstones)`
    * Do this to actually garbage collect the data - note that this may grow the used disk size (up to 2X if you're deleting most things!) before it shrinks it
