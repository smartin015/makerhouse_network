#!/bin/bash
cd /volume
tmux new-session -s node 'node index.js || /bin/bash'