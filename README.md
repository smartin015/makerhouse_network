# makerhouse_network

Public scripts, services, and configuration for running a smart home K3S network cluster

![image1](https://user-images.githubusercontent.com/607666/149633433-d87defd0-4143-4bab-8256-fe7ab35c6d46.png)

## Setup

Setting up a replicated pi cluster from scratch is an involved process consisting of several steps:

* Purchasing the hardware
* Flashing the OS
* Installing K3S and linking the nodes together
* Configuring the load balancer and reverse proxy
* Installing a distributed storage solution
* Setting up SSL certificate handling and dynamic DNS
* Deploying an image registry for custom container images
* Setting up monitoring/alerting and IoT messaging

There are knowledge prerequisites for following this guide:

* Some basic networking (e.g. how to find a remote device's IP address and SSH into it)
* Linux command line fundamentals (navigating to files, opening and editing them, and running commands)

Even if you have advanced knowledge of kubernetes, be prepared to spend several hours on initial setup, plus an hour or two here and there to further refine it.

## Purchasing the Hardware

For the cluster network, you will need:

* An ethernet switch (preferably gigabit) with as many ports as the number of nodes in your cluster, plus one.
* A power supply for your switch
* An ethernet cable running to whatever existing network you have.

For each node, you will need:

* A raspberry pi 4 (or better)
* A USB C power supply (5V with at least 2A)
* A short ethernet cable (to connect the pi to the network switch)

For sufficient storage, you will need (per node):

* A USB 3 NVMe M.2 SSD enclosure https://www.amazon.com/gp/product/B07MNFH1PX
* An NVMe M.2 SSD (I picked [this 256GB one](https://www.amazon.com/gp/product/B07ZGK3K4V))

Before continuing on:

1. connect your switch to power and the LAN
2. connect each raspberry pi via ethernet to the switch (whichever port doesn't matter)
3. Install an SSD into each enclosure, then plug one enclosures into one of the blue USB ports on each raspberry pi
   * At this point, it helps to label the SSDs with the name you expect each node to be, e.g. `k3s1`, `k3s2` etc. to keep track of where the image 'lives'.

### A note on earlier versions of raspbery pi:

Try to avoid using raspberry pi's earlier than the pi 4. To check for compatibility, run:

```
uname -a
```

If the output contains armv6l then kubernetes does not support the device. There are precompiled k8s binaries for armv6l which you could get, but you’d have to compile manually. [This issue](https://github.com/kubernetes/kubeadm/issues/253) describes that kubernetes support for armv6l has been dropped.

A comment at the end of that issue links to compiled binaries for armv6l:

[https://github.com/aojea/kubernetes-raspi-binaries](https://github.com/aojea/kubernetes-raspi-binaries)

### Setup SSD boot

Follow [these instructions](https://www.tomshardware.com/how-to/boot-raspberry-pi-4-usb) to install a USB bootloader onto each raspberry pi. Stop when you get to step 9 (inserting the Raspberry Pi OS) as we'll be installing Ubuntu instead.

## Flashing the OS

Use https://www.balena.io/etcher/ or similar to write an [Ubuntu 20.04 ARM 64-bit LTS image ](https://ubuntu.com/download/server/arm) to one of the SSDs. We'll do the majority of setup on this drive, then clone it to the other pi's (with some changes).

Unplug and re-plug the SSD, then navigate to the `boot` partition and ensure there's a file labeled `ssh` there (if not, create a blank one). This allows us to remote in to the raspi's.

### Enable cgroups

[cgroups](https://en.wikipedia.org/wiki/Cgroups) are used by k3s to manage the resources of processes that are running on the cluster. 

Append to /boot/firmware/cmdline.txt (see [here](https://askubuntu.com/questions/1237813/enabling-memory-cgroup-in-ubuntu-20-04)):

`cgroup_enable=memory cgroup_memory=1`

Example of a correct config:

```
ubuntu@k3s1:~$ cat /boot/firmware/cmdline.txt 
net.ifnames=0 dwc_otg.lpm_enable=0 console=serial0,115200 console=tty1 root=LABEL=writable rootfstype=ext4 elevator=deadline rootwait fixrtc cgroup_enable=memory cgroup_memory=1
```

### Verify installation

Plug in the SSD, then plug in power to your raspberry pi. Look on your router to find the IP address of the raspberry pi, 

You should be able to SSH into it 

### Clone to other pi's

Use your software of choice (e.g. `gparted` for linux) to clone the SSD onto the other blank SSDs. For each SSD, mount it and  TODO

### On all devices (systemd or openrc)

#### For server nodes

Run the install script from get.k3s.io:

[https://rancher.com/docs/k3s/latest/en/installation/install-options/](https://rancher.com/docs/k3s/latest/en/installation/install-options/)

K3S version included for repeatability

```
export INSTALL_K3S_VERSION=v1.19.7+k3s1
curl -sfL https://get.k3s.io | sh -s - --disable servicelb --disable local-storage
```

ServiceLB and local storage are disabled to make way for MetalLB and Longhorn (distributed storage)

#### For worker nodes

To install on worker nodes and add them to the cluster, run the installation script with the K3S_URL and K3S_TOKEN environment variables. Note use of raw IP - this is to remove dependency on Pihole serving DNS requests, since that service will itself be hosted on k3s.

Token can be recovered on the master at /var/lib/rancher/k3s/server/node-token

```
export K3S_URL=https://192.168.1.5:6443 
export INSTALL_K3S_VERSION=v1.19.7+k3s1
export K3S_TOKEN=mynodetoken
curl -sfL https://get.k3s.io | sh -
```

Where K3S_URL is the URL and port of a k3s server, and K3S_TOKEN comes from `/var/lib/rancher/k3s/server/node-token` on the server node

That should be it! You can confirm the node successfully joined the cluster by running

`kubectl get nodes`

## Set Up Access

Grab the kubeconfig file from the server node(s) onto whatever node you want to do k8s stuff from and stick it in ~/.kube/config.

```
scp ubuntu@192.168.1.5:/etc/rancher/k3s/k3s.yaml ~/.kube/config
```

(TODO manage kubeconfigs for [multiple clusters](https://kubernetes.io/docs/concepts/configuration/organize-cluster-access-kubeconfig/#supporting-multiple-clusters-users-and-authentication-mechanisms))

You may need to update the IP/address of the cluster master node in the kubeconfig file, since from the server node’s perspective it’s running on localhost.

## Distributed storage

_Note: these solutions require an arm64 architecture, NOT armhf/armv7l which is the default for Raspbian / Raspberry PI OS._

* Recommended software from Rancher: Longhorn. Followed [installation guide](https://rancher.com/docs/k3s/latest/en/storage/)
    * Note: need to set it as the default storage class, or else certain helm charts will fail to provision their persistent volumes:
    * kubectl patch storageclass longhorn -p '{"metadata": {"annotations":{"storageclass.kubernetes.io/is-default-class":"false"}}}'
* Longhorn UI is not exposed by default; you can expose it with [these instructions](https://longhorn.io/docs/1.0.0/deploy/accessing-the-ui/).

Note: alternative would be [Rook+Ceph](https://jflesch.kwain.net/blog/post/12/Raspberry-pi-K3s-Rook-Ceph ) - see also this [comparison list](https://rpi4cluster.com/k3s/k3s-storage-setting/)

## MetalLB load balancing / endpoint handling

[https://metallb.universe.tf/installation/](https://metallb.universe.tf/installation/) 

* Note: instructions say to do `kubectl edit configmap -n kube-system kube-proxy` but there's no such config map in k3s. Continuing anyways...
* kubectl apply -f https://raw.githubusercontent.com/metallb/metallb/v0.9.5/manifests/namespace.yaml
* kubectl apply -f https://raw.githubusercontent.com/metallb/metallb/v0.9.5/manifests/metallb.yaml
* kubectl create secret generic -n metallb-system memberlist --from-literal=secretkey="$(openssl rand -base64 128)"
* kubectl apply -f metallb-configmap.yml 
    * See .../makerhouse/k3s/metallb-configmap.yml

Test whether metallb is working by starting an exposed service, then cleaning up after:

* kubectl apply -f lbtest.yaml
* kubectl describe service hello
    * Look for "IPAllocated" in event log
    * Visit 192.168.0.3 and confirm "Welcome to nginx!" is visible
* kubectl delete service hello
* kubectl delete deployment hello

## Traefik configuration

Generate dashboard password

* htpasswd -c passwd admin
* echo ./passwd
* get the part after the colon, before the trailing slash. That's $password

Update config (/var/lib/rancher/k3s/server/manifests/traefik.yaml, move to traefik-customized.yaml):

* ssl.insecureSkipVerify: true 
* metrics.serviceMonitor.enabled: true
* dashboard.enabled: true
* dashboard.serviceType: "LoadBalancer"
* dashboard.auth.basic.admin: $password
* loadBalancerIP: "192.168.0.2"
* logLevel: "debug"

Edit /etc/systemd/system/k3s.service and add "--disable traefik" to disable original traefik config

* sudo systemctl daemon-reload
* sudo service k3s restart

Test configuration:

* kubectl apply -f ingresstest.yaml
* kubectl get ingress
    * "hello   &lt;none>   i.mkr.house   192.168.0.2   80      2m2s"

Note: Attempts to query i.mkr.house internally lead to the router admin page. You'll need to use a mobile network to test external ingress properly. 

### Troubleshooting:

* `journalctl -u k3s` to view logs
* Remove `--disable traefik` from /etc/systemd/system/k3s.service and then `sudo systemctl daemon-reload && sudo service k3s restart`
* Totally re-added /var/lib/rancher/k3s/server/manifests/traefik.yaml, which I don't think is correct. 

TODO actually visit the enabled traefik dashboard, somehow

## SSL cert-manager

Followed [https://opensource.com/article/20/3/ssl-letsencrypt-k3s](https://opensource.com/article/20/3/ssl-letsencrypt-k3s), but substituted for arm64 packages (this tutorial assumes just "arm").

Note: need to have ports 80 and 443 forwarded to whatever address is given by `kubectl get ingress`, which is what Traefik is configured to use in /var/lib/rancher/k3s/server/manifests/traefik-customized.yaml (See "Traefik configuration" above)

* kubectl create namespace cert-manager
* curl -sL https://github.com/jetstack/cert-manager/releases/download/v0.11.0/cert-manager.yaml | sed -r 's/(image:.*):(v.*)$/\1-arm64:\2/g' > cert-manager-arm.yaml
* grep "image:" cert-manager-arm.yaml
* kubectl apply -f cert-manager-arm.yaml
* kubectl --namespace cert-manager get pods
* kubectl apply -f letsencrypt-issuer-prod.yaml
* kubectl apply -f ingresstest.yaml
    * including "annotations" and "tls" sections described [here](https://opensource.com/article/20/3/ssl-letsencrypt-k3s), "request a certificate for our website"
* kubectl get certificate
    * Should be "true", may take a couple seconds after init
    * If not, check if i.mkr.house resolves to the current house IP. May have to update Hover manually.
* kubectl describe certificate
    * Should say "Certificate issued successfully"
* Confirm behavior by going to [https://i.mkr.house](https://i.mkr.house) from external network

## Private Registry

For custom containers

[https://www.linuxtechi.com/setup-private-docker-registry-kubernetes/](https://www.linuxtechi.com/setup-private-docker-registry-kubernetes/) 

Htpasswd setup (following [these](https://carpie.net/articles/installing-docker-registry-on-k3s) instructions):

* sudo apt -y install apache2-utils
* htpasswd -Bc htpasswd registry_htpasswd
* kubectl create secret generic private-registry-htpasswd --from-file ./htpasswd
* kubectl describe secret private-registry-htpasswd
* Values:
    * user: registry_htpasswd
    * pass: "r,A!U9@p>N^(nW!Ja-~6~h"

Then start the deployment

* kubectl apply -f  private-registry.yml
    * Creates persistent volume (via Longhorn), deployment/pod and exposed service on 192.168.0.5. Also cert.
* Add to pihole DNS: "registry" and "registry.lan" mapping to that IP

Test registry ability:

* docker tag ubuntu:20.04 registry.mkr.house:443/ubuntu
* docker push registry.mkr.house:443/ubuntu

See what's in the registry:

* curl -X GET --basic -u registry_htpasswd https://registry.mkr.house:443/v2/_catalog | python -m json.tool

Push to, then pull image from registry

* docker login registry.mkr.house:443
    * (add username & password)
* docker tag ddns-lexicon registry.mkr.house:443/ddns-lexicon
* docker push registry.mkr.house:443/ddns-lexicon 
* docker pull registry.mkr.house:443/ddns-lexicon

Add the custom registry to each node, following [these instructions](https://rancher.com/docs/k3s/latest/en/installation/private-registry/#without-tls) (note: not TLS)

* ssh ubuntu@pi4
    * sudo vim /etc/rancher/k3s/registries.yaml

    ```
    mirrors:
      "registry.mkr.house:443":
        endpoint:
          - "https://registry.mkr.house:443"
    configs:
      "registry.mkr.house:443":
        auth:
          username: "registry_htpasswd"
          password: "r,A!U9@p>N^(nW!Ja-~6~h"
        tls:
          insecure_skip_verify: true
    ```

    * sudo service k3s restart
* scp ubuntu@pi4:/etc/rancher/k3s/registries.yaml .
* scp ./registries.yaml ubuntu@pi5:/home/ubuntu/ 
* ssh ubuntu@pi5
    * sudo mkdir -p /etc/rancher/k3s/
    * sudo mv registries.yaml /etc/rancher/k3s/
    * sudo service k3s-agent restart
* scp ./registries.yaml ubuntu@pi6:/home/ubuntu/ 
* ssh ubuntu@pi6
    * sudo mkdir -p /etc/rancher/k3s/
    * sudo mv registries.yaml /etc/rancher/k3s/
    * sudo service k3s-agent restart

## Prometheus monitoring & Grafana dashboarding

* helm repo add prometheus-community [https://prometheus-community.github.io/helm-charts](https://prometheus-community.github.io/helm-charts)
* helm upgrade --install prometheus prometheus-community/kube-prometheus-stack --values k3s-prometheus-stack-values.yaml
* To see what changes to the *values.yaml file make: helm upgrade **--dry-run** prometheus prometheus-community/kube-prometheus-stack --values k3s-prometheus-stack-values.yaml

Setting up additional scrape configs (for e.g. nodered custom metrics): [https://github.com/prometheus-operator/prometheus-operator/blob/master/Documentation/additional-scrape-config.md](https://github.com/prometheus-operator/prometheus-operator/blob/master/Documentation/additional-scrape-config.md) 

* kubectl create secret generic additional-scrape-configs --from-file=prometheus-additional.yaml --dry-run -oyaml > additional-scrape-configs.yaml
* kubectl apply -f additional-scrape-configs.yaml

If prometheus runs out of space, the "prometheus-prometheus-kube-prometheus-prometheus-0" job will crashloop forever with an obscure stack trace. Resizing the volume that prometheus uses is somewhat tricky:

* go to 192.168.0.4 (the longhorn web ui) to assess how much storage you can assign.
* `kubectl edit deployment prometheus-kube-prometheus-operator`
    * Set "replicas" to 0. The operator automatically updates other prometheus entities in kubernetes, so if it's running you can't edit replicasets etc. without them immediately being reverted.
* `kubectl edit statefulset prometheus-prometheus-kube-prometheus-prometheus`
    * Set "replicas" to 0. This generates the pod which binds to the data volume. Longhorn storage *must* be unbound before it can be resized.
* `vim ~/makerhouse/k3s/k3s-prometheus-stack-values.yaml` 
    * Under prometheus.prometheusSpec.storageSpec.volumeClaimTemplate.spec.resources.requests.storage, change to e.g. "50Gi"
* `helm upgrade prometheus prometheus-community/kube-prometheus-stack --values k3s-prometheus-stack-values.yaml`
    * Longhorn should indicate the volume is being resized. You can also check with `kubectl describe pvc prometheus-prometheus-prometheus-kube-prometheus-prometheus-0` and look for an event like "External resizer is resizing volume pvc-9da184ed-28f9-48d1-82ea-3e0c0a93cf1d"
    * If the status of the pvc is still "Bound", run `kubectl get pods | grep prometheus` to see whether the prometheus operator or the main prometheus pod is still running for some reason. It should be deletable with `kubectl delete pod &lt;foo>` if the deployment and statefulset are both set to 0 replicas. 

Deleting unneeded metrics:

* curl -X POST -g 'http://localhost:9090/api/v1/admin/tsdb/delete_series?match[]=a_bad_metric&match[]={region="mistake"}'
    * See [https://www.robustperception.io/deleting-time-series-from-prometheus](https://www.robustperception.io/deleting-time-series-from-prometheus) 
* curl -X POST -g 'http://prometheus:9090/api/v1/admin/tsdb/delete_series?match[]={instance="192.168.1.5:6443"}'
    * Deletes all metrics for a particular target/instance. 
* curl -X POST -g [http://prometheus:9090/api/v1/admin/tsdb/clean_tombstones](http://prometheus:9090/api/v1/admin/tsdb/clean_tombstones)
    * Do this to actually garbage collect the data - note that this may grow the used disk size (up to 2X if you're deleting most things!) before it shrinks it

## Kubernetes Dashboard

TODO [https://rancher.com/docs/k3s/latest/en/installation/kube-dashboard/](https://rancher.com/docs/k3s/latest/en/installation/kube-dashboard/) 

## MQTT (NodeRed + Mosquitto)

* kubectl apply -f mqtt.yaml -f configmap-mosquitto.yml
* kubectl create secret generic nodered-jwt-key --from-file=/home/ubuntu/makerhouse/k3s/hackerhouse-94c67-5497e5f46d16.json

## Example deployment flow

#### Deployment config:

```
apiVersion: apps/v1
kind: Deployment
metadata:
  name: lbtest-deployment
  labels:
    app: nginx
spec:
  replicas: 3
  selector:
    matchLabels:
      app: nginx
  template:
    metadata:
      labels:
        app: nginx
    spec:
      containers:
      - name: nginx
        image: nginx:1.14.2
        ports:
        - containerPort: 80
```

#### LB config:

```
apiVersion: v1
kind: Service
metadata:
  name: lbtest-service
spec:
  ports:
  - port: 80
    targetPort: 80
  selector:
    app: nginx
  type: LoadBalancer
  loadBalancerIP: 192.168.0.2
```

Commands:

* kubectl create deployment kubernetes-bootcamp --image=gcr.io/google-samples/kubernetes-bootcamp:v1
* kubectl get deployments
* kubectl proxy
    * Can visit e.g. localhost:8001/version
* kubectl get pods
* kubectl describe pods
* export POD_NAME=volume-test
    * visit http://localhost:8001/api/v1/namespaces/default/pods/$POD_NAME/proxy/
* kubectl logs $POD_NAME
* kubectl exec $POD_NAME env
* kubectl exec -ti $POD_NAME bash
    * curl localhost:80

Expose as service via loadbalancer:

* kubectl expose deployment/volume-test --type="LoadBalancer" --port 8080

## Troubleshooting MetalLB

Some failure modes of MetalLB cause only a fraction of the VIPs to not be responsive.

Check to see if all MetalLB pods are in state "running"

* kubectl get pods -n metallb-system -o wide

        ```
        speaker-7l7kv                 1/1     Running   2          16d   192.168.1.5   pi4-1   <none>           <none>
        controller-65db86ddc6-fkpnj   1/1     Running   2          16d   10.42.0.75    pi4-1   <none>           <none>
        speaker-st749                 1/1     Running   1          16d   192.168.1.7   pi4-3   <none>           <none>
        speaker-8wcwj                 1/1     Running   0          16m   192.168.1.6   pi4-2   <none>           <none>

        ```

More details - download kubetail - see bottom of [this page](https://metallb.universe.tf/configuration/troubleshooting/)

* ./kubetail.sh -l component=speaker -n metallb-system
* If you see an error like "connection refused" referencing 192.168.1.#:7946, check to see if one of the "speaker" pods isn't actually running. 

## Maintenance Log

### 2021-04-30 Master node reinstall

Prep:

* Set router DHCP to 8.8.8.8 DNS 
* Copied pihole config ("Teleporter" setting)
* Saved Nodered flows
* TODO Copy k3s keys

Unlisted dependency:

* When setting up SSL cert-manager, certificates couldn’t be issued because the Hover IP hadn’t been updated. Manually update IP in Hover to current house IP.

### 2021-07-22 personal website install

Needed to extend the "SUBDOMAIN" env var in ddns-lexicon.yml, and possibly also add the record to hover.com (may be doing an update, not an upsert?) in addition to creating ingress/service/deployment k3s configs

### 2021-09-02 pihole out of disk

Ran `pihole -g -r` to recreate gravity.db, also deleted /etc/pihole/pihole-FTL.db
