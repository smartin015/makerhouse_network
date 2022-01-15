# Setup instructions for a new nanoleaf

Following https://pypi.org/project/nanoleafapi/

1. To discover without nanoleafapi discovery (Which may fail), use `nmap 192.168.1.* -p 16021 | less` and search for "open"
1. Setup static IP in the edgerouter with a descriptive name so the IP address doesn't move around
1. Enter `python3` shell, `from nanoleafapi import Nanoleaf`
1. Press and hold the power button on the panel until the white light starts flashing
1. Then `nl = Nanoleaf(ip)`, `nl.identify()` to blink the nanoleaf & confirm
1. Do `nl.get_auth_token()` and write it into a file `config/<ip_address>` so it's loaded by the container

# New panels on an existing controller

Check `docker-compose logs`, which reports on panel IDs not yet configured per IP address

# Migrating between hosts

Ensure ~/makerhouse/containers/nanoleaf is up to date with HEAD (the version on github), then copy the config files at `config/...` to the new host (these should NOT get checked in). You may also have to rename the files if the IP address of the nanoleaf has changed since the container was last restarted.
