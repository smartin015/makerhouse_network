# makerhouse_network

Scripts, services, and configuration for running [MakerHouse](https://www.mkr.house/)'s home network and cluster. Features include:

* external HTTPS endpoints (Traefik & Cert-Manager)
* virtual services accessible via IP address (MetalLB)
* DNS-level adblocking (PiHole)
* inter-device pub/sub messaging via MQTT (Mosquitto)
* distributed storage (Longhorn)
* automation flows (NodeRed)
* monitoring, dashboarding, and alerting (Prometheus / Grafana)
* custom container hosting (via private registry)

For more high level details, see [this blog post](TODO TODO TODOOOOOO)

![MakerHouse Networking Diagram](https://user-images.githubusercontent.com/775657/150461044-72547ee2-321e-4d7c-a58f-0c0ba6e08656.png "https://docs.google.com/drawings/d/1UkQKlT5fA8L5bAdiAecp-bR1siNsGnlf4KK2kBhsDHk/edit")

For additional services deployed on top of this stack, see the other `*.md` files in this repository.

## Setup

For setup, we will be installing a 64-bit ARM version of Ubuntu onto several raspberry pi's.

Then, we will install a version of kubernetes called [k3s](https://k3s.io/) which is optimized for running on IoT and "edge" devices but is otherwise a drop-in replacement for [k8s i.e. kubernetes](https://kubernetes.io/). This lets us run replicated services with all of the fancy features listed above.

Setting up a replicated pi cluster is an involved process consisting of several steps:

1. Setting up the cluster
    1. Purchasing the hardware
    2. (optional) Network setup
    3. Flashing the OS
    4. Installing K3S and linking the nodes together
2. Configuring the cluster to be useful
    1. Configuring the load balancer and reverse proxy
    2. Installing a distributed storage solution
    3. Setting up SSL certificate handling and dynamic DNS
3. Setting up customization for IoT and other uses
    1. Deploying an image registry for custom container images
    2. Setting up monitoring/alerting 
    3. Setting up MQTT for IoT messaging

Knowledge prerequisites for this guide:

* Some basic networking (e.g. how to find a remote device's IP address and SSH into it)
* Linux command line fundamentals (navigating to files, opening and editing them, and running commands)
* It's also useful to know what DHCP is and how to configure it and subnets in your router, for the optional network setup step

Be prepared to spend several hours on initial setup, plus an hour or two here and there for further refinements.

## 1.1: Purchasing the Hardware

For the cluster network, you will need:

* A gigabit ethernet switch with as many ports as nodes in your cluster, plus one (such as [this one](https://www.amazon.com/gp/product/B0000BVYT3/))
* An ethernet cable connected to your existing network

For each node, you will need:

* A raspberry pi 4 (or better), recommended 4GB. Ideally all nodes are the same type of pi with the same hardware specs.
* A USB-C power supply (5V with at least 2A, such as [this one](https://www.amazon.com/CanaKit-Raspberry-Power-Supply-USB-C/dp/B07TYQRXTK/))
* A short ethernet cable to connect the pi to the switch (such as [this pack](https://www.amazon.com/Cable-Matters-10-Pack-Snagless-Ethernet/dp/B00K2E4X2U/))

For sufficient storage, you will need (per node):

* A USB 3 NVMe M.2 SSD enclosure (such as [this one](https://www.amazon.com/gp/product/B07MNFH1PX))
* An NVMe M.2 SSD (I picked [this 256GB one](https://www.amazon.com/gp/product/B07ZGK3K4V))

You will also likely need an SD card image to flash a "USB boot" bootloader to your raspberry pi's. This will only be needed for initial setup - it will not be used after the pi's boot via SSD.

Before continuing on:

1. Connect your switch to power and the LAN
2. Connect each pi to the switch via ethernet (which port doesn't matter)
3. Install an SSD into each enclosure, then plug one enclosures into one of the blue USB ports on each pi
   * At this point, it helps to label the SSDs with the name you expect each node to be, e.g. `k3s1`, `k3s2` etc. to keep track of where the image 'lives'.

### A note on earlier versions of raspbery pi:

TL;DR: Try to avoid using raspberry pi's earlier than the pi 4, and distributions running ARMv6. If you use a Pi 4 and follow the instructions below, you're in the clear. 

For compatibility with published k3s binaries, you must also be running an ARMv7 or higher OS. This is [only supported on Raspberry Pi 2B and higher](https://wiki.ubuntu.com/ARM/RaspberryPi).[This issue](https://github.com/kubernetes/kubeadm/issues/253) describes that kubernetes support for ARMv6 has been dropped.

## 1.2: Network setup

This guide will assume your router is set up with a LAN subnet of `192.168.0.0/23` (i.e. allowing for IP addresses from `192.168.0.1` all the way to `192.168.1.254`). You may also use `192.168.0.0/16` as well, if you don't plan to have any other subnets on your local network (it takes up the full `192.168.*` range).

* `192.168.0.1` is the address of the router
* IP addresses from `192.168.0.2-254` are for exposed cluster services (i.e. virtual devices)
* IP addresses from `192.168.1.2-254` are for physical devices (the pi's, other IoT devices, laptops, phones etc.)
  * We recommend having a static IP address range not managed by DHCP, e.g. `192.168.1.2-30` and avoiding leasing `192.168.1.1` as it'd be confusing.

## 1.3: Flashing the OS

### Setup SSD boot

Follow [these instructions](https://www.tomshardware.com/how-to/boot-raspberry-pi-4-usb) to install a USB bootloader onto each pi. Stop when you get to step 9 (inserting the Raspberry Pi OS) as we'll be installing Ubuntu for Servers instead.

Use https://www.balena.io/etcher/ or similar to write an [Ubuntu 20.04 ARM 64-bit LTS image](https://ubuntu.com/download/server/arm) to one of the SSDs. We'll do the majority of setup on this drive, then clone it to the other pi's (with some changes).

### Enable cgroups and SSH

**On your local machine** (not the pi) unplug and re-plug the SSD, then navigate to the `boot` partition and ensure there's a file labeled `ssh` there (if not, create a blank one). This allows us to remote in to the pi's.

Now we will enable [cgroups](https://en.wikipedia.org/wiki/Cgroups) which are used by k3s to manage the resources of processes that are running on the cluster. 

Append to /boot/firmware/cmdline.txt (see [here](https://askubuntu.com/questions/1237813/enabling-memory-cgroup-in-ubuntu-20-04)):

`cgroup_enable=memory cgroup_memory=1`

Example of a correct config:

```
ubuntu@k3s1:~$ cat /boot/firmware/cmdline.txt 
net.ifnames=0 dwc_otg.lpm_enable=0 console=serial0,115200 console=tty1 root=LABEL=writable rootfstype=ext4 elevator=deadline rootwait fixrtc cgroup_enable=memory cgroup_memory=1
```

You can now unmount and remove the SSD from your local machine.

### Verify installation

Plug in the SSD to your pi, then plug in USB-C power to turn it on.

Look on your router to find the IP address of the pi. You should be able to SSH into it with username and password `ubuntu`. 

Run `passwd` to change away from the default password.

Run `sudo shutdown now` (sudo password is `ubuntu`) and unplug power once its LED stops blinking. 

### Clone to other pi's

Remove the SSD and use your software of choice (e.g. `gparted` for linux) to clone it to the other blank SSDs. For each SSD, mount it and edit `/etc/hostname` to be something unique (e.g. `k3s1`, `k3s2`...)

Now's a good time to edit your router settings and assign static IP addresses to each pi for easier access later.

## 1.4: Installing k3s and linking the nodes together

For a three node cluster, we'll have one "master" node named `k3s1` and two worker nodes (`k3s2` and `k3s3`). These instructions generally follow the [installation guide from Rancher](https://rancher.com/docs/k3s/latest/en/installation/install-options/).

### Set up k3s1 as master

SSH into the pi, and run the install script from get.k3s.io (see [install options](https://rancher.com/docs/k3s/latest/en/installation/install-options/) for more details):

```
export INSTALL_K3S_VERSION=v1.19.7+k3s1
curl -sfL https://get.k3s.io | sh -s - --disable servicelb --disable local-storage
```

Before exiting `k3s1`, run `sudo cat /var/lib/rancher/k3s/server/node-token` and copy it for the next step of linking the client nodes.

Notes:

* We include the K3S version for repeatability
* ServiceLB and local storage are disabled to make way for MetalLB and Longhorn (distributed storage) configured later in this guide

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

That should be it! You can confirm the node successfully joined the cluster by running `kubectl get nodes` when SSH'd into `k3s1`:

```
~ kubectl get nodes
NAME   STATUS   ROLES                  AGE    VERSION
k3s1   Ready    control-plane,master   5m   v1.21.0+k3s1
k3s2   Ready    <none>                 1m   v1.21.0+k3s1
k3s3   Ready    <none>                 1m   v1.21.0+k3s1
```

### Set Up Remote Access

It's convenient to run cluster management commands from a personal computer rather than having to SSH into the master every time. 

Let's grab the k3s.yaml file from master, and convert it into our local config:

```
ssh ubuntu@k3s1 "sudo cat /etc/rancher/k3s/k3s.yaml" > ~/.kube/config
```

Now edit the server address to be the address of the pi, since from the server's perspective the master is `localhost`:

```
sed -i "s/127.0.0.1/<actual server IP address>/g" ~/.kube/config
```

## 2.1: Configuring the load balancer and reverse proxy

We will be using [MetalLB](https://metallb.universe.tf/) to allow us to "publish" virtual cluster services on actual IP addresses (in our `192.168.0.2-254` range). This allows us to type in e.g. `192.168.0.10` in a browser and see a webpage hosted from our cluster, without having a device with that specific IP address.

### MetalLB load balancing / endpoint handling

Install MetalLB onto the cluster following [https://metallb.universe.tf/installation/](https://metallb.universe.tf/installation/):

```
kubectl apply -f https://raw.githubusercontent.com/metallb/metallb/v0.9.5/manifests/namespace.yaml
kubectl apply -f https://raw.githubusercontent.com/metallb/metallb/v0.9.5/manifests/metallb.yaml
kubectl create secret generic -n metallb-system memberlist --from-literal=secretkey="$(openssl rand -base64 128)"
kubectl apply -f metallb-configmap.yml
```
(TODO what's the user supposed to look at this file for?) See `./core/metallb-configmap.yml`

*Note: instructions say to do `kubectl edit configmap -n kube-system kube-proxy` but there's no such config map in k3s. This wasn't a problem for our installation.*

Test whether metallb is working by starting an exposed service, then cleaning up after:

1. `kubectl apply -f ./core/lbtest.yaml`
2. `kubectl describe service hello`
    1. Look for "IPAllocated" in event log
    2. Visit `192.168.0.3` and confirm "Welcome to nginx!" is visible
3. `kubectl delete service hello`
4. `kubectl delete deployment hello`

### Troubleshooting

Some failure modes of MetalLB cause only a fraction of the VIPs (Virtual IPs) to not be responsive.

Check to see if all MetalLB pods are in state "running" via `kubectl get pods -n metallb-system -o wide`:

        ```
        speaker-7l7kv                 1/1     Running   2          16d   192.168.1.5   pi4-1   <none>           <none>
        controller-65db86ddc6-fkpnj   1/1     Running   2          16d   10.42.0.75    pi4-1   <none>           <none>
        speaker-st749                 1/1     Running   1          16d   192.168.1.7   pi4-3   <none>           <none>
        speaker-8wcwj                 1/1     Running   0          16m   192.168.1.6   pi4-2   <none>           <none>

        ```

More details - download kubetail - see bottom of [this page](https://metallb.universe.tf/configuration/troubleshooting/)

* `./kubetail.sh -l component=speaker -n metallb-system`
* If you see an error like "connection refused" referencing 192.168.1.#:7946, check to see if one of the "speaker" pods isn't actually running. 

## 2.2: Installing a distributed storage solution

Now we can set up a distributed storage solution. Storage should be replicated just as with nodes in a cluster - in this way, no storage location is a single point of failure for the cluster.

We'll be using [Longhorn](https://rancher.com/products/longhorn), the recommended solution from Rancher, which you can read more about [here](https://longhorn.io/). In addition to data redundancy, it abstracts away "where the data is stored" and lets us specify a size of storage to use as a persistent volume for any individual servce, regardless of which node it's hosted on.

Follow the [installation guide](https://rancher.com/docs/k3s/latest/en/storage/) to set it up. See `core/longhorn.yaml` for the MakerHouse configured version, which pins the specific config and version, and tells MetalLB to expose it on 192.168.0.4 (see the `loadBalancerIP` setting).

_Note: this solution requires an arm64 architecture, NOT armhf/armv7l which is the default for Raspbian / Raspberry PI OS. If you followed the instructions for OS installation above, you should be OK._

Be sure to set Longhorn as the default storage class, so that service configs without an explicit `storageClass` specified can automatically use it:

```
kubectl patch storageclass longhorn -p '{"metadata": {"annotations":{"storageclass.kubernetes.io/is-default-class":"false"}}}'
```

The Longhorn UI is not available by default; you can expose it with [these instructions](https://longhorn.io/docs/1.0.0/deploy/accessing-the-ui/).


# Next steps

At this point, you should have a home raspberry pi cluster running k3s, with locally available endpoints and distributed block storage. Congrats!

While this is entirely functional on its own for running simple home services, you may find it lacking if you want to host your own custom/private container images,publish webpages / APIs for external use, or integrate with home automation services (e.g. control homebrew IoT devices with Google Assistant).

Head over to [ADVANCED_SETUP.md](ADVANCED_SETUP.md) to learn how to get the most out of your k3s cluster!

## 3.2: Prometheus monitoring & Grafana dashboarding

We'll set up [Prometheus](https://prometheus.io/) to collect metrics - including timeseries data we expose from IoT devices via NodeRed.

[Grafana](https://grafana.com/) will host dashboards showing visualizations of the data we collect.

We'll use [Helm](https://helm.sh/) to install Prometheus, as there is a nice community-provided Helm "chart" that does a lot of setup work for us.

```
helm repo add prometheus-community [https://prometheus-community.github.io/helm-charts](https://prometheus-community.github.io/helm-charts)
helm upgrade --install prometheus prometheus-community/kube-prometheus-stack --values k3s-prometheus-stack-values.yaml
```

If you need to modify the config, you can see what changes to the `*values.yaml` file do by running: `helm upgrade **--dry-run** prometheus prometheus-community/kube-prometheus-stack --values k3s-prometheus-stack-values.yaml`

We'll set up an additional scrape config (for e.g. nodered custom metrics; [docs here](https://github.com/prometheus-operator/prometheus-operator/blob/master/Documentation/additional-scrape-config.md)).

```
kubectl create secret generic additional-scrape-configs --from-file=prometheus-additional.yaml --dry-run -oyaml > additional-scrape-configs.yaml
kubectl apply -f additional-scrape-configs.yaml
```

## 3.3: MQTT (NodeRed + Mosquitto)

We use [MQTT](https://mqtt.org/) to pass messages to and from embedded IoT and other devices, and [Node-RED](https://nodered.org/) to set up automation flows based on those messages. 

Let's build the nodered image to include some extra plugins not provided by the default one:

`cd ./nodered && docker build -t registry.mkr.house:443/nodered:latest && docker image push registry.mkr.house:443/nodered:latest`

Both MQTT and NodeRed are included in the `mqtt.yaml` config. "mosquitto" is the specific MQTT broker we're installing.

`kubectl apply -f mqtt.yaml -f configmap-mosquitto.yml`

To support Google Assistant commands, we'll need a JWT file. More details [on the plugin page](https://flows.nodered.org/node/node-red-contrib-google-smarthome) for how to acquire this file for your particular instance.

`kubectl create secret generic nodered-jwt-key --from-file=/home/ubuntu/makerhouse/k3s/secretfile.json`

# (Optional) 4: External access

The following steps are for if you want to enable access of your cluster's services from outside of your local network. This can be necesary for some integrations (e.g. NodeRed and Google Assistant) but it may cause vulnerability if not done carefully. The instructions below should provide a secure setup, but variations in home network and cluster setup may still allow for unwanted access. Be careful, and proceed at your own risk.

## 4.1: Port forwarding for external use

If you wish to have public services, set up port forwarding rules for `192.168.0.2` (or the equivalent `loadBalancerIP` set below) for ports 80 and 443, so that your services can be viewed outside the local network.

## 4.2: reverse-proxy with Traefik

We will use [Traefik](https://doc.traefik.io/traefik/) to reverse-proxy incoming requests. This lets us different services respond to different subdomains (`mqtt.mkr.house` and `registry.mkr.house`, for instance) without having to do lots of manual IP address mapping. This will require port forwarding to be set up as described in "Network Setup" above, or else you will not be able to route external traffic to your k3s services.

If you do not want to publish external services, you can ignore this part.

### Traefik configuration

Traefik is already installed by default with k3s. We still need to configure it, though.

Generate the dashboard password:

1. `htpasswd -c passwd admin`
2. `echo ./passwd`
3. Get the part after the colon, before the trailing slash. That's `$password`
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

Note: Attempts to query `*.mkr.house` internally lead to the router admin page. You'll need to use a mobile network or VPN to test external ingress properly, i.e. that with the lbtest.yaml and default-ingress.yml applied, a "Welcome to nginx!" page is displayed from outside the network.

### Troubleshooting tips

* You can use `journalctl -u k3s` to view k3s logs and look for errors.

## 4.3: Setting up SSL certificate handling and dynamic DNS

Now we will set up SSL certificate handling, so that we can serve https pages without browsers complaining about "risky business".

Dynamic DNS will also be configured so that an external DNS provider (in our case, Hover) can direct web traffic to our cluster using a domain name. If you don't already have a particular hosting provider, you can use [our referral code](https://hover.com/yOLF7gpu) and get a $2 credit off your first domain purchase (we get a $2 kickback as well).

### Certificate Management

The following instructions are based on [https://opensource.com/article/20/3/ssl-letsencrypt-k3s](https://opensource.com/article/20/3/ssl-letsencrypt-k3s), but with substitutions for arm64 packages (this tutorial assumes just "arm").

Note that you will need to have ports 80 and 443 forwarded to whatever local IP address is given by `kubectl get ingress`, which is what Traefik is configured to use in `/var/lib/rancher/k3s/server/manifests/traefik-customized.yaml` (See "Traefik configuration" above). In the case of Makerhouse, this is `192.168.0.2`

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

## 3.1: Private Registry

A private registry hosts customized containers - such as our custom NodeRed installation with addons for handling Google Sheets, Google Assistant etc.

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

To test the registry, let's try tagging and pushing an image. Note that you will need to "log in" to the registry in order to interact with it, which is something unique to private registries:

1. `docker login registry.mkr.house:443`
   * (add username & password when prompted)
2. `docker pull ubuntu:20.04`
3. `docker tag ubuntu:20.04 registry.mkr.house:443/ubuntu`
4. `docker push registry.mkr.house:443/ubuntu`

To see what's in the registry:

5. `curl -X GET --basic -u registry_htpasswd https://registry.mkr.house:443/v2/_catalog | python -m json.tool`

To pull the image:

6. `docker pull registry.mkr.house:443/ubuntu`

Now we need to set up each node to look for the registry, following [these instructions](https://rancher.com/docs/k3s/latest/en/installation/private-registry/#without-tls) (note: not TLS)

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

### Dynamic DNS

Dynamic DNS allows for a DNS provider to route web traffic to a IP address which changes over time (such as one provided for a residence by an ISP). Some providers have their own setup for DDNS which you can configure in your home router - others (including Hover) do not have a dedicated process and require a bit more setup.

We use a custom container hosted on our private registry (configured above) to renew the dynamic DNS when our IP changes. To set this up:

```
cd .../makerhouse_network/dynamic_dns

# Build the container image and push it to the registry
docker-compose build
docker image push registry.mkr.house:443/ddns_lexicon:latest

# Push credentials to k3s
# (Replace the $VARs with your credentials for your DNS provider)
./create_ddns_secrets.sh $DNS_USER $DNS_PASSWORD

# Set up the k3s deployment
# Note: you will need to edit the file if you want to manage different subdomains or have a different registry name
kubectl apply -f ddns_lexicon.yaml
```
