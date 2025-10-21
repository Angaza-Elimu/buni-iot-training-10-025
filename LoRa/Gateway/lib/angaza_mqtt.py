# Author: Donatus
# This script holds all functions that enable wireless related activities such as mqtt
from cmdlib import *
from machine import RTC, Pin
import os
from time import sleep, ticks_ms, ticks_diff
import ubinascii
from device_handler import device_details

client_list = []
w_led = Pin(12, Pin.OUT)    # led pin object for connection status updates

class MQTTException(Exception):
    pass


class MQTTClient:
    def __init__(
        self,
        uart_obj,
        client_id,
        server,
        port=0,      
        keepalive=0,
        ssl=False,
        ssl_params={},
        publish_feedback=True,
    ):
        if port == 0:
            port = 8883 if ssl else 1883
        self.client_id = client_id
        self.sock = None
        self.server = server
        self.port = port
        self.ssl = ssl
        self.ssl_params = ssl_params
        self.cb = {}
        self.keepalive = keepalive       
        self.uart_obj = uart_obj
        self.target_ref = None
        client_list.append(self)
        self.ref = client_list.index(self)
        self.publish_feedback = publish_feedback
        self.mqtt_connect_success = False


    @property
    def publish_feedback(self):
        return self.__publish_feedback
    

    @publish_feedback.setter
    def publish_feedback(self, feedback_set):
        assert type(feedback_set) is bool, 'Publish feedback should be a boolean'
        self.__publish_feedback = feedback_set


    def set_callback(self, topic, f):
        self.cb[topic] = f
    

    def read_pem(self, filename):        
        with open(filename, 'r') as f:
            text = f.read().strip()
            split_text = text.split('\n')
            base64_text = ''.join(split_text[1:-1])
            # Decode base64-encoded data, ignoring invalid characters in the input. Conforms to RFC 2045 s.6.8. Returns a bytes object.
            return ubinascii.a2b_base64(base64_text)
    

    @func_handler
    def send_key_cert(self, specifier, filename):
        assert filename in os.listdir(), f'{filename} not in file system'
        txjson = {'action': ['mqtt_operation'], 'mqtt_operation': {'arg_available': True, 'argument': [{'operation': 'receive_key_cert', 'receive_key_cert': {'arg_available': True, 'argument': [self.ref, specifier]}}]}}
        send_data(self.uart_obj, ujson.dumps(txjson), end_format='command')       

        while True:
            rxData = receive_data(self.uart_obj)            

            if rxData is not None and rxData[0] == f'receive {specifier} ready':
                sleep(0.01)
                send_data(self.uart_obj, self.read_pem(filename))
            elif rxData is not None and rxData[-1] == 'd':
                rxjson = ujson.loads(rxData[0])                
                return rxjson.get('status')
            elif rxData is not None and rxData[-1] == 'o':
                print(rxData[0])
    
    
    @func_handler
    def mqtt_init(self, file_dict, **kwargs):
        # send certificates to esp
        for specifier, filename in file_dict.items():
            sleep(0.1)
            if not self.send_key_cert(specifier, filename, debug_func=True):
                raise Exception('Error in sending keys')
        
        txjson = {'action': ['mqtt_operation'], 'mqtt_operation': {'arg_available': True, 'argument': [{'operation': 'mqtt_init', 'mqtt_init': {'arg_available': True, 'argument': [[self.client_id, self.server, self.port, self.keepalive, self.ssl, self.ref]]}}]}}
        # send mqtt_init command to esp
        # print(f'sending init command to esp')
        sleep(0.1)
        send_data(self.uart_obj, ujson.dumps(txjson), end_format='command')

        while True:
            rxData = receive_data(self.uart_obj)
            
            if rxData is not None and rxData[-1] == 'c':            
                process_command(self.uart_obj, rxData[0])
            elif rxData is not None and rxData[-1] == 'd':
                rxjson = ujson.loads(rxData[0])
                return rxjson.get('status')
            elif rxData is not None and rxData[-1] == 'o':                
                print(rxData[0])


    retry_dict['connect'] = {'retries': 3, 'other_args': {'jump_mqtt_init': False}}
    @func_handler
    def connect(self, file_dict, **kwargs):
        jump_mqtt_init = kwargs.get('jump_mqtt_init', False)
        # initialize mqtt object on esp side and obtain target ref value
        if not jump_mqtt_init or self.target_ref is None:           
            if not self.mqtt_init(file_dict, debug_func=True):
                raise Exception('mqtt init failed')
            retry_dict['connect']['other_args']['jump_mqtt_init'] = True

        txjson = {'action': ['mqtt_operation'], 'mqtt_operation': {'arg_available': True, 'argument': [{'operation': 'mqtt_connect', 'mqtt_connect': {'arg_available': True, 'argument': [self.target_ref]}}]}}
        # send connect command to esp
        sleep(0.1)
        send_data(self.uart_obj, ujson.dumps(txjson), end_format='command')
        timer_x = Timer()

        while True:
            rxData = receive_data(self.uart_obj)

            if rxData is not None and rxData[-1] == 'd':
                rxjson = ujson.loads(rxData[0])
                timer_x.deinit()
                print('\n', end='')
                self.mqtt_connect_success = rxjson.get('status')
                return self.mqtt_connect_success
            elif rxData is not None and rxData[-1] == 'o':                
                if rxData[0] == 'Connecting to MQTT broker...':
                    print(rxData[0], end='')
                    timer_x.init(mode=Timer.PERIODIC, freq=1, callback=progress_bar)
                else:
                    print(f'\n{rxData[0]}')


    def disconnect(self):
        # send disconnect command to esp
        pass
    

    exempt_function_dict['publish'] = ['on_success', 'on_failure']
    @func_handler
    def publish(self, topic, msg):
        assert self.mqtt_connect_success, 'Device not connected to mqtt broker'
        sleep(0.1)
        # send publish command to esp
        txjson = {'action': ['mqtt_operation'], 'mqtt_operation': {'arg_available': True, 'argument': [{'operation': 'mqtt_publish', 'mqtt_publish': {'arg_available': True, 'argument': [self.target_ref, topic, msg, self.__publish_feedback]}}]}}
        send_data(self.uart_obj, ujson.dumps(txjson), end_format='command')
        while True:
            rxData = receive_data(self.uart_obj)

            if rxData is not None and rxData[-1] == 'd':
                rxjson = ujson.loads(rxData[0])
                execution_status = rxjson.get('status')
                return rxjson.get('status')
            elif rxData is not None and rxData[-1] == 'o':
                print(rxData[0])


    @func_handler
    def subscribe(self, topic, qos=0):
        assert self.mqtt_connect_success, 'Device not connected to mqtt broker'
        sleep(0.1)
        # check if callback for specific topic is set
        assert self.cb.get(topic, None) is not None, f'Callback for {topic} is not set'
        # send subscribe command to esp
        txjson = {'action': ['mqtt_operation'], 'mqtt_operation': {'arg_available': True, 'argument': [{'operation': 'mqtt_subscribe', 'mqtt_subscribe': {'arg_available': True, 'argument': [self.target_ref, topic]}}]}}
        send_data(self.uart_obj, ujson.dumps(txjson), end_format='command')
        while True:
            rxData = receive_data(self.uart_obj)

            if rxData is not None and rxData[-1] == 'd':
                rxjson = ujson.loads(rxData[0])
                return rxjson.get('status')
            elif rxData is not None and rxData[-1] == 'o':
                print(rxData[0])


    # Checks whether a pending message from server is available.
    # Subscribed messages are delivered to a callback previously
    # set by .set_callback() method
    # If not, returns immediately with None
    exempt_function_dict['check_msg'] = ['on_success', 'on_failure']
    def check_msg(self):
        assert self.mqtt_connect_success, 'Device not connected to mqtt broker'
        sleep(0.1)
        # send message wait_msg command to esp
        # calls corresponding callback for a subscribed topic
        txjson = {'action': ['mqtt_operation'], 'mqtt_operation': {'arg_available': True, 'argument': [{'operation': 'mqtt_check_msg', 'mqtt_check_msg': {'arg_available': True, 'argument': [self.target_ref]}}]}}
        send_data(self.uart_obj, ujson.dumps(txjson), end_format='command')
        msg = None
        while True:
            rxData = receive_data(self.uart_obj)

            if rxData is not None and rxData[-1] == 'd':
                rxjson = ujson.loads(rxData[0])
                execution_status = rxjson.get('status')                

                if not execution_status:
                    # print(f'{self.check_msg.__name__} failed')
                    raise Exception(f'{self.check_msg.__name__} failed')
                elif execution_status:
                    print(f'{self.check_msg.__name__} succeeded')
                
                break
            elif rxData is not None and rxData[-1] == 'o':
                print(rxData[0])
            elif rxData is not None and rxData[-1] == 'j':
                msg = rxData[0]
        
        if msg is None:
            return None
        elif msg is not None:
            msg = ujson.loads(msg)
        
        # print(msg)
        self.cb.get(msg.get('topic', None), None)(msg.get('message', None))
        
        return msg


    # Checks whether a pending message from server is available.
    # Subscribed messages are delivered to a callback previously
    # set by .set_callback() method
    # If not, returns immediately with None
    exempt_function_dict['wait_msg'] = ['on_success', 'on_failure']
    def wait_msg(self):
        sleep(0.1)
        # send message wait_msg command to esp
        # calls corresponding callback for a subscribed topic
        txjson = {'action': ['mqtt_operation'], 'mqtt_operation': {'arg_available': True, 'argument': [{'operation': 'mqtt_wait_msg', 'mqtt_wait_msg': {'arg_available': True, 'argument': [self.target_ref]}}]}}
        send_data(self.uart_obj, ujson.dumps(txjson), end_format='command')
        msg = None
        while True:
            rxData = receive_data(self.uart_obj)

            if rxData is not None and rxData[-1] == 'd':
                rxjson = ujson.loads(rxData[0])
                execution_status = rxjson.get('status')                

                if not execution_status:
                    raise Exception(f'{self.wait_msg.__name__} failed')
                elif execution_status:
                    print(f'{self.wait_msg.__name__} succeeded')
                
                break
            elif rxData is not None and rxData[-1] == 'o':
                print(rxData[0])
            elif rxData is not None and rxData[-1] == 'j':
                msg = rxData[0]
        
        if msg is None:
            return None
        elif msg is not None:
            msg = ujson.loads(msg)
        
        # print(msg)
        self.cb.get(msg.get('topic', None), None)(msg.get('message', None))
        
        return msg


