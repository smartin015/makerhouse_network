from nanoleafapi import Nanoleaf
from nanoleafapi import RED, ORANGE, YELLOW, GREEN, LIGHT_BLUE, BLUE, PINK, PURPLE, WHITE
import paho.mqtt.client as mqtt
import json
import time
import os
import threading
import logging

CONN_CHECK_PD_SEC = 30

# Monkey patch the nanoleaf API to allow for request timeouts when writing effects
import requests
from requests.exceptions import Timeout
def write_effect_patch(self, effect_dict) -> bool:
        """Writes a user-defined effect to the panels
        :param effect_dict: The effect dictionary in the format
            described here: https://forum.nanoleaf.me/docs/openapi#_u2t4jzmkp8nt
        :raises NanoleafEffectCreationError: When invalid effect dictionary is provided.
        :returns: True if successful, otherwise False
        """
        try:
            response = requests.put(self.url + "/effects", data=json.dumps({"write": effect_dict}), timeout=5.0)
        except Timeout:
            raise Exception("write_effect timeout to " + self.url)
            
        if response.status_code == 400:
            raise Exception("Invalid effect dictionary")
        return response.status_code in (200, 204)
Nanoleaf.write_effect = write_effect_patch

class NanoleafManager:
    def __init__(self, host, config):
        logging.info(f"Connecting to nanoleaf {host} token {config['token']}")
        self.host = host
        self.config = config

        self.panel_ids = config["panels"]
        self.state = { panel_name : (0,0,0) for panel_name in self.panel_ids.keys() }

        try:
            self.nl = Nanoleaf(host, auth_token=config["token"])
        except Exception as e:
            logging.error(f"Error connecting to nanoleaf: {e}")
            return

        logging.info(str(self.nl.get_info()))
        layout = self.nl.get_info()["panelLayout"]
        orient = layout["globalOrientation"]
        nl_panels = layout["layout"]["positionData"]

        # Check if the nanoleaf knows about any panels not listed in the config
        unmapped_ids = []
        for panel in nl_panels:
            panel_id = panel['panelId']
            if panel_id not in self.panel_ids.values():
                logging.warning(f"Nanoleaf {host} has panel id {panel_id} which was not found in the config file. Reference it by id.")
                unmapped_ids.append(panel_id)
                self.panel_ids[panel_id] = panel_id
                self.state[panel_id] = (0,0,0)

        logging.info(f"Nanoleaf {host} connected, {len(self.panel_ids)} ids: {self.panel_ids}")

    def clone(self):
        return NanoleafManager(self.host, self.config)

    # https://forum.nanoleaf.me/docs#_yvkl74bgmtgu
    # numPanels; panelId0; numFrames0; RGBWT01; RGBWT02; ... RGBWT0n(0);
    # panelId1; numFrames1; RGBWT11; RGBWT12; ... RGBWT1n(1); ... ... panelIdN;
    # numFramesN; RGBWTN1; RGBWTN2; ... RGBWTNn(N);
    def setPanels(self, panel_colors):
        for (panel, rgb) in panel_colors.items():
            if panel not in self.panel_ids:
                logging.error(f"Unrecognized panel name {panel} couldn't be set (to {rgb})")
                continue
            self.state[panel] = (int(rgb[0]), int(rgb[1]), int(rgb[2]))
        idcolormap = [(self.panel_ids[panel], rgb[0], rgb[1], rgb[2]) for (panel, rgb) in self.state.items()]
        animData = f"{len(idcolormap)} " + " ".join([f"{self.panel_ids[panel_id]} 1 {rgb[0]} {rgb[1]} {rgb[2]} 0 20" for (panel_id, rgb) in self.state.items()])
        animData = "%d " % (len(idcolormap)) + " ".join(["%d 1 %d %d %d 0 20" % v for v in idcolormap])
        effect_data = {
                    "command": "display",
                    "animType": "static",
                    "loop": False,
                    "colorType": "HSB",
                    "animData": animData,
                    "palette": [],
                }
        self.nl.write_effect(effect_data)

