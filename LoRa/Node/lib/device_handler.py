# Author: Donatus
# This script holds functionality for device details handling
from sys import stdin
from select import poll, POLLIN
import os
import ujson
from machine import Pin
from time import ticks_ms

w_led = Pin(12, Pin.OUT)

def request_input(key, **kwargs):
    w_led.on()
    value = input(f'Enter {key} value: ').strip()
    w_led.off()
    return value


def request_input_with_timeout(**kwargs):
    timeout_ms = kwargs.get('timeout_ms', 5000)
    # Read whatever is retained in stdin first
    # Assuming stdin works as a generator, this should be the last line
    # for line in stdin:
    #     break
    # Register the standard input so we can read keyboard presses.
    keyboard = poll()
    keyboard.register(stdin, POLLIN)

    t = ticks_ms()
    # Check if a key has been pressed.
    if keyboard.poll(timeout_ms):
        # Read the key and print it.
        for line in stdin:
            if line == '\n':
                continue
            line = line.rstrip()
            if line != '':
                # print(f'{line}\r\n')    # this is to avoid error prints if you use Thonny
                print(f'Chosen: {line}')
            elif line == '':
                print('')
            break
        keyboard.unregister(stdin)
        return line.strip()
    else:
        print('Timeout elapsed')
        return None


class DeviceDetails():
    checks = {
        'device_check_dict':{
            'base_parameters': ['user_id', 'configure_wireless_parameters', 'configure_advanced_parameters'],
            'wireless_parameters': ['wifi_ssid', 'wifi_password', 'mqtt_client_id', 'mqtt_server', 'publish_topic', 'subscribe_topic', 'certificate_file_name', 'private_key_file_name']
            }
        }
    json_updated = False
    device_details_json = {}

    def __init__(self, file_name='device_details.json'):
        self.file_name = file_name
    
    
    def setup_file(self, file_name):
        with open(file_name, 'w') as f:            
            ujson.dump({}, f)

    @property
    def file_name(self):
        return self._file_name
    

    @file_name.setter
    def file_name(self, file_name_value):
        if file_name_value not in os.listdir():
            self.setup_file(file_name_value)
        
        self._file_name = file_name_value
    

    @property
    def device_details_json(self):
        if DeviceDetails.json_updated:
            return DeviceDetails.device_details_json
        elif not DeviceDetails.json_updated:
            with open(self.file_name, 'r') as f:
                DeviceDetails.device_details_json = ujson.load(f)
            DeviceDetails.json_updated = True
            return DeviceDetails.device_details_json


    @device_details_json.setter
    def device_details_json(self, device_details_json_value):
        if not device_details_json_value:
            self.setup_file(self.file_name)                    
        else:
            with open(self.file_name, 'w') as f:
                ujson.dump(device_details_json_value, f)
        DeviceDetails.json_updated = False
    

    def update_json(self):
        with open(self.file_name, 'w') as f:
            ujson.dump(self.device_details_json, f)
    

    def store(self, key, value, **kwargs):
        self.device_details_json[key] = value
        self.update_json()


    def get(self, key, **kwargs):
        ask = kwargs.get('ask', True)
        ask_always = kwargs.get('ask_always', False)
        value = self.device_details_json.get(key, None)
        if value is None and ask:
            value = request_input(key)
            self.store(key, value)
        
        elif value is not None:
            if ask_always:
                print(f'Edit {key}={value} (y/n)? ', end='')
                response = request_input_with_timeout()

                if response == 'y':
                    value = request_input(key)
                    self.store(key, value)
        
        return value
device_details = DeviceDetails()


class FileDetails():
    checks = {
        'file_check_dict':{
            'base_parameters': ['project_id', 'configure_advanced_parameters'],
            'advanced_parameters': ['run_on_start', 'activate_watchdog']
            }
        }


    def __init__(self, file_name):
        self.file_name = file_name
        self._file_details_json = self.file_details_json

    @property
    def file_name(self):
        return self._file_name
    

    @file_name.setter
    def file_name(self, file_name_value):
        if device_details.device_details_json.get(file_name_value, None) is None:
            device_details.device_details_json[file_name_value] = {}
        self._file_name = file_name_value

    
    @property
    def file_details_json(self):
        return device_details.device_details_json.get(self.file_name)
    
    @file_details_json.setter
    def file_details_json(self, file_details_json_value):
        device_details.device_details_json[self.file_name] = file_details_json_value
        device_details.update_json()
    

    def store(self, key, value, **kwargs):
        device_details.device_details_json[self.file_name][key] = value
        device_details.update_json()


    def get(self, key, **kwargs):
        ask = kwargs.get('ask', True)
        ask_always = kwargs.get('ask_always', False)
        value = device_details.device_details_json[self.file_name].get(key, None)
        if value is None and ask:
            value = request_input(key)
            self.store(key, value)
        
        elif value is not None:            
            if ask_always:
                print(f'Edit {key}={value} (y/n)? ', end='')
                response = request_input_with_timeout()

                if response == 'y':
                    value = request_input(key)
                    self.store(key, value)
        
        return value