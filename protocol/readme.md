# One Smart Control protocol description
Thanks to Tweaker [tbone789](https://gathering.tweakers.net/forum/list_message/72315700#72315700) for helping reverse-engineer the protocol.

Connectivity
====================
The One Connect server (eg. One Connect BO-S/6t) listens on TCP port 9010. The listener provides a TLSv1.2 socket with a self signed certificate (Common Name: UnitTestCertificate).
This socket is used by the One Smart Control mobile app to connect locally to the platform.

Protocol
========
The protocol consists of a transaction-based JSON-RPC like protocol. A message can contain any of the following fields:

|Field name|Data type|Description|
|----------|---------|-----------|
|cmd|string|A command domain (see below)|
|transaction|int|An integer to keep track of the result of the command|
|action|string|An action (see below) to perform on the command domain|

Authentication
--------------
Before sending any commands, the client must send the `authenticate` command. 
This command must include a `username` field and a SHA1-encoded hash of the password in the `password` field.
After authenticating, the socket will remain authenticated as long as it is open.

Keep alive
----------
To keep the connection alive, a `ping` command must be sent periodically.
The server will acknowledge this command with a `ping` command and an empty `result` field.

Replies
-------
After issuing a command, the server will respond with the following fields:

|Field name|Data type|Description|
|----------|---------|-----------|
|transaction|int|The transaction id for this reply|
|result|dict|The response data, as a dictionary object|
|cmd|string|The command that was sent (only when replying to `ping`) |

Errors
------
When a command cannot complete, the server replies to the transaction with a error object in the `result` field.


|Code|Description|Explanation|
|----|-----------|-----------|
|1|Parse error|The command could not be parsed|
|3|Timeout|The command did not complete in time|
|10|User not authenticated|The user has not yet issued a `authenticate` command with valid credentials|
|12|Wrong password|The user has supplied invalid credentials in the `authenticate` command|
|100|No such command|The command domain (cmd) does not exist|
|200|Object not found|An object could not be found for the supplied id|
|202|Error in arguments|Command does not contain the expected arguments|
|300|Remote system error|The command threw an exception while executing|


Commands
--------
**Command domains**
|Command|Actions|Description|
|-------|-------|-----------|
|apparatus|?||
|authenticate||Authentication|
|device|get list|Connected devices|
|energy|total|Energy and power|
|events|subscribe unsubscribe|(un)Subscribe to push events|
|gettoken||Get a token to use gateway services|
|logbook|get|Debug logbook|
|meter|get list|Energy meter information
|modules|list|Installed software modules|
|ping||Connection test/keepalive|
|preset|list perform|Presets (actions in the app)|
|presetgroup|list|Preset groups (scenes/automations)|
|room|list get|Rooms|
|site|get|The current deployment context (system)|
|user|get list|User accounts|
|upgrade|check perform|Software updates|
|sitepreset||Site preset triggers|
|shell|?|?|
|trigger|get|Trigger links|

**Action domains**
|Action|Description|
|------|-----------|
|add|Add an object|
|check||
|delete|Remove an object|
|get|Get one object|
|list|List all objects|
|perform|Activate an object|
|subscribe|Subscribe to specified events|
|total|Get total counters|
|update|Update an object's attributes|

**System commands**

|Command|Action|Extra fields|Description|
|-------|------|------------|-----------|
|ping|||Keep-alive command (must be sent periodically)|
|authenticate||`username` (string) and `password` (string, sha1 encoded)|Authenticates the socket connection|

**Command specification**
|Command|Action|Extra fields|Description|
|-------|------|------------|-----------|
|apparatus|get|id (device id), attributes (array of attribute names)|Returns the value of an attribute|
|apparatus|set|id (device id), attributes (dict?)|Set the value of a given attribute|
|apparatus|list|Device ID: `id`|List available device attributes for a given device ID|
|events|subscribe|`topics`: List of topics (see below)|Subscribe to events for the specified topics|
|events|unsubscribe|`topics`: List of topics (see below)|Unsubscribe to events for the specified topics|
|energy|total||Return total values for all meter objects|
|gettoken|get||Returns a Bearer token for portal gateway functions|
|room|list||List all rooms|
|room|get|id|Get specific room information|
|preset|list||Get all presets (actions)|
|meter|list||Get all meters|
|modules|list||List installed software modules|
|role|list||List available user roles|
|room|add||Add a new room|
|room|list||List rooms|
|room|update||Update room attributes|
|room|delete||Remove a room|
|presetgroup|list||Get all scenes / automations|
|device|list||Get all devices|
|site|get||Gets system information|
|site|update|name|Update the system name|
|sitepreset|perform|id|Activate a sitepreset|
|trigger|get|actiontype|Get triggers for `actiontype`, which can be either `SITEPRESET` or `PRESETGROUP`|
|user|list||List all users on the system|
|user|get|username|List information about a specific user|
|upgrade|check||Check for upgrades|
|upgrade|perform|id|Perform the selected upgrade|

Events
------
|Topic|Event|Description|
|-----|-----|-----------|
|APPARATUS|||
|DEVICE|device_input|Called when an input on a device is activated, contains `id` from the triggering device |
|DEVICE|device_data||
|DEVICE|device_status||
|DEVICE|discovery_device_discovered||
|DEVICE|discovery_device_registered||
|DEVICE|discovery_device_register_failed||
|ENERGY|energy_consumption|Reports meter power readings|
|METER|meter_create|Called when a new meter is created|
|METER|meter_update|Called when meter parameters are changed|
|METER|meter_delete|Called when a meter is deleted|
|PRESET|preset_perform|Called when a preset is activated|
|PRESET|preset_stop|Called when a preset is deactivated|
|PRESET|preset_delete|Called when a preset is deleted|
|PRESETGROUP|presetgroup_perform|Called when a presetgroup (scene) is activated|
|ROLE|role_create||
|ROLE|role_update||
|ROLE|role_delete||
|ROOM|room_create||
|ROOM|room_update||
|ROOM|room_delete||
|SITE|site_update|Called when site values are updated. Contains most of the `site` command data.|
|SITEPRESET|sitepreset_perform|Called when a sitepreset is activated|
|TRIGGER|trigger_create|Called when a new trigger is created|
|TRIGGER|trigger_perform|Called when a trigger is executed|
|TRIGGER|trigger_delete|Called when a trigger is deleted|
|UPGRADE|upgrade_available|Called when a software upgrade is available|
|USER|user_update|Called when a user is edited|


Portal Gateway
--------------
One Smart Control provides gateway services from the portal.onesmartcontrol.com domain. To use these services, the client needs a site-id and access token. In the app, this is used to display Comfort and Energy graphs.

The site-id can be acquired via the `site` command with the `get` action.

By using the `gettoken` command with the `get` action, the client acquires a token for gateway services.
The token must be used in the `Authorization` header:
```
Authorization: Bearer {token}
```

With this token and site-id, the client can connect to these endpoints:

|Name|URL|
|----|---|
|Energy|https://portal.onesmartcontrol.com/gateways/{siteid}/|
|Comfort|https://portal.onesmartcontrol.com/gateways/{siteid}/comfort|
|Check comfort features|https://portal.onesmartcontrol.com/gateways/{siteid}/has_parameter?name=room_temperature_zone1|