def update():
    w_led.value(0)
    w_led.value(1)
    sleep(0.25)
    w_led.value(0)
handler_dict['update'] = update

def blinky(t):
    try:
        w_led.toggle()
    except:
        t.deinit()

timer_standby = None
def standby():
    timeout_ms = 2000
    global timer_standby
    if timer_standby is None:
        timer_standby = Timer()        
    elif timer_standby is not None:
        timer_standby.deinit()
    timer_standby.init(mode=Timer.PERIODIC, freq=3, callback=blinky)
    t = ticks_ms()    
    while True:
        if ticks_diff(ticks_ms(), t) > timeout_ms:
            break
    timer_standby.deinit()
    w_led.value(0)
handler_dict['standby'] = standby


retry_dict['connect_to_wifi'] = {'retries': 2}
@func_handler
def connect_to_wifi(uart_obj, ssid, password, **kwargs):
    sleep(0.1)
    timeout_ms = kwargs.get('timeout_ms', 5000)
    execution_status = None
    
    txjson = {
        'action': ['connect_to_wifi'],
        'connect_to_wifi':{
            'arg_available': True,
            'argument': [ssid, password, timeout_ms]
        }
    }

    send_data(uart_obj, ujson.dumps(txjson), end_format='command')

    while True:
        rxData = receive_data(uart_obj)

        if rxData is not None and rxData[-1] == 'd':
            rxjson = ujson.loads(rxData[0])
            return rxjson.get('status')
        elif rxData is not None and rxData[-1] == 'o':
            print(rxData[0])


