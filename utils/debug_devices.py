import asyncio
from const import *
from onesmartsocket import OneSmartSocket

gateway = OneSmartSocket()

async def setup():
	await gateway.connect("172.25.16.119", 9010)
	await gateway.authenticate("admin", "MasPasOne")

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
		device_id = device[RPC_ID]
		result = await command_wait(COMMAND_APPARATUS, action=ACTION_LIST, id=device_id)
		attributes = result[RPC_RESULT][RPC_ATTRIBUTES]
		for attribute in attributes:
			attribute_name = attribute[RPC_NAME]
			if attribute[RPC_ACCESS] in [ACCESS_READ, ACCESS_READWRITE]:
				try:
					result = await command_wait(
						COMMAND_APPARATUS, action=ACTION_GET, 
						id=device_id, attributes=[attribute_name]
					)
					attribute_value = result[RPC_RESULT][RPC_ATTRIBUTES][attribute_name]
				except:
					attribute_value = "Failed"
				finally:
					print(attribute_name, attribute, attribute_value)
			else:
				print(attribute_name, attribute)

			

	await shutdown()

asyncio.run(run())
