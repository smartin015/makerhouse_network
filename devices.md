# Embedded Devices

Several additional devices provide additional features for MakerHouse residents.

## General

### Occupancy displays (Nanoleaf)

There are [NanoLeaf](https://nanoleaf.me/en-US/) panels configured in 

### Smart light switches (Kasa)

### Voice control (Google Home)

### Custom occupancy and IR control sensors (Wemos D1 Mini)

TODO door switches, PIR sensors

IR blaster for AC units

### AC smart plugs & power monitoring (Sonoff S1 & Custom)

### Embedded displays (D1 Mini)

### Occupancy detection (AIY Vision Kit)

## Workshop

### Workstation

A desktop PC with two monitors in "mirror" mode. The tower is located in a separate room, with two long DisplayPort/HDMI + USB cables providing output to monitors located on opposite sides of the shop. 

The monitors have their own separate keyboards and mice, and the displays are mirrored - this allows for walking around the space and having a consistent desktop environment at each "terminal".

### Print failure auto-detection (Jetson Nano)

There are two [Jetson Nano](https://developer.nvidia.com/embedded/jetson-nano-developer-kit) SBCs available for GPU-enabled embedded computing. 

One of the nano's runs a local instance of [The Spaghetti Detective](https://github.com/TheSpaghettiDetective/TheSpaghettiDetective) to catch failing 3D prints.

### Depth mapping and localization (Jetson Nano)

TODO realsense depth images

### 3D Print Controller (Raspberry Pi)

There are several pi's embedded in the workshop:

* One running [OctoPrint](https://octoprint.org/) for 3d print management on our [CR-30 belt 3d printer](https://www.creality3dofficial.com/products/cr-30-infinite-z-belt-3d-printer). It also has a webcam for remote viewing, and communicates to the jetson nano runnning TSD (above) for failure detection.

### Workshop cameras (Raspberry Pi)