def mqtt_msg(uart_obj, topic, msg):
    print(f'topic: {topic} message: {msg}')


def target_ref(uart_obj, ref, target_ref):
    client_list[ref].target_ref = target_ref
    return True


retry_dict['set_time'] = {'retries': 2}
@func_handler
def set_time(uart_obj, rtc, utc_offset=3, **kwargs):
    sleep(0.1)
    utc_epoch = utc_offset * 60 * 60
    timeout_ms = kwargs.get('timeout_ms', 5000)
    execution_status = None
    
    txjson = {
        'action': ['get_ntp_time'],
        'get_ntp_time':{
            'arg_available': False,
        }
    }

    send_data(uart_obj, ujson.dumps(txjson), end_format='command')

    while True:
        rxData = receive_data(uart_obj)

        if rxData is not None and rxData[-1] == 'd':
            rxjson = ujson.loads(rxData[0])
            return rxjson.get('status')
        elif rxData is not None and rxData[-1] == 'o':
            print(rxData[0])
        elif rxData is not None and 'epoch' in rxData[0]:
            time_l = list(map(int, rxData[0].split(': ')[-1][1:-1].split(', ')))
            time_l[4] = (time_l[4] + utc_offset) % 24   # (year, month, day, weekday, h, m, s, sub_s)            
            rtc.datetime(tuple(time_l))


def sub_handler(f):
    def wrapper(*args, **kwargs):
        try:
            message_json = ujson.loads(args[0])
            user_id = message_json.get('user_id', None)
            device_user_id = device_details.get('user_id', ask=False)
            if user_id is None or device_user_id is None or user_id != device_user_id:
                return
            client_id = message_json.get('client_id', None)
            device_client_id =  device_details.get('mqtt_client_id', ask=False)
            if client_id is not None and device_client_id is not None and client_id != device_client_id:
                return
            broker_error = message_json.get('broker_error', None)

            if broker_error:
                print(f'Broker error: {broker_error}')
            
            f(*args, **kwargs)
        except Exception as e:
            print(f'Sub handler exception: {e}')
            return
    
    return wrapper
        

function_map['mqtt_msg'] =  mqtt_msg
mqtt_operation_map['mqtt_msg'] =  mqtt_msg
mqtt_operation_map['target_ref'] =  target_ref