# Maintenance Log

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
