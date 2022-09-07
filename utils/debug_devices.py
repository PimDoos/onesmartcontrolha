import asyncio
from const import *
from onesmartsocket import OneSmartSocket

gateway = OneSmartSocket()

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

	result = await command_wait(COMMAND_DEVICE, action=ACTION_LIST)
	devices = result[RPC_RESULT][RPC_DEVICES]
	for device in devices:
		device_name = device[RPC_NAME]
		print(f"=== { device_name } ===")
		print(f"Device properties: { device }")
		
		device_id = device[RPC_ID]
		result = await command_wait(COMMAND_APPARATUS, action=ACTION_LIST, id=device_id)
		attributes = result[RPC_RESULT][RPC_ATTRIBUTES]

		print(f"Attributes: { len (attributes) }")
		device_attributes = list()
		for attribute in attributes:
			attribute_name = attribute[RPC_NAME]
			if attribute[RPC_ACCESS] in [ACCESS_READ, ACCESS_READWRITE]:
				device_attributes.append(attribute_name)

		try:
			result = await command_wait(
				COMMAND_APPARATUS, action=ACTION_GET, 
				id=device_id, attributes=device_attributes
			)
			device[RPC_ATTRIBUTES] = result[RPC_RESULT][RPC_ATTRIBUTES]
		except Exception as e:
			print(f"Error fetching attributes for { device_id }: { e }")

		for attribute in attributes:
			attribute_name = attribute[RPC_NAME]
			if attribute_name in device[RPC_ATTRIBUTES]:
				attribute_value = device[RPC_ATTRIBUTES][attribute_name]
				print(attribute_name, attribute, attribute_value)
			else:
				print(attribute_name, attribute)

		print("")

	await shutdown()

asyncio.run(run())
