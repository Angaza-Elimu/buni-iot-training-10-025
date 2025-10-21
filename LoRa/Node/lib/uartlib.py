# Author: Donatus
from time import sleep, ticks_ms, ticks_diff
from machine import Timer, Pin
import os

if os.uname().sysname == 'rp2':
    from pcf8574 import *

## process_txData - adds formatting character to raw txData
# txData - raw txData to be processed
# Return: processed txData
def process_txData(txData, retain_bytes, end_format, packet_end):
    if retain_bytes:
        txData = b'b' + txData + b'b' + packet_end
    elif not retain_bytes:
        txData = b's' + txData

        if end_format == 'command':
            txData = txData + 'c' + packet_end
        elif end_format == 'command_execution':
            txData = txData + 'd' + packet_end
        elif end_format == 'json':
            txData = txData + 'j' + packet_end
        elif end_format == 'esp_output':
            txData = txData + 'o' + packet_end
        elif end_format == 'string':
            txData = txData + 's' + packet_end
    
    return txData


##
# send_data_basic - sends data over uart
# uart_obj - uart object to be used
# txData - txData to be sent, bytes or string
# Return: "received all" or "waiting next" or None
def send_data_basic(uart_obj, txData, **kwargs):
    retain_bytes = kwargs.get('retain_bytes', False)
    jump_receive = kwargs.get('jump_receive', False)
    timeout_ms = kwargs.get('timeout_ms', 2000)
    # print(f"Send data called: {txData} jump_receive: {jump_receive}")
    if retain_bytes:
        uart_obj.write(txData)

    elif not retain_bytes:
        uart_obj.write(bytes(txData, 'utf-8'))
    
    if not jump_receive:        
        t = ticks_ms()
        while uart_obj.any() == 0:
            sleep(0.0001)
            if ticks_diff(ticks_ms(), t) > timeout_ms:
                raise Exception('Waiting for confirmation timed out')

        rx_temp = receive_data(uart_obj)
        # print(f'rx_temp: {rx_temp}')
        if rx_temp is None:
            raise Exception("Error in receiving confirmation")
        elif rx_temp is not None:
            return rx_temp[0]
    elif jump_receive:
        return b'received all' if retain_bytes else "received all" 


##
# send_data - sends data over uart
# uart_obj - uart object to be used
# txData - txData to be sent, bytes or string
# Return: "send success" or "send fail" or None
# Description - if txData is greater than max_char
# it will break the txData into lengths max_char long
# and send them one at a time
def send_data(uart_obj, txData, **kwargs):
    max_char = kwargs.get('max_char', None)
    if max_char is None:
        max_char = 285 if os.uname().sysname == 'esp8266' else 12
    end_format = kwargs.get('end_format', 'string')
    retain_bytes = type(txData) is bytes
    txlen = len(txData)
    received_final = None
    jump_receive = False

    if not retain_bytes and (txData == "received all" or txData == "waiting next"):
        jump_receive = True
    elif retain_bytes and (txData == b'received all' or txData == b'waiting next'):
        jump_receive = True
    
    if txlen <= max_char:
        packet_end = b'e' if retain_bytes else 'e'
        txData = process_txData(txData, retain_bytes, end_format, packet_end)
        received_final = send_data_basic(uart_obj, txData, retain_bytes=retain_bytes, jump_receive=jump_receive)
        
    elif txlen > max_char:
        # send data in packets
        x = max_char
        rem_char = txlen - max_char
        packet_end = 'c'
        temp_tx = process_txData(txData[x - max_char: max_char], retain_bytes, end_format, packet_end)
        received_final = send_data_basic(uart_obj, temp_tx, retain_bytes=retain_bytes)

        while (received_final == "waiting next" or received_final == b'waiting next') and rem_char > max_char:
            x += max_char
            rem_char -= max_char
            packet_end = 'c'
            temp_tx = process_txData(txData[x - max_char: x], retain_bytes, end_format, packet_end)
            received_final = send_data_basic(uart_obj, temp_tx, retain_bytes=retain_bytes)
            # print(f'received_final: {received_final}')
            sleep(0.001)
        
        if (received_final == "waiting next" or received_final == b'waiting next') and rem_char <= max_char:
            packet_end = 'e'
            temp_tx = process_txData(txData[x: x + rem_char], retain_bytes, end_format, packet_end)
            received_final = send_data_basic(uart_obj, temp_tx, retain_bytes=retain_bytes)
            # print(f'received_final end: {received_final}')
        
        elif received_final is None or received_final != "waiting next" or received_final != b'waiting next':
            # print(f'Error, received_final: {received_final}')
            raise Exception("Problem in sending data packet by packet")
    
    # print(f'Elif exited received_final: {received_final}')
    if received_final == "received all" or received_final == b'received all':
        return "send success"
    
    return None


