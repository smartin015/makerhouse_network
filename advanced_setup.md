# Advanced cluster setup

The following instructions build on top of the initial setup in [README.md](readme.md) and further configure your home cluster:

1. Setting up external access
    1. Configuring your DNS provider
    2. Reverse-proxy with Traefik
    3. Configuring SSL certificate handling and renewal
2. Customization for IoT and other uses
    1. Deploying an image registry for custom container images
    2. Setting up MQTT for IoT messaging
    3. Setting up monitoring/alerting/dashboarding with Prometheus and Grafana
3. Setting up dynamic DNS

Knowledge prerequisites for this guide:

* Some basic networking (e.g. how to find a remote device's IP address and SSH into it)
* Linux command line fundamentals (navigating to files, opening and editing them, and running commands)

**IMPORTANT:** This guide assumes you have a running k3s cluster as configured in [README.md](readme.md). Please follow that guide first if you haven't already.

# 1. External access

The following steps are for if you want to enable access of your cluster's services from outside of your local network. This is necessary for some integrations (e.g. NodeRed and Google Assistant) but it may cause vulnerability if not done carefully. The instructions below are intended to provide a secure setup, but variations in home network and cluster setup may still allow for unwanted access. Be careful, and proceed at your own risk.

## 1.1: DNS providers

If you don't already have a particular hosting provider, you can use [our referral code](https://hover.com/yOLF7gpu) and get a $2 credit off your first domain purchase (we get a $2 kickback as well). 

Otherwise, please use the provider of your choice and register a [DNS A Record](https://www.cloudflare.com/learning/dns/dns-records/dns-a-record/#:~:text=What%20is%20a%20DNS%20A,210.9.) for each subdomain you wish to use (e.g. "hello" for `hello.mkr.house`) that points to the external IP address of your home network (you can use e.g. https://www.whatismyip.com/ to find this address). 

Don't worry about the IP address changing; we'll set up Dynamic DNS in a bit.

**Note:** We will reference `*.mkr.house` in the instructions below; this is our house domain. Substitute these with your own domain.

## 1.2: Reverse-proxy with Traefik

We will use [Traefik](https://doc.traefik.io/traefik/) to reverse-proxy incoming requests. This lets us different services respond to different subdomains (`mqtt.mkr.house` and `registry.mkr.house`, for instance) without having to do lots of manual IP address mapping. This will require port forwarding to be set up as described in "Network Setup" above, or else you will not be able to route external traffic to your k3s services.

### Router configuration

At this time, set up port forwarding rules for `192.168.0.2` (or the equivalent `loadBalancerIP` if you set up MetalLB with a different one) for ports 80 and 443, so that your services can be viewed outside the local network. The process varies per home router, but are usually pretty straightforward.

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
    * You should see something like `hello   &lt;none>   hello.mkr.house   192.168.0.2   80      2m2s`

Note: Attempts to query `*.mkr.house` may internally lead to your router's admin page, unless something like [hairpin NAT](https://en.wikipedia.org/wiki/Hairpinning) is enabled. If this is the case, you'll need to use a mobile network or VPN to test external ingress properly, i.e. that with the lbtest.yaml and default-ingress.yml applied, a "Welcome to nginx!" page is displayed from outside the network.

### Troubleshooting tips

* You can use `journalctl -u k3s` to view k3s logs and look for errors.

## 1.3: Setting up SSL certificate handling

Now we will set up SSL certificate handling, so that we can serve HTTPS pages without browsers complaining about "risky business". We will be using [cert-manager](https://cert-manager.io/docs/) which automatically handles certificate acquisitiona and renewal for any services we set up for external access (which is to say, any [Ingress](https://kubernetes.io/docs/concepts/services-networking/ingress/) objects we've set up).

### Certificate Management

The following instructions are based on [https://opensource.com/article/20/3/ssl-letsencrypt-k3s](https://opensource.com/article/20/3/ssl-letsencrypt-k3s), but with substitutions for arm64 packages (this tutorial assumes just "arm").

The first two instructions aren't needed if `core/cert-manager-arm.yaml` is correct for the setup:

1. `curl -sL https://github.com/jetstack/cert-manager/releases/download/v0.11.0/cert-manager.yaml | sed -r 's/(image:.*):(v.*)$/\1-arm64:\2/g' > cert-manager-arm.yaml`
2. `grep "image:" cert-manager-arm.yaml`

Now we apply the cert manager:

3. `kubectl create namespace cert-manager`
4. `kubectl apply -f cert-manager-arm.yaml`
5. `kubectl --namespace cert-manager get pods`
6. `kubectl apply -f letsencrypt-issuer-prod.yaml`
7. `kubectl apply -f core/lbtest.yaml`
    * This contains an `Ingress` configuration which by default exposes on `hello.mkr.house`.
    * The importint bits are the "annotations" and "tls" sections described [here](https://opensource.com/article/20/3/ssl-letsencrypt-k3s), "request a certificate for our website"
8.  Wait a few minutes for cert-manager to request and get a certificate for this subdomain
8. `kubectl get certificate`
    * Should be "true"
    * If not, check if `hello.mkr.house` resolves to the current house IP. You may have to update Hover manually for this portion until we've set up DDNS (below)
9. `kubectl describe certificate`
    * Should say "Certificate issued successfully"
10. Confirm behavior by going to [https://hello.mkr.house](https://hello.mkr.house) from external network and seeing the test page.

## 2: Customization for IoT and other uses

Now that we have external access set up, we can 

## 2.1: Private Registry

A private registry hosts customized containers - such as our custom NodeRed installation with addons for handling Google Sheets, Google Assistant etc. We'll need to set this up before we go any further. 

We wish to host our registry so it can be accessed externally (with authentication). This requires an "A" record `registry.mkr.house` (or equivalent) configured with your DNS provider (see above). You *can* forgo this and use the MetalLB IP address, but it's not intended to run without HTTPS and requires [additional hoop jumping](https://docs.docker.com/registry/insecure/) for it to work. Just use the subdomain; it's easier.

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


## 2.2: MQTT (NodeRed + Mosquitto)

We use [MQTT](https://mqtt.org/) to pass messages to and from embedded IoT and other devices, and [Node-RED](https://nodered.org/) to set up automation flows based on those messages. 

Let's build the nodered image to include some extra plugins not provided by the default one:

`cd ./nodered && docker build -t registry.mkr.house:443/nodered:latest && docker image push registry.mkr.house:443/nodered:latest`

Both MQTT and NodeRed are included in the `mqtt.yaml` config. "mosquitto" is the specific MQTT broker we're installing.

`kubectl apply -f mqtt.yaml -f configmap-mosquitto.yml`

To support Google Assistant commands, we'll need a JWT file. More details [on the plugin page](https://flows.nodered.org/node/node-red-contrib-google-smarthome) for how to acquire this file for your particular instance.

`kubectl create secret generic nodered-jwt-key --from-file=/home/ubuntu/makerhouse/k3s/secretfile.json`

## 2.3: Prometheus monitoring & Grafana dashboarding

Now we'll set up [Prometheus](https://prometheus.io/) to collect metrics - including timeseries data we expose from IoT devices via NodeRed.

[Grafana](https://grafana.com/) will host dashboards showing visualizations of the data we collect.

We'll use [Helm](https://helm.sh/) to install Prometheus. Helm is a package manager for kubernetes, and there is a nice community-provided Helm "chart" that does a lot of setup work for us.

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

## 3: Dynamic DNS

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

## Next Steps

Now our home cluster is really rockin'! We have external HTTPS hosting, pub-sub networking via MQTT, monitoring and dashboarding capabilities, and we can build and host our own containers without any external dependencies.

There's still more that can be done - if there's interest, we may publish later tutorials on:

* Setting up [smart lighting](https://nanoleaf.me/en-US/products/nanoleaf-light-panels/) to indicate room and appliance occupancy
* Building custom home automation devices using [Tasmota](https://tasmota.github.io/docs/) to power lights, monitor power, control HVAC devices, and more
* Configuring shortURLs and local DNS for quick access to services, plus DNS-level adblocking using K3S-hosted [PiHole](https://pi-hole.net/)

And even more advanced topics, such as:

* Localization and depth mapping for robotics using [Intel Realsense](https://www.intel.com/content/www/us/en/architecture-and-technology/realsense-overview.html) depth cameras 
* Industrial PLC automation using [Click PLCs](https://www.automationdirect.com/adc/overview/catalog/programmable_controllers/click_series_plcs/click_plcs_(stackable_micro_brick)) and [Ignition HMI](https://inductiveautomation.com/ignition/)
