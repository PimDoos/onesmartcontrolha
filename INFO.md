This component add entities from One Smart Control to your Home Assistant instance.

The connection is entirely local, using the JSON-RPC socket on TCP port 9010 of the OneConnect.

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
- Efficiency
- Voltage
- Current
- Frequency
- Percentages
- Revolutions per minute (RPM)
- Mitsubishi Heatpump (via Procon ATW): Operation mode, flow rate, various diagnostic sensors, energy consumption/production

Supported control entities:
- Climate (Mitsubishi Heatpump, Comfoair WTW)
- Water Heater (Mitsubishi Heatpump)
- Room presets
- On/off switches
- One Smart Control light modules
