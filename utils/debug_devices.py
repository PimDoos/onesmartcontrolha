from time import time
from const import *
from onesmartsocket import OneSmartSocket

gateway = OneSmartSocket()
gateway.connect("oneconnect-ip", 9010)
login_transaction = gateway.authenticate("user", "password")
gateway.get_transaction(login_transaction)

last_ping = time()
meters = None
site = None

def command_wait(command, **kwargs):
	transaction_id = gateway.send_cmd(command, **kwargs)
	transaction_done = False
	while not transaction_done:
		gateway.get_responses()
		transaction = gateway.get_transaction(transaction_id)
		transaction_done = transaction != None

	return transaction

def split_list(lst, n):  
	for i in range(0, len(lst), n): 
		yield lst[i:i + n]

devices = command_wait(COMMAND_DEVICE, action=ACTION_LIST)
devices = devices[RPC_RESULT][RPC_DEVICES]

for device in devices:
	print("============================================")
	print(device[RPC_NAME], "-", device[RPC_TYPE], "-", device["group"])
	if not device[RPC_VISIBLE]:
		continue

	apparatuses = command_wait(COMMAND_APPARATUS, action=ACTION_LIST, id=device[RPC_ID])
	apparatuses = apparatuses[RPC_RESULT][RPC_ATTRIBUTES]

	print(f"Apparatuses: {len(apparatuses)}")
	sensors = []
	selects = []
	for apparatus in apparatuses:
		print(apparatus)
		# Fetch values for READ access
		# if apparatus[RPC_ACCESS] == ACCESS_READ and apparatus[RPC_TYPE] in [TYPE_NUMBER, TYPE_REAL, TYPE_STRING]:
		# 	transaction = command_wait(COMMAND_APPARATUS, action=ACTION_GET, id=device[RPC_ID], attributes=[apparatus[RPC_NAME]])
		# 	if not RPC_ERROR in transaction[RPC_RESULT]:
		# 		sensor_values = transaction[RPC_RESULT][RPC_ATTRIBUTES]	
		# 		for sensor in sensor_values:
		# 			print(sensor, sensor_values[sensor])
		# 	else:
		# 		print(transaction[RPC_RESULT])