class Listener:
    def __init__(self, host, port, topic_prefix, status_topic, nanoleaf_map):
        self.client = mqtt.Client()
        self.host = host
        self.port = port
        hosts = nanoleaf_map.keys()
        self.topics = [os.path.join(topic_prefix, h) for h in hosts]
        self.status_topic = status_topic
        self.nanoleaf_map = nanoleaf_map
        self.last_message = time.time()
        self.reinit_client()

    def reinit_client(self):
        logging.info("(re)initializing MQTT client")
        self.client.reinitialise()
        self.client.on_connect = self.on_connect
        self.client.on_disconnect = self.on_disconnect
        self.client.on_message = self.on_message
        self.client.on_log = self.on_log # MQTT wraps on_message in try/except, with errors calling back here.
        logging.info(f"MQTT connecting to {self.host} port {self.port}")
        self.client.connect(self.host, self.port, 60)

    def on_disconnect(client, userdata, rc):
        logging.error(f"MQTT disconnected with result code {rc}")

    def loop_forever(self):
        run = True
        # Been having connection issues with MQTT - reinitializing the connection once per hour
        # is an attempt to "fix" these problems.
        WATCHDOG_TIMEOUT_SEC = 60.0
        while run:
            self.client.loop(timeout=1.0) # Loops once
            if time.time() > self.last_message + WATCHDOG_TIMEOUT_SEC:
                raise Exception(f"MQTT watchdog timeout; message not received for more than {WATCHDOG_TIMEOUT_SEC}")

    def on_log(self, client, userdata, level, buff):
        logging.info(f"MQTT log level {level}: {buff}")

    def on_connect(self, client, userdata, flags, rc):
        logging.info(f"MQTT connected with result code {rc}")
        client.subscribe("/nanoleaf_status_req")
        for t in self.topics:
            client.subscribe(t)
            logging.info(f"Subscribing to {t}")
        client.publish(self.status_topic, "connected")

    def on_message(self, client, userdata, msg):
        self.last_message = time.time()
        try:
            if msg.topic == "/nanoleaf_status_req":
                logging.info("Received status request")
                for nlm in self.nanoleaf_map.values():
                    logging.info(f"Getting and sending info for nanoleaf {nlm.host}")
                    client.publish(self.status_topic, json.dumps(nlm.nl.get_info()))
                logging.info("Status request fulfilled")
            else:
                leaf_id = msg.topic.split("/")[-1]
                data = json.loads(msg.payload)
                self.nanoleaf_map[leaf_id].setPanels(data)
        except Exception as e:
            logging.error(f"Error handling MQTT message to {msg.topic}: {str(e)}")
            try:
                client.publish(self.status_topic, str(e))
            except e:
                logging.error(f"Failed to publish: {e}")
                pass


nl_map = {}
def ensure_connection():
    global nl_map
    logging.info(f"Connection watchdog initialized, checking connection every {CONN_CHECK_PD_SEC} seconds")
    while True:
        time.sleep(CONN_CHECK_PD_SEC)
        keys = list(nl_map.keys())
        for k in keys:
            try:
                nl_map[k].nl.check_connection()
            except Exception as e: # Could be v.nl doesn't exist, or receive connection error
                logging.error(f"Watchdog failed connection to {k} - recreating NanoleafManager")
                nm = nl_map[k].clone()
                del nl_map[k]
                nl_map[k] = nm

def main(args):
    logging.basicConfig(format="%(asctime)s %(levelname)s (t%(thread)d): %(message)s", level=logging.INFO)
    logging.info(f"Looking for config files - available: {os.listdir(args.auth_token_dir)}")
    for h in args.nanoleaf_host:
        os.chdir(args.auth_token_dir)
        with open(h, mode='r') as f:
            config = json.load(f);
        nl_map[h] = NanoleafManager(h, config)

    threading.Thread(target=ensure_connection, daemon=True).start()

    l = Listener(args.mqtt_host, args.mqtt_port, args.mqtt_topic_prefix, args.status_topic, nl_map)
    l.loop_forever()

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Receive MQTT commands to change individual Nanoleaf display panels")
    parser.add_argument("--mqtt_host", default=os.getenv("MQTT_HOST", ""), help="host of MQTT service")
    parser.add_argument("--mqtt_port", default=int(os.getenv("MQTT_PORT", 1883)), help="port of MQTT service")
    parser.add_argument("--mqtt_topic_prefix", default=os.getenv("MQTT_TOPIC_PREFIX", "/nanoleaf/set"), help="topic to listen on. NANOLEAF_HOST is appended")
    parser.add_argument("--status_topic", default=os.getenv("STATUS_TOPIC", "/nanoleaf/status"), help="topic for sending status")
    parser.add_argument("--auth_token_dir", default=os.getenv("AUTH_TOKEN_DIR", "/root/"), help="directory for auth tokens")
    parser.add_argument("--nanoleaf_host", default=os.getenv("NANOLEAF_HOST", ""), help="CSV of ips or hostnames of nanoleaf devices", type=lambda s: [i.strip() for i in s.split(',')])
    args = parser.parse_args()
    main(args)
