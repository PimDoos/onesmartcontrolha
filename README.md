# One Smart Control integration
[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)

Home Assistant integration for One Smart Control server

Uses local push via JSON-RPC over TLS on port 9010. Thanks to [tbone789](https://tweakers.net/gallery/532104/) on Tweakers for helping reverse engineer the protocol.
Read more about the protocol [here](https://github.com/PimDoos/onesmartcontrolha/tree/main/protocol).

Setup via HACS
-----
1. Add this repository to your custom repositories
2. Setup the integration via the config flow 

[![](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=onesmartcontrol)

Supported functionality
-----------------------
Supported OneConnect sensors:
- P1 meter (Energy / Power)
- Pulse meter (Energy / Power)
- Phase meter (Energy / Power)
- System Mode (Home/Away/Sleep)

Supported device sensors:
- Temperature
- CO2
- Power
- Huawei SUN2000 Energy (Total/day)
- Voltage
- Current
- Frequency
- Percentages
- Mitsubishi Heatpump (via Procon ATW): Operation mode, flow rate, various diagnostic sensors
