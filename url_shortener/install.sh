#!/bin/bash

apt-get update

apt-get install -y git cron tmux bash vim nodejs npm
ln -s /usr/bin/nodejs /usr/bin/node