## receive_data_basic - receives data over uart
# Return: a list with the received data and the end format or None
def receive_data_basic(uart_obj):
    rxData = None
    if uart_obj.any() > 0:
        rxData = uart_obj.read()
    elif uart_obj.any() < 0:
        return None
    
    if rxData is None or rxData == b'\x00':
        return None
    
    # print(f'Receive data called: {rxData} rxstate: {uart_obj.any()}')
    try:
        retain_bytes = chr(rxData[0]) == 'b'
        end_format = chr(rxData[-2])
        packet_end = chr(rxData[-1]) == 'e'
    
    except:
        raise Exception("Unicode error. Sending device has possibly restarted or connection has been made while receiving")
    
    # Due to Thonny adding \r\n sESP: Stopse will be sESP: Stopse\r\n
    if os.uname().sysname == 'esp8266':
        if not retain_bytes and 'ESP: Stop' in rxData[1:]:
            send_data(uart_obj, "received all")
            return [b'ESP: Stop', retain_bytes, 's', True]

    if packet_end:        
        if not retain_bytes and rxData[1:-2].decode('utf-8') != "received all" and rxData[1:-2].decode('utf-8') != "waiting next":            
            send_data(uart_obj, "received all")
        elif retain_bytes and rxData[1:-2] != b'received all' and rxData[1:-2] != b'waiting next':            
            send_data(uart_obj, b'received all')
    
    elif not packet_end:
        if not retain_bytes:
            send_data(uart_obj, "waiting next")
        elif retain_bytes:
            send_data(uart_obj, b'waiting next')
    
    temp_rx = rxData[1:-2]

    return [temp_rx, retain_bytes, end_format, packet_end]


## receive_data - reads data on the rx buffer
# Return: a list with the received data and the end format or None
def receive_data(uart_obj, **kwargs):
    timeout_ms = kwargs.get('timeout_ms', 2000)
    rxDatalist = receive_data_basic(uart_obj)
    if rxDatalist is None:
        return None
    
    rxData, retain_bytes, end_format, packet_end = rxDatalist
    # print(f'first receive: {rxData} packet end: {packet_end} end_format: {end_format}')    
    
    while not packet_end:        
        # may need to wait for a certain timeout
        # sleep isn't the best
        t = ticks_ms()
        while uart_obj.any() == 0:
            sleep(0.0001)
            if ticks_diff(ticks_ms(), t) > timeout_ms:
                raise Exception('Waiting for receive timed out')
        rxDatalist = receive_data_basic(uart_obj)
        # print(f'in not packet end, rxDatalist: {rxDatalist}')

        if rxDatalist is None:
            return None
        
        temp_rx, retain_bytes, end_format, packet_end = rxDatalist
        # print(f'temp receive: {temp_rx}')
        rxData += temp_rx

    if retain_bytes:
        return [rxData, end_format]
    
    elif not retain_bytes:
        return [rxData.decode('utf-8'), end_format]


def uart_config(uart_obj):
    x_led = Pin(12, Pin.OUT)
    esp_enable_pin = PCF8574_PIN(PCF8574_PIN.ESP_EN_PIN, PCF8574_PIN.OUT)
    print('Setting up ESP')
    # reset esp
    esp_enable_pin.value(0)
    sleep(0.1)
    esp_enable_pin.value(1)
    # wait until boot up data is available on buffer
    while uart_obj.any() == 0:
        sleep(0.01)
    # read any bytes loaded to rp buffer due to ESP boot
    while uart_obj.any() > 0:
        uart_obj.read()
        sleep(0.1)
    sleep(2)
    
    try:
        send_data(uart_obj, 'ESP Ready?')
        sleep(0.1)
        
        if receive_data(uart_obj)[0] == 'ESP: Ready':
            x_led.off()
            return          
    except:
        if uart_obj.any() > 0:
            uart_obj.read()
        x_led.on()
        # print("Press ESP reset button")

        while uart_obj.any() == 0:
            sleep(0.01)
        # read any bytes loaded to rp buffer due to ESP reset
        while uart_obj.any() > 0:
            uart_obj.read()
            sleep(0.1)        
        timer_x = Timer()
        timer_x.init(mode=Timer.PERIODIC, freq=1, callback=progress_bar)
        sleep(2)
        send_data(uart_obj, 'ESP Ready?')
        sleep(0.1)
        if receive_data(uart_obj)[0] == 'ESP: Ready':
            timer_x.deinit()
            x_led.off()
            return


def esp_sleep(uart_obj):
    uart_config(uart_obj)
    send_data(uart_obj, 'ESP: Sleep')
    return


def progress_bar(t):
    print('.', end='')


def print_s(uart_obj, s, **kwargs):
    if os.uname().sysname == 'esp8266':
        if uart_obj is None:
            raise Exception('Uart object is None')
        sleep(0.01)
        send_data(uart_obj, s, end_format='esp_output')
    elif os.uname().sysname == 'rp2':
        print(s, **kwargs)