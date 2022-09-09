import asyncio
import time
from const import *
from onesmartsocket import OneSmartSocket
import logging
logging.basicConfig(level=logging.DEBUG)

gateway = OneSmartSocket()

fetch_attributes = False

async def setup():
	await gateway.connect("OneServerIP", 9010)
	await gateway.authenticate("admin", "password")

async def command_wait(command, **kwargs):
	transaction_id = await gateway.send_cmd(command, **kwargs)
	transaction_done = False
	while not transaction_done:
		await gateway.get_responses()
		transaction = gateway.get_transaction(transaction_id)
		transaction_done = transaction != None

	return transaction


async def shutdown():
	await gateway.close()

async def run():
	await setup()

	for command in [COMMAND_PRESET, COMMAND_PRESET_GROUP, COMMAND_MODULES, COMMAND_METER]:
		print(f"=== Listing { command } ===")
		result = await command_wait(command, action=ACTION_LIST)
		print(result)
	
	
	for action_type in [ACTIONTYPE_SITE_PRESET, ACTIONTYPE_PRESET_GROUP]:
		print(f"=== Listing triggers for { action_type } ===")
		result = await command_wait(COMMAND_TRIGGER, action=ACTION_GET, actiontype=action_type)
		print(result)


	result = await command_wait(COMMAND_DEVICE, action=ACTION_LIST)
	devices = result[RPC_RESULT][RPC_DEVICES]
	for device in devices:
		device_name = device[RPC_NAME]
		print(f"=== { device_name } ===")
		print(f"Device properties: { device }")
		
		device_id = device[RPC_ID]

		result = await command_wait(COMMAND_APPARATUS, action=ACTION_LIST, id=device_id)
		if not RPC_RESULT in result:
			logging.error("No command result (command timed out?)")
			attributes = []
		elif not RPC_ATTRIBUTES in result[RPC_RESULT]:
			logging.error(f"No device attributes in command result: { result[RPC_RESULT] }")
			attributes = []
		else:
			attributes = result[RPC_RESULT][RPC_ATTRIBUTES]

		print(f"Attributes: { len (attributes) }")
		device_attributes = list()
		device[RPC_ATTRIBUTES] = dict()

		async def fetch_attribute_values(device, device_id, device_attributes):
			if not fetch_attributes:
				return
			await command_wait(COMMAND_PING)
			try:
				print("Fetching attribute values...")
				result = await command_wait(
					COMMAND_APPARATUS, action=ACTION_GET, 
					id=device_id, attributes=device_attributes
				)
				device[RPC_ATTRIBUTES] = device[RPC_ATTRIBUTES] | result[RPC_RESULT][RPC_ATTRIBUTES]
				device_attributes = list()
			except Exception as e:
				logging.error(f"Error fetching attribute values for { device_id }: { e }")

		for attribute in attributes:
			attribute_name = attribute[RPC_NAME]
			if attribute[RPC_ACCESS] in [ACCESS_READ, ACCESS_READWRITE]:
				device_attributes.append(attribute_name)
			
			if len(device_attributes) >= MAX_APPARATUS_ATTRIBUTES_LENGTH:
				await fetch_attribute_values(device, device_id, device_attributes)
		
		if len(device_attributes) > 0:
			await fetch_attribute_values(device, device_id, device_attributes)

		for attribute in attributes:
			attribute_name = attribute[RPC_NAME]
			if attribute_name in device[RPC_ATTRIBUTES]:
				attribute_value = device[RPC_ATTRIBUTES][attribute_name]
				print(attribute_name, attribute, attribute_value)
			else:
				print(attribute_name, attribute)

		print("")

	print("===EVENTS===")
	#topics = ['ENERGY', 'DEVICE', 'MESSAGE', 'METER', 'PRESET', 'PRESETGROUP', 'ROLE', 'ROOM', 'TRIGGER', 'SITE', 'SITEPRESET', 'UPGRADE', 'USER']
	topics = ['DEVICE', 'MESSAGE', 'METER', 'PRESET', 'PRESETGROUP', 'ROLE', 'ROOM', 'TRIGGER', 'SITE', 'SITEPRESET', 'UPGRADE', 'USER']
	await command_wait(COMMAND_EVENTS, action=ACTION_SUBSCRIBE, topics=topics)

	last_ping = time.time()
	while True:
		await gateway.get_responses()
		events = gateway.get_events()
		for event in events:
			print(event)
		
		if time.time() > last_ping + PING_INTERVAL:
			await gateway.send_cmd(COMMAND_PING)

	await shutdown()

asyncio.run(run())
