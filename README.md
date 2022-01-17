# makerhouse_network

Public scripts, services, and configuration for running MakerHouse's home network. This network supports:

* external HTTPS endpoints (Traefik & Cert-Manager)
* virtual services accessible via IP address (MetalLB)
* DNS-level adblocking (PiHole)
* inter-device pub/sub messaging via MQTT (Mosquitto)
* distributed storage (Longhorn)
* automation flows (NodeRed)
* monitoring, dashboarding, and alerting (Prometheus / Grafana)
* custom container hosting (via private registry)

For more high level details, see [this blog post](TODO TODO TODOOOOOO)

![image1](https://user-images.githubusercontent.com/607666/149633433-d87defd0-4143-4bab-8256-fe7ab35c6d46.png)

TODO use the drawing at https://docs.google.com/drawings/d/1UkQKlT5fA8L5bAdiAecp-bR1siNsGnlf4KK2kBhsDHk/edit

For additional services deployed on top of this stack, see the other `*.md` files in this repository.

## Setup

Setting up a replicated pi cluster from scratch is an involved process consisting of several steps:

**Setting up the cluster**

* Purchasing the hardware
* (optional) Network setup
* Flashing the OS
* Installing K3S and linking the nodes together

**Configuring the cluster to be useful**

* Configuring the load balancer and reverse proxy
* Installing a distributed storage solution
* Setting up SSL certificate handling and dynamic DNS

**Setting up customization for IoT and other uses**

* Deploying an image registry for custom container images
* Setting up monitoring/alerting and IoT messaging

There are knowledge prerequisites for following this guide:

* Some basic networking (e.g. how to find a remote device's IP address and SSH into it)
* Linux command line fundamentals (navigating to files, opening and editing them, and running commands)
* It's also useful to know what DHCP is and how to configure it and subnets in your router, for the optional network setup step.

Even if you have advanced knowledge of kubernetes, be prepared to spend several hours on initial setup, plus an hour or two here and there to further refine it.

## Purchasing the Hardware

For the cluster network, you will need:

* An ethernet switch (preferably gigabit) with as many ports as the number of nodes in your cluster, plus one.
* A power supply for your switch
* An ethernet cable running to whatever existing network you have.

For each node, you will need:

* A raspberry pi 4 (or better), recommended 4GB. Ideally all nodes are the same type of pi with the same hardware specs.
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

## (Optional) Network setup

This guide will assume your router is set up with a LAN subnet of `192.168.0.0/23` (i.e. allowing for IP addresses from `192.168.0.1` all the way to `192.168.1.254`).

* `192.168.0.1` is the address of the router
* IP addresses from `192.168.0.2-254` are for exposed cluster services (i.e. virtual devices)
* IP addresses from `192.168.1.2-254` are for physical devices (the raspi's, other IoT devices, laptops, phones etc.)
  * We recommend having a static IP address range not managed by DHCP, e.g. `192.168.1.2-30` and avoiding leasing `192.168.1.1` as it'd be confusing.

If you wish to have public services, set up port forwarding rules for `192.168.0.2` (or the equivalent `loadBalancerIP` set below) for ports 80 and 443, so that your services can be viewed outside the local network.

## Flashing the OS

### Setup SSD boot

Follow [these instructions](https://www.tomshardware.com/how-to/boot-raspberry-pi-4-usb) to install a USB bootloader onto each raspberry pi. Stop when you get to step 9 (inserting the Raspberry Pi OS) as we'll be installing Ubuntu instead.

Use https://www.balena.io/etcher/ or similar to write an [Ubuntu 20.04 ARM 64-bit LTS image ](https://ubuntu.com/download/server/arm) to one of the SSDs. We'll do the majority of setup on this drive, then clone it to the other pi's (with some changes).

### Enable cgroups and SSH

Unplug and re-plug the SSD, then navigate to the `boot` partition and ensure there's a file labeled `ssh` there (if not, create a blank one). This allows us to remote in to the raspi's.

Now we will enable [cgroups](https://en.wikipedia.org/wiki/Cgroups) which are used by k3s to manage the resources of processes that are running on the cluster. 

Append to /boot/firmware/cmdline.txt (see [here](https://askubuntu.com/questions/1237813/enabling-memory-cgroup-in-ubuntu-20-04)):

`cgroup_enable=memory cgroup_memory=1`

Example of a correct config:

```
ubuntu@k3s1:~$ cat /boot/firmware/cmdline.txt 
net.ifnames=0 dwc_otg.lpm_enable=0 console=serial0,115200 console=tty1 root=LABEL=writable rootfstype=ext4 elevator=deadline rootwait fixrtc cgroup_enable=memory cgroup_memory=1
```

### Verify installation

Plug in the SSD, then plug in power to your raspberry pi. Look on your router to find the IP address of the raspberry pi, 

You should be able to SSH into it with username and password `ubuntu`. 

While we're inside, run `passwd` to change away from the default password.

Run `sudo shutdown now` (sudo password is `ubuntu`) and remove power once its led stops blinking. 

### Clone to other pi's

Remove the SSD and use your software of choice (e.g. `gparted` for linux) to clone it to the other blank SSDs. For each SSD, mount it and edit /etc/hostname to be something unique (e.g. `k3s1`, `k3s2`...)

At this time, you can edit your router settings to assign static IP addresses to each raspberry pi for easier access later.

## Installing k3s and linking the nodes together

We will have one server node named `k3s1` and two worker nodes (`k3s2` and `k3s3`). These instructions generally follow the [installation guide from Rancher](https://rancher.com/docs/k3s/latest/en/installation/install-options/).

### Set up k3s1 as master

SSH into the pi, and run the install script from get.k3s.io (see [install options](https://rancher.com/docs/k3s/latest/en/installation/install-options/) for more details):

```
export INSTALL_K3S_VERSION=v1.19.7+k3s1
curl -sfL https://get.k3s.io | sh -s - --disable servicelb --disable local-storage
```

Note:

* We include the K3S version for repeatability.
* ServiceLB and local storage are disabled to make way for MetalLB and Longhorn (distributed storage) configured later in this guide.

Before exiting `k3s1`, run `sudo cat /var/lib/rancher/k3s/server/node-token` and copy it for the next step of linking the client nodes.

### Install and link the remaining nodes

To install on worker nodes and add them to the cluster, run the installation script with the K3S_URL and K3S_TOKEN environment variables. Note use of raw IP - this is more reliable than depending on the cluster DNS (Pihole) to be serving, since that service will itself be hosted on k3s.

```
export K3S_URL=https://<k3s1 IP address>:6443 
export INSTALL_K3S_VERSION=v1.19.7+k3s1
export K3S_TOKEN=<token from k3s1>
curl -sfL https://get.k3s.io | sh -
```

Where K3S_URL is the URL and port of a k3s server, and K3S_TOKEN comes from `/var/lib/rancher/k3s/server/node-token` on the server node (described in the prior step)

### Verifying

That should be it! You can confirm the node successfully joined the cluster by running `kubectl get nodes` when SSH'd into `k3s1:

```
~ kubectl get nodes
NAME   STATUS   ROLES                  AGE    VERSION
k3s1   Ready    control-plane,master   5m   v1.21.0+k3s1
k3s2   Ready    <none>                 1m   v1.21.0+k3s1
k3s3   Ready    <none>                 1m   v1.21.0+k3s1
```

### Set Up Remote Access

It's useful to run cluster management commands from a personal computer rather than having to SSH into the master every time. 

Let's grab the k3s.yaml file from master, and convert it into our local config:

```
ssh ubuntu@k3s1 "sudo cat /etc/rancher/k3s/k3s.yaml" > ~/.kube/config
```

Now edit the server address to be the address of the pi, since from the server's perspective the master is `localhost`:

```
sed -i "s/127.0.0.1/<actual server IP address>/g" ~/.kube/config
```

## Configuring the load balancer and reverse proxy

We will be using [MetalLB](https://metallb.universe.tf/) to allow us to "publish" virtual cluster services on actual IP addresses (in our `192.168.0.2-254` range). This allows us to type in e.g. `192.168.0.10` in a browser and see a webpage hosted from our cluster, without having a device with that specific IP address.

We will also use [Traefik](https://doc.traefik.io/traefik/) to reverse-proxy incoming requests. This lets us different services respond to different subdomains (`mqtt.mkr.house` and `registry.mkr.house`, for instance) without having to do lots of manual IP address mapping.

### MetalLB load balancing / endpoint handling

Install MetalLB onto the cluster following [https://metallb.universe.tf/installation/](https://metallb.universe.tf/installation/):

1. `kubectl apply -f https://raw.githubusercontent.com/metallb/metallb/v0.9.5/manifests/namespace.yaml`
2. `kubectl apply -f https://raw.githubusercontent.com/metallb/metallb/v0.9.5/manifests/metallb.yaml`
3. `kubectl create secret generic -n metallb-system memberlist --from-literal=secretkey="$(openssl rand -base64 128)"`
4. `kubectl apply -f metallb-configmap.yml`
    * See `./core/metallb-configmap.yml`

*Note: instructions say to do `kubectl edit configmap -n kube-system kube-proxy` but there's no such config map in k3s. This wasn't a problem for our installation.*

Test whether metallb is working by starting an exposed service, then cleaning up after:

5.`kubectl apply -f ./core/lbtest.yaml`
6. `kubectl describe service hello`
    * Look for "IPAllocated" in event log
    * Visit `192.168.0.3` and confirm "Welcome to nginx!" is visible
7. `kubectl delete service hello`
8. `kubectl delete deployment hello`

### Troubleshooting

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

* `./kubetail.sh -l component=speaker -n metallb-system`
* If you see an error like "connection refused" referencing 192.168.1.#:7946, check to see if one of the "speaker" pods isn't actually running. 

## Traefik configuration

Traefik is already installed by default with k3s. We still need to configure it, though.

Generate the dashboard password:

1. `htpasswd -c passwd admin`
2. `echo ./passwd`
3. get the part after the colon, before the trailing slash. That's `$password`
4. Update config (`/var/lib/rancher/k3s/server/manifests/traefik.yaml`, move it to `traefik-customized.yaml`):
  * `ssl.insecureSkipVerify: true `
  * `metrics.serviceMonitor.enabled: true`
  * `dashboard.enabled: true`
  * `dashboard.serviceType: "LoadBalancer"`
  * `dashboard.auth.basic.admin: $password`
  * `loadBalancerIP: "192.168.0.2"`
  * `logLevel: "debug"`
5. Edit `/etc/systemd/system/k3s.service` and add `--disable traefik` to disable original traefik config
  * `sudo systemctl daemon-reload`
  * `sudo service k3s restart`
6. Test the configuration:
  * `kubectl apply -f ./core/default-ingress.yml`
  * `kubectl get ingress`
    * You should see something like `hello   &lt;none>   i.mkr.house   192.168.0.2   80      2m2s`

Note: Attempts to query `*.mkr.house` internally lead to the router admin page. You'll need to use a mobile network to test external ingress properly, i.e. that with the lbtest.yaml and default-ingress.yml applied, a "Welcome to nginx!" page is displayed from outside the network.

### Troubleshooting tips

* You can use `journalctl -u k3s` to view k3s logs and look for errors.

## Installing a distributed storage solution

Now we can set up a distributed storage solution, so that we can host things on any of the raspberry pi's that can move freely between them, without worring about locality of data to any particular pi. 

We'll be using [Longhorn](https://rancher.com/products/longhorn), the recommended solution from Rancher.

Follow the [installation guide](https://rancher.com/docs/k3s/latest/en/storage/) to set it up. See `core/longhorn.yaml` for the MakerHouse configured version.

_Note: this solution requires an arm64 architecture, NOT armhf/armv7l which is the default for Raspbian / Raspberry PI OS._

Be sure to also set it as the default storage class, or else certain helm charts will fail to provision their persistent volumes without specifying `storageClass` specifically:

```
kubectl patch storageclass longhorn -p '{"metadata": {"annotations":{"storageclass.kubernetes.io/is-default-class":"false"}}}'
```

The Longhorn UI is not exposed by default; you can expose it with [these instructions](https://longhorn.io/docs/1.0.0/deploy/accessing-the-ui/).

## Setting up SSL certificate handling and dynamic DNS

Now we will set up SSL certificate handling, so that we can serve https pages without browsers complaining about "risky business".

Dynamic DNS will also be configured so that an external DNS provider (in our case, Hover) can direct web traffic to our cluster using a domain name.

### Certificate Management

The following instructions are based on [https://opensource.com/article/20/3/ssl-letsencrypt-k3s](https://opensource.com/article/20/3/ssl-letsencrypt-k3s), but with substitutions for arm64 packages (this tutorial assumes just "arm").

Note that you will need to have ports 80 and 443 forwarded to whatever address is given by `kubectl get ingress`, which is what Traefik is configured to use in `/var/lib/rancher/k3s/server/manifests/traefik-customized.yaml` (See "Traefik configuration" above).

The first two instructions aren't needed if `core/cert-manager-arm.yaml` is correct for the setup:

1. `curl -sL https://github.com/jetstack/cert-manager/releases/download/v0.11.0/cert-manager.yaml | sed -r 's/(image:.*):(v.*)$/\1-arm64:\2/g' > cert-manager-arm.yaml`
2. `grep "image:" cert-manager-arm.yaml`

Now we apply the cert manager:

3. `kubectl create namespace cert-manager`
4. `kubectl apply -f cert-manager-arm.yaml`
5. `kubectl --namespace cert-manager get pods`
6. `kubectl apply -f letsencrypt-issuer-prod.yaml`
7. `kubectl apply -f ingresstest.yaml` (TODO ingress test file)
    * including "annotations" and "tls" sections described [here](https://opensource.com/article/20/3/ssl-letsencrypt-k3s), "request a certificate for our website"
8. `kubectl get certificate`
    * Should be "true", although this may take a couple seconds after init
    * If not, check if `i.mkr.house` resolves to the current house IP. May have to update Hover manually for this portion.
9. `kubectl describe certificate`
    * Should say "Certificate issued successfully"
10. Confirm behavior by going to [https://i.mkr.house](https://i.mkr.house) from external network and seeing the test page.

## Private Registry

A private registry hosts customized containers - such as our custom NodeRed installation with specific addons for handling google sheets, google assistant etc.

This parallels the guide at [https://www.linuxtechi.com/setup-private-docker-registry-kubernetes/](https://www.linuxtechi.com/setup-private-docker-registry-kubernetes/) 

For "simple password" i.e. htpasswd setup (following [these](https://carpie.net/articles/installing-docker-registry-on-k3s) instructions):

1. `sudo apt -y install apache2-utils`
2. `htpasswd -Bc htpasswd registry_htpasswd`
3. `kubectl create secret generic private-registry-htpasswd --from-file ./htpasswd`
4. `kubectl describe secret private-registry-htpasswd`
  * Values:
    * `user: registry_htpasswd`
    * `pass: <your password here>`

Then start the deployment:

5. `kubectl apply -f  private-registry.yml`
    * This creates a persistent volume (via Longhorn), deployment/pod, an exposed service on `192.168.0.5` and a TLS certificate.
6. Add to pihole DNS: "registry" and "registry.lan" mapping to that IP

To test the registry, let's try tagging and pushing an image:

1. docker login registry.mkr.house:443
   * (add username & password when prompted)
2. `docker pull ubuntu:20.04`
3. `docker tag ubuntu:20.04 registry.mkr.house:443/ubuntu`
4. `docker push registry.mkr.house:443/ubuntu`

To see what's in the registry:

5. `curl -X GET --basic -u registry_htpasswd https://registry.mkr.house:443/v2/_catalog | python -m json.tool`

To pull the image:

6. `docker pull registry.mkr.house:443/ubuntu`

Now we need to set up each node so it knows to look for the registry, following [these instructions](https://rancher.com/docs/k3s/latest/en/installation/private-registry/#without-tls) (note: not TLS)

7. `ssh ubuntu@k3s1`
8. `sudo vim /etc/rancher/k3s/registries.yaml`

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

9. `sudo service k3s restart`, then logout

Let's copy it to the remaining nodes and reboot them:

10. `scp ubuntu@k3s1:/etc/rancher/k3s/registries.yaml .`
11. `scp ./registries.yaml ubuntu@k3s2:/home/ubuntu/ `
12. `ssh ubuntu@k3s2`
13. `sudo mkdir -p /etc/rancher/k3s/`
14. `sudo mv registries.yaml /etc/rancher/k3s/`
15. `sudo service k3s-agent restart`
16. Repeat steps 11-15 for `k3s3`.

## Prometheus monitoring & Grafana dashboarding

We'll set up [Prometheus](https://prometheus.io/) to collect metrics for us - including timeseries data we expose from IoT devices via NodeRed.

[Grafana](https://grafana.com/) will host dashboards showing visualizations of the data we collect.

To install Prometheus we will be using [Helm](https://helm.sh/), as there is a nice community provided helm "chart" that does a lot of config and setup work for us.

1. `helm repo add prometheus-community [https://prometheus-community.github.io/helm-charts](https://prometheus-community.github.io/helm-charts)`
2. `helm upgrade --install prometheus prometheus-community/kube-prometheus-stack --values k3s-prometheus-stack-values.yaml`
3. If you need to modify the config, you can see what changes to the `*values.yaml` file do by running: `helm upgrade **--dry-run** prometheus prometheus-community/kube-prometheus-stack --values k3s-prometheus-stack-values.yaml`

We'll set up an additional scrape config (for e.g. nodered custom metrics; [see here for documentation on the config](https://github.com/prometheus-operator/prometheus-operator/blob/master/Documentation/additional-scrape-config.md)).

4. `kubectl create secret generic additional-scrape-configs --from-file=prometheus-additional.yaml --dry-run -oyaml > additional-scrape-configs.yaml`
5. `kubectl apply -f additional-scrape-configs.yaml`

## MQTT (NodeRed + Mosquitto)

We will be using [MQTT](https://mqtt.org/) to pass messages to and from embedded IoT and other devices, and [Node-RED](https://nodered.org/) to set up automation flows based on messages seen. 

Let's build the nodered image to include some extra plugins not provided by the default one:

1. `cd ./nodered && docker build -t registry.mkr.house:443/nodered:latest && docker image push registry.mkr.house:443/nodered:latest`

Both MQTT and NodeRed are included in the `mqtt.yaml` config. "mosquitto" is the specific MQTT broker we're installing.

2. `kubectl apply -f mqtt.yaml -f configmap-mosquitto.yml`

To support Google Assistant commands, we'll need a JWT file. More details [on the plugin page](https://flows.nodered.org/node/node-red-contrib-google-smarthome) for how to acquire this file for your particular instance.

4. `kubectl create secret generic nodered-jwt-key --from-file=/home/ubuntu/makerhouse/k3s/secretfile.json`

