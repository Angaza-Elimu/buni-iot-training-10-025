from time import sleep
from ulora import LoRa, ModemConfig, SPIConfig, conex_dict, con_dict
import ujson
import machine
import onewire
import ds18x20
from PicoDHT22 import PicoDHT22
from angaza_mqtt import *
from device_handler import *

# Create DeviceDetails object to access/store device details on board
device_details = DeviceDetails()
# Create FileDetails object to access/store file details on board
file_details = FileDetails('send_lora_combined_mqtt.py')

def on_recv(payload):
    try:
        message_json = ujson.loads(payload.message)
        broker_error = message_json.get('broker_error', None)

        if broker_error:
            print(f'Broker error: {broker_error}')
    except:
        return


# Variables
light_adc = machine.ADC(29)
dht22 = PicoDHT22(machine.Pin(10, machine.Pin.IN, machine.Pin.PULL_UP))
ds18b20_sensor = ds18x20.DS18X20(onewire.OneWire(machine.Pin(2)))
ds_18 = ds18b20_sensor.scan() # scan for the DS18B20 sensor on the onewire bus
moisture_adc_pin = machine.ADC(27)
moisture_digital_pin = machine.Pin(11, machine.Pin.IN)
tds_adc_pin = machine.ADC(26)


# Read ambient light sensor values
def fetch_light_values():
    raw_value = light_adc.read_u16()    #Read raw ADC value
    light_intensity = raw_value * (100/65535)   # Convert raw value to percentage

    return round(light_intensity, 2)


# Read ambient Temperature and Humidity values from the DHT22 sensor
def fetch_dht_values():
    T, H = dht22.read() # Read ambient temperature and humidity values
    return [round(i, 2) for i in [T, H]]


# Read soil temperature
def detect_soil_temperature():
    ds18b20_sensor.convert_temp()   # Read the soil temperature values from the sensor
    soil_temperature = ds18b20_sensor.read_temp(ds_18[0]) # Read the soil temperature values from the sensor
    return round(soil_temperature, 2)


# Read soil moisture content values from the FC-28 soil moisture content sensor
def detect_soil_moisture():
    digital_moisture_value = moisture_digital_pin.value()   # Read the value from the digital pin of the sensor
    analog_moisture_value = moisture_adc_pin.read_u16() # Read the value from the analog pin of the sensor
    soil_moisture_percentage = ((65535-analog_moisture_value) /65535) * 100 # Calculate the soil moisture content value in percent
    return round(soil_moisture_percentage, 2)


# Read TDS value
def detect_tds_values():
    tds_calibration_factor = 800
    tds_analog_value = tds_adc_pin.read_u16()    # Read analog value
    voltage = tds_analog_value *(3.3/65535)      # Convert analog tds value to voltage
    tds_value = voltage * tds_calibration_factor # Calculate TDS value in ppm
    return round(tds_value, 2)


# Wireless specs. Store on device level
user_id = int(device_details.get('user_id', ask_always=True))
project_id = int(file_details.get('project_id', ask_always=True))

# Lora Parameters
RA02_RST = 23
RA02_SPIBUS = SPIConfig.rp2_0   # This is a tuple containing pins used for SPI between the rp2 and RA02 module
RA02_CS = 5
RA02_INT = 24
RA02_FREQ = 433.0
RA02_POW = 18
CLIENT_ADDRESS = 0

while CLIENT_ADDRESS not in range(2, 255):
    try:
        CLIENT_ADDRESS = int(file_details.get('lora_client_address', ask_always=True))
        if CLIENT_ADDRESS not in range(2, 255): print('Invalid lora_client_address. Must be from 2 to 254')
    except:
        print('Invalid lora_client_address. Must be from 2 to 254')

SERVER_ADDRESS = 1  # Address of the server, make sure to ask for this number if you are not configuring the server device yourself

# initialise radio
lora = LoRa(RA02_SPIBUS, RA02_INT, CLIENT_ADDRESS, RA02_CS, reset_pin=RA02_RST, freq=RA02_FREQ, tx_power=RA02_POW, acks=True)
# set callback
lora.on_recv = on_recv
count = 0


# loop and send data
while True:
    light = fetch_light_values()    # Fetch light values
    T, H = fetch_dht_values() # Read ambient temperature and humidity values
    soil_temperature = detect_soil_temperature()    # Read the soil temperature value
    soil_moisture_percentage = detect_soil_moisture()   # Read the soil moisture content value
    tds_value = detect_tds_values() # Read TDS values

    mesg = {
        'count': count,
        'device_id': 'COMBINED',
        'AMBIENT_LIGHT': light,
        'DHT_TEMPERATURE': T,
        'DHT_HUMIDITY': H,
        'SOIL_TEMPERATURE': soil_temperature,
        'SOIL_MOISTURE': soil_moisture_percentage,
        'TDS': tds_value,
        'user_id': user_id,
        'project_id': project_id,
    }


    lora.send_to_wait(conex_dict(mesg, con_dict), SERVER_ADDRESS)
    print("sent")
    sleep(1)
    # set to listen continuously for 10 seconds
    lora.set_mode_rx()
    sleep(10)
    count += 1
