# Author: Donatus
from machine import I2C, Pin


class PCF8574():
    i2c_address = 0x38
    i2c = I2C(0, scl=Pin(21), sda=Pin(20), freq=400000)
    x = 0 # will use this for bytes conversion

    def __init__(self):
        pass
    # p0 - mosfet1
    # p1 - mosfet2
    # p2 - mosfet3
    # p3 - relay2
    # p4 - relay1
    # p5 - relay3
    # p6 - modules_power
    # p7 - esp_en

    def read_pcf8574(self):
        bytes_input = self.i2c.readfrom(self.i2c_address, 1)
        string_input = bin(self.x.from_bytes(bytes_input, 'big'))
        bytes_input_len = len(string_input)

        if bytes_input_len < 10:
            string_input = f'{'0' * (10 - bytes_input_len)}{string_input[2:]}'
        elif bytes_input_len == 10:
            string_input = f'{string_input[2:]}'        

        return [int(i) for i in list(string_input)[::-1]]
    

    def write_pcf8574(self, expander_byte):
        self.i2c.writeto(self.i2c_address, expander_byte)
    

class PCF8574_PIN(PCF8574):
    # configuration. 1 is input and 0 is output
    IN = 1
    OUT = 0
    MOSFET1_PIN = 0
    MOSFET2_PIN = 1
    MOSFET3_PIN = 2
    RELAY1_PIN = 4
    RELAY2_PIN = 3
    RELAY3_PIN = 5
    MODULES_POWER_PIN = 6
    ESP_EN_PIN = 7
    PIN_LIST = (MOSFET1_PIN, MOSFET2_PIN, MOSFET3_PIN, RELAY1_PIN, RELAY2_PIN, RELAY3_PIN, MODULES_POWER_PIN, ESP_EN_PIN)

    def __init__(self, position, configuration=OUT):
        self.position = position
        self.configuration = configuration
    

    @property
    def position(self):
        return self._position
    

    @position.setter
    def position(self, position_set):
        assert position_set in PCF8574_PIN.PIN_LIST, 'Invalid pin number'
        self._position = position_set


    @property
    def configuration(self):
        return self._configuration
    
    @configuration.setter
    def configuration(self, configuration_set):
        assert configuration_set == PCF8574_PIN.IN or configuration_set == PCF8574_PIN.OUT, 'Pin configuration must be either PCF8574_PIN.IN or PCF8574_PIN.OUT'
        self._configuration = configuration_set
    

    def read_pin(self):
        return int(not self.read_pcf8574()[self.position]) if self.position == PCF8574_PIN.MODULES_POWER_PIN else self.read_pcf8574()[self.position]
    

    def write_pin(self, pin_value):  
        expander_byte = 0      
        for ind, i in enumerate(self.read_pcf8574()):
            if ind == self.position:
                expander_byte += (pin_value * (2**ind))
            elif ind != self.position:
                expander_byte += (i * (2**ind))
        
        self.write_pcf8574(bytes([expander_byte]))
    

    def value(self, pin_value=None):
        pin_configuration = self.configuration
        if pin_value is not None and pin_configuration == PCF8574_PIN.IN:
            raise Exception('Cannot set value of input pin')
        
        if pin_configuration == PCF8574_PIN.IN:
            return self.read_pin()
        elif pin_configuration == PCF8574_PIN.OUT:
            if pin_value is None:
                return self.read_pin()
        
            elif pin_value is not None:
                assert pin_value == 0 or pin_value == 1, 'Pin value must be either 0 or 1'
                if self.position == PCF8574_PIN.MODULES_POWER_PIN:
                    pin_value = not pin_value
                self.write_pin(pin_value)
    
    def toggle(self):
        assert self.configuration == PCF8574_PIN.OUT, 'Cannot toggle value of input pin'
        self.write_pin(not self.read_pin())
    

    mosfet_name_pin_map = {'mosfet1': MOSFET1_PIN, 'mosfet2': MOSFET2_PIN, 'mosfet3': MOSFET3_PIN}
    relay_name_pin_map = {'relay1': RELAY1_PIN, 'relay2': RELAY2_PIN, 'relay3': RELAY3_PIN}        