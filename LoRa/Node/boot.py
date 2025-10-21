from machine import UART, Pin, I2C
from time import sleep, ticks_ms, ticks_diff

sleep(0.01) # Await I2C bus to settle

uart = UART(0, baudrate=115200, tx=Pin(0), rx=Pin(1))   # Initialize uart
led = Pin(12, Pin.OUT)
de_pin=Pin(17, Pin.OUT)
re_pin=Pin(16, Pin.OUT)

def flash_led(num_count):
    count = 0
    while count < num_count:
        led.on()
        sleep(0.1)
        led.off()
        sleep(0.1)
        count += 1


try:
    timeout_ms = 5000
    t = ticks_ms()
    while uart.any() > 0:
        if ticks_diff(ticks_ms(), t) < timeout_ms:
            raise Exception('Waiting for confirmation timed out')
        # read any bytes loaded to rp buffer due to ESP reset
        uart.read()
        sleep(0.1)  

    # Turn off relays, mosfets and esp
    i2c = I2C(0, scl=Pin(21), sda=Pin(20), freq=400000)
    while (len(i2c.scan()) == 0):
        flash_led(2)
    i2c.writeto(0x38, bytes([0b10000000]))

    # Inactivate modbus lines
    de_pin.value(0)
    re_pin.value(1)
    
except Exception as e:
    count = 0
    while count < 10:
        flash_led(2)
        print(f'Exception: {e}')    
        count += 1