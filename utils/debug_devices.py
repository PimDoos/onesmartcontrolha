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

	for command in [OneSmartCommand.PRESET, OneSmartCommand.PRESET_GROUP, OneSmartCommand.MODULES, OneSmartCommand.METER, OneSmartCommand.ROOM, OneSmartCommand.USER, OneSmartCommand.ROLE]:
		print(f"=== Listing { command } ===")
		result = await command_wait(command, action=OneSmartAction.LIST)
		print(result)
	
	
	for action_type in [OneSmartActionType.SITE_PRESET, OneSmartActionType.PRESET_GROUP]:
		print(f"=== Listing triggers for { action_type } ===")
		result = await command_wait(OneSmartCommand.TRIGGER, action=OneSmartAction.GET, actiontype=action_type)
		print(result)


	result = await command_wait(OneSmartCommand.DEVICE, action=OneSmartAction.LIST)
	devices = result[OneSmartFieldName.RESULT][OneSmartFieldName.DEVICES]
	for device in devices:
		device_name = device[OneSmartFieldName.NAME]
		print(f"=== { device_name } ===")
		print(f"Device properties: { device }")
		
		device_id = device[OneSmartFieldName.ID]

		result = await command_wait(OneSmartCommand.APPARATUS, action=OneSmartAction.LIST, id=device_id)
		if not OneSmartFieldName.RESULT in result:
			logging.error("No command result (command timed out?)")
			attributes = []
		elif not OneSmartFieldName.ATTRIBUTES in result[OneSmartFieldName.RESULT]:
			logging.error(f"No device attributes in command result: { result[OneSmartFieldName.RESULT] }")
			attributes = []
		else:
			attributes = result[OneSmartFieldName.RESULT][OneSmartFieldName.ATTRIBUTES]

		print(f"Attributes: { len (attributes) }")
		device_attributes = list()
		device[OneSmartFieldName.ATTRIBUTES] = dict()

		async def fetch_attribute_values(device, device_id, device_attributes):
			if not fetch_attributes:
				return
			await command_wait(OneSmartCommand.PING)
			try:
				print("Fetching attribute values...")
				result = await command_wait(
					OneSmartCommand.APPARATUS, action=OneSmartAction.GET, 
					id=device_id, attributes=device_attributes
				)
				device[OneSmartFieldName.ATTRIBUTES] = device[OneSmartFieldName.ATTRIBUTES] | result[OneSmartFieldName.RESULT][OneSmartFieldName.ATTRIBUTES]
				device_attributes = list()
			except Exception as e:
				logging.error(f"Error fetching attribute values for { device_id }: { e }")

		for attribute in attributes:
			attribute_name = attribute[OneSmartFieldName.NAME]
			if attribute[OneSmartFieldName.ACCESS] in [OneSmartAccessLevel.READ, OneSmartAccessLevel.READWRITE]:
				device_attributes.append(attribute_name)
			
			if len(device_attributes) >= MAX_APPARATUS_POLL:
				await fetch_attribute_values(device, device_id, device_attributes)
		
		if len(device_attributes) > 0:
			await fetch_attribute_values(device, device_id, device_attributes)

		for attribute in attributes:
			attribute_name = attribute[OneSmartFieldName.NAME]
			if attribute_name in device[OneSmartFieldName.ATTRIBUTES]:
				attribute_value = device[OneSmartFieldName.ATTRIBUTES][attribute_name]
				print(attribute_name, attribute, attribute_value)
			else:
				print(attribute_name, attribute)

		print("")

	print("===EVENTS===")
	topics = ['ENERGY', 'DEVICE', 'MESSAGE', 'METER', 'PRESET', 'PRESETGROUP', 'ROLE', 'ROOM', 'TRIGGER', 'SITE', 'SITEPRESET', 'UPGRADE', 'USER']
	#topics = ['DEVICE', 'MESSAGE', 'METER', 'PRESET', 'PRESETGROUP', 'ROLE', 'ROOM', 'TRIGGER', 'SITE', 'SITEPRESET', 'UPGRADE', 'USER']
	await command_wait(OneSmartCommand.EVENTS, action=OneSmartAction.SUBSCRIBE, topics=topics)

	last_ping = time.time()
	while True:
		await gateway.get_responses()
		events = gateway.get_events()
		for event in events:
			print(event)
		
		if time.time() > last_ping + PING_INTERVAL:
			await gateway.send_cmd(OneSmartCommand.PING)
		await asyncio.sleep(1)

	await shutdown()

asyncio.run(run())
