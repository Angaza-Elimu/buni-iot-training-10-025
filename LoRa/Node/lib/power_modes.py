from pcf8574 import *
from time import sleep
import picosleep
from machine import Pin

# main things
# put esp to sleep
# power off sensors
# power off rs485
esp_enable_pin = PCF8574_PIN(PCF8574_PIN.ESP_EN_PIN, PCF8574_PIN.OUT)
modules_pin = PCF8574_PIN(PCF8574_PIN.MODULES_POWER_PIN, PCF8574_PIN.OUT)
npk_power_pin = PCF8574_PIN(PCF8574_PIN.MOSFET3_PIN, PCF8574_PIN.OUT)
rs485_de_pin = Pin(17, Pin.OUT)
rs485_re_pin = Pin(16, Pin.OUT)


def hibernate(duration, f_list=None):
    assert 10 <= duration, 'Hibernate period must be greater than 10'
    sleep_duration = duration - 5
    initial_esp_value = esp_enable_pin.value()
    initial_modules_value = modules_pin.value()
    initial_de_value = rs485_de_pin.value()
    initial_re_value = rs485_re_pin.value()
    esp_enable_pin.value(0)
    modules_pin.value(0)
    npk_power_pin.value(0)
    rs485_de_pin.value(0)
    rs485_re_pin.value(1)
    
    if sleep_duration >= 60:
        while sleep_duration >= 60:
            picosleep.seconds(59)
            sleep_duration -= 59
    
    picosleep.seconds(sleep_duration)
    esp_enable_pin.value(initial_esp_value)
    modules_pin.value(initial_modules_value)
    rs485_de_pin.value(initial_de_value)
    rs485_re_pin.value(initial_re_value)
    npk_power_pin.value(1)
    picosleep.seconds(5)
    

def power_off_peripherals():
    esp_enable_pin.value(0)
    rs485_de_pin.value(0)
    rs485_re_pin.value(1)


def power_off_esp():
    esp_enable_pin.value(0)