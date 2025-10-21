# Author: Donatus
# This script holds functions that enable execution of any commands called by the sending device
import ujson
from uartlib import *
from machine import UART

retry_dict = {} # a dictionary to map function to its number of retries if it fails
function_map = {}   # a dictionary to map command received to a function to be executed
mqtt_operation_map = {} # a dictionary to map mqtt command received to a mqtt function to be executed
handler_dict = {} # a dictionary to map terms to functions
exempt_function_dict = {}  # a dict to hold functions exempted from handling on success or failure

def func_handler(func):
    def wrapper(*args, **kwargs):
        debug_func = kwargs.get('debug_func', False)
        uart_obj = kwargs.get('uart_obj', None)
        # look to find if there is a uart object in args if it is not in kwargs
        if uart_obj is None:
            for x in args:
                if type(x) is UART:
                    uart_obj = x
        
        func_retry_dict = retry_dict.get(f'{func.__name__}', None)
        retries = 0

        if func_retry_dict is not None:
            retries = func_retry_dict.get('retries', 0)

        if 'debug_func' in kwargs:
            del kwargs['debug_func']
        
        if 'uart_obj' in kwargs:
            del kwargs['uart_obj']
        
        try:
            execution_status = func(*args, **kwargs)
            sleep(0.1)
            if not execution_status:
                print_s(uart_obj, f'{func.__name__} failed.{' Trying again...' if retries > 0 else ''}')
        except Exception as e:
            print_s(uart_obj, f'{func.__name__} failed with error: {e}.{' Trying again...' if retries > 0 else ''}')
            execution_status = False

        while not execution_status and retries:
            try:
                execution_status = func(*args, **kwargs, **func_retry_dict.get('other_args', {}))
                sleep(0.1)
                if not execution_status:
                    print_s(uart_obj, f'{func.__name__} failed.{' Trying again...' if retries > 0 else ''}')

            except Exception as e:
                sleep(0.1)
                print_s(uart_obj, f'{func.__name__} failed with error: {e}.{' Trying again...' if retries > 0 else ''}')
                execution_status = False

            retries -= 1
        
        if execution_status:
            if debug_func:
                print_s(uart_obj, f'{func.__name__} succeeded')
            if os.uname().sysname == 'rp2':
                if exempt_function_dict.get(f'{func.__name__}', None) is None:
                    handler_dict.get('update')()
                elif exempt_function_dict.get(f'{func.__name__}', None) is not None:
                    if 'on_success' not in exempt_function_dict.get(f'{func.__name__}'):
                        handler_dict.get('update')()
        elif not execution_status:                        
            if os.uname().sysname == 'esp8266':
                if debug_func:
                    print_s(uart_obj, f'{func.__name__} failed')
                raise Exception(f'{func.__name__} failed')
            elif os.uname().sysname == 'rp2':
                if exempt_function_dict.get(f'{func.__name__}', None) is None:
                    handler_dict.get('standby')()
                elif exempt_function_dict.get(f'{func.__name__}', None) is not None:
                    if 'on_failure' not in exempt_function_dict.get(f'{func.__name__}'):
                        handler_dict.get('standby')()
                    elif 'on_failure' in exempt_function_dict.get(f'{func.__name__}'):
                        raise Exception(f'{func.__name__} failed')
            
        
        return execution_status
    
    return wrapper


def process_command(uart_obj, rxData):
    sleep(0.01)
    rxjson = ujson.loads(rxData)
    f_list = rxjson.get('action', None)
    execution_list = []

    if f_list is None:
        return None
    
    for i in f_list:
        f_found = function_map.get(i, None)

        if f_found is None:            
            print_s(uart_obj, f'{os.uname().sysname.upper()}: Function {i} not found')
            execution_list.append(False)
            continue
        
        f_argument = rxjson.get(i).get('arg_available')
        
        try:
            if f_argument:
                # print(rxjson.get(i).get('argument'))
                if f_found(uart_obj, *rxjson.get(i).get('argument')):
                    execution_list.append(True)
                else:
                    execution_list.append(False)
            elif not f_argument:
                if f_found(uart_obj):
                    execution_list.append(True)
                else:
                    execution_list.append(False)
        
        except Exception as e:
            print_s(uart_obj, f'{os.uname().sysname.upper()} Error: {e}')
            execution_list.append(False)
    
    execution_status = False not in execution_list
    
    txjson = {'status': execution_status, 'status_list': execution_list}
    # print(ujson.dumps(txjson))
    sleep(0.01)
    send_data(uart_obj, ujson.dumps(txjson), end_format='command_execution')
    return True


def mqtt_operation(uart_obj, params):
    f_found = mqtt_operation_map.get(params.get('operation', None), None)

    if f_found is None:            
        return None
        
    f_argument = params.get(params.get('operation')).get('arg_available')
    
    if f_argument:
        if f_found(uart_obj, *params.get(params.get('operation')).get('argument')):
            # print(f'{params.get('operation')} done')
            return True
        else:
            return False
    elif not f_argument:
        if f_found(uart_obj):
            return True
        else:
            return False


function_map['mqtt_operation'] =  mqtt_operation