from time import sleep
from ulora import LoRa, ModemConfig, SPIConfig, conex_dict, ex_dict
import ujson

uid_to_lora_map = {}   # map of device user_id to lora address

# This is our callback function that runs when a message is received
def on_recv(payload):
    try:
        client_message = ujson.loads(payload.message)
    except Exception as e:
        print('Invalid payload message')
        return

    # Map new node id to the map list
    try:
        if payload.header_from not in uid_to_lora_map:
            uid_to_lora_map[client_message['u_id']] = payload.header_from
    except:
        print(f'Payload from address {payload.header_from} lacks user_id parameter')
        return

    print(f'From: address {payload.header_from}, user_id: {client_message['u_id']}')
    print(f'Received: {conex_dict(client_message, ex_dict)}')
    print(f'RSSI: {payload.rssi}, SNR: {payload.snr}')
    # RSSI: Received signal strength indicator
    # SNR: Signal to noise ratio
    # Confirm payload is of good format

# Lora Parameters
RA02_RST = 23
RA02_SPIBUS = SPIConfig.rp2_0   # This is a tuple containing pins used for SPI between the rp2 and RA02 module
RA02_CS = 5
RA02_INT = 24
RA02_FREQ = 433.0
RA02_POW = 18
SERVER_ADDRESS = 1  # Address number of the server. Can be 0-255

# initialise lora
lora = LoRa(RA02_SPIBUS, RA02_INT, SERVER_ADDRESS, RA02_CS, reset_pin=RA02_RST, freq=RA02_FREQ, tx_power=RA02_POW, acks=True)

# set callback
lora.on_recv = on_recv

# set to listen continuously
lora.set_mode_rx()

# loop and wait for data
while True:
    sleep(0.1)
