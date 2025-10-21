from time import sleep
from ulora import LoRa, ModemConfig, SPIConfig, conex_dict, ex_dict
import ujson
import machine
from angaza_mqtt import *
from device_handler import *

# Create DeviceDetails object to access/store device details on board
device_details = DeviceDetails()
# Create FileDetails object to access/store file details on board
file_details = FileDetails('receive_lora_mqtt.py')

wdt = None
wdt_timer = None
activate_watchdog = file_details.get('activate_watchdog', ask_always=True)
if activate_watchdog is not None and activate_watchdog == 'y':
    wdt = machine.WDT(timeout=8000)
    wdt_timer = machine.Timer()

    def feed_watchdog(t):
        wdt.feed()
    wdt_timer.init(mode=machine.Timer.PERIODIC, freq=1, callback=feed_watchdog)

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
uid_to_lora_map = {}   # map of device user_id to lora address
payload_list = []

# Wireless specs. Store on device level
# Make sure all mqtt related parameters are allowed in the policies!!!
user_id = int(device_details.get('user_id', ask_always=True))
wifi_ssid = device_details.get('wifi_ssid', ask_always=True)
wifi_password = device_details.get('wifi_password', ask_always=True)
mqtt_client_id = device_details.get('mqtt_client_id', ask_always=True)
mqtt_server = device_details.get('mqtt_server', ask_always=True)
publish_topic = device_details.get('publish_topic', ask_always=True)
subscribe_topic = device_details.get('subscribe_topic', ask_always=True)
private_key_file_name = device_details.get('private_key_file_name', ask_always=True)
certificate_file_name = device_details.get('certificate_file_name', ask_always=True)


# define a function that will be executed when a message from the broker is received having subscribed to a topic
@sub_handler
def sub_callback(message):
    message_json = ujson.loads(message)
    client_address = message_json.get('user_id', None)

    if client_address:
        lora.send_to_wait(message, uid_to_lora_map[client_address])

    sleep(1)
    lora.set_mode_rx()


# mqtt setup
uart = machine.UART(0, baudrate=115200, tx=machine.Pin(0), rx=machine.Pin(1))   # Initialize uart on the rp2040
mqtt = MQTTClient(uart_obj=uart, client_id=mqtt_client_id, server=mqtt_server, port=8883, keepalive=1200, ssl=True)
file_dict = {'key': private_key_file_name, 'cert': certificate_file_name}   # Make sure these files are in the rp2040 fs

def wireless_setup():
    while True:
        try:
            uart_config(uart)   # Ensure graceful esp12-f startup
            global wifi_ssid, wifi_password
            assert connect_to_wifi(uart, wifi_ssid, wifi_password) == True, 'Failed to connect to wifi'
            mqtt.connect(file_dict)   # Connect to mqtt broker
            mqtt.set_callback(subscribe_topic, sub_callback)  # Set callback function. Do this before subscribing
            mqtt.subscribe(subscribe_topic)  # Subscribe to a topic
            break
        except KeyboardInterrupt:
            raise KeyboardInterrupt
        except Exception as e:
            print(f'Failed with error: {e}')
            if wdt_timer is not None:
                wdt_timer.deinit()
            sleep(10) # Sleep until reset if wdt is not None

wireless_setup()


# Define lora callback
# This is our callback function that runs when a message is received from a lora client
def on_recv(payload):
    # Confirm payload is of good format
    payload_user_id = None
    try:
        client_message = ujson.loads(payload.message)
    except Exception as e:
        print('Invalid payload message. Ignoring mqtt publish...')
        return

    try:
        if payload.header_from not in uid_to_lora_map:
            payload_user_id = client_message['u_id']
            uid_to_lora_map[payload_user_id] = payload.header_from
    except:
        print(f'Payload from address {payload.header_from} lacks user_id parameter')
        return

    try:
        if int(payload_user_id) == user_id:
            push_dict = conex_dict(client_message, ex_dict)
            push_dict['client_id'] = mqtt_client_id
            payload_list.append(push_dict)

            if len(payload_list) > 5:
                del payload_list[0]
        else:
            print(f'Ignoring publish of payload from user_id: {payload_user_id}')
    except:
        print('Failed to publish')


# set lora callback
lora.on_recv = on_recv

# set to listen continuously
lora.set_mode_rx()

# loop and wait for data
while True:
    # Check for messages.
    try:
        mqtt.check_msg()

        if len(payload_list) > 0:
            mqtt.publish(publish_topic, payload_list[0])
            del payload_list[0]
    except KeyboardInterrupt:
        raise KeyboardInterrupt
    except Exception as e:
        print(f'Failed with error: {e}')

        try:
            wireless_setup()
        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f'Failed with error: {e}')

    sleep(5)


private.pem.key
certificate.pem.crt
Solar operation - check with Elvis
Multiparameter sensor - check with Don
    -
