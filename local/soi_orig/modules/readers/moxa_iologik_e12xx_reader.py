#!/usr/bin/env python3

import logging
import requests
import sys
import json
from time import sleep, time

from os.path import dirname, realpath
sys.path.append(dirname(dirname(dirname(dirname(realpath(__file__))))))
from logger.readers.reader import Reader  # noqa: E402
from logger.utils.formats import Text  # noqa: E402

READ_BUFFER_SIZE = 4096  # max number of characters to read in one call
HEADERS = {'Accept': 'vdn.dac.v1', 'Content-Type': 'application/json'}
API_ROOT = "/api/slot/0"

################################################################################
# Read to the specified file. If filename is empty, read to stdout.
class MOXAioLogikE12xxReader(Reader):
    """
    Read data from a MOXA ioLogik E12xx devices via the device's RESTful API.

    """
    ############################

    def __init__(self, address, polling_rate=1, timeout=0.1,
                 analog_channels='0,1,2,3', encoding='utf-8',
                 encoding_errors='ignore'):
        """
        ```
        address      Network address to read, in host:port format (e.g.
                     '192.168.127.254' '192.168.127.254:8000'). If port is
                     omitted (e.g. ':6202'), read via UDP on specified port.

        polling_rate Seconds between update requests to MOXA Device

        timeout      Max time to wait for device to respond.

        analog_channels The analog channels to poll.

        encoding - 'utf-8' by default. If empty or None, do not attempt any decoding
                and return raw bytes. Other possible encodings are listed in online
                documentation here:
                https://docs.python.org/3/library/codecs.html#standard-encodings

        encoding_errors - 'ignore' by default. Other error strategies are 'strict',
                'replace', and 'backslashreplace', described here:
                https://docs.python.org/3/howto/unicode.html#encodings
        ```
        """
        super().__init__(output_format=Text,
                         encoding=encoding,
                         encoding_errors=encoding_errors)

        self.address = address
        self.polling_rate = polling_rate
        self.timeout = timeout
        self.analog_channels = [int(i) for i in analog_channels.split(',')]
        self.last_get_time = 0

        # test that the device is present.
        try:
            res = requests.get('http://' + self.address + API_ROOT + '/sysInfo/device',
                               headers=HEADERS,
                               timeout=self.timeout,
                              )
        except Exception as err:
            logging.debug(str(err))
            raise AttributeError('Problem connecting to device at: %s', self.address)

        if res.status_code == 404:
            raise AttributeError('Unable to connect to device at: %s', self.address)

        logging.debug(res.content)

    ############################
    def read(self):
        """
        Query the API for new data.
        """

        url = 'http://' + self.address + API_ROOT + '/io/ai'

        while True:

            # Wait the timeout or for a keyboard interrupt, whichever comes
            # first.
            try:
                wait_time  = time() - self.last_get_time
                if wait_time < self.polling_rate:
                    sleep(self.polling_rate - wait_time)
            
            except KeyboardInterrupt:
                logging.warning('Keyboard interrupt recieved, quitting.')
                return

            except:
                pass

            self.last_get_time = time()
            # Retrieve the data
            try:
                res = requests.get(url,
                                   headers=HEADERS,
                                   timeout=self.timeout,
                                  )

                if res.status_code == 200:
                    # {"slot":0,"io":{"ai":[{"aiIndex":0,"aiMode":0,"aiValueRaw":26,"aiValueScaled":0.003967,"aiValueRawMin":0,"aiValueRawMax":12345,"aiValueScaledMin":0,"aiValueScaledMax":1.883726,"aiResetMinValue":0,"aiResetMaxValue":0,"aiStatus":0,"aiBurnoutValue":2},{"aiIndex":1,"aiMode":0,"aiValueRaw":5516,"aiValueScaled":0.841688,"aiValueRawMin":0,"aiValueRawMax":29519,"aiValueScaledMin":0,"aiValueScaledMax":4.504311,"aiResetMinValue":0,"aiResetMaxValue":0,"aiStatus":0,"aiBurnoutValue":2},{"aiIndex":2,"aiMode":0,"aiValueRaw":525,"aiValueScaled":0.08011,"aiValueRawMin":0,"aiValueRawMax":4487,"aiValueScaledMin":0,"aiValueScaledMax":0.684672,"aiResetMinValue":0,"aiResetMaxValue":0,"aiStatus":0,"aiBurnoutValue":2},{"aiIndex":3,"aiMode":0,"aiValueRaw":133,"aiValueScaled":0.020294,"aiValueRawMin":0,"aiValueRawMax":767,"aiValueScaledMin":0,"aiValueScaledMax":0.117037,"aiResetMinValue":0,"aiResetMaxValue":0,"aiStatus":0,"aiBurnoutValue":2}]}}
                    logging.debug(f'Raw Output: {res.content}')
                    response_json = json.loads(res.content)

                    # cull out the slots we care about
                    return_channels = [response_json['io']['ai'][i] for i in self.analog_channels]
                    logging.debug(f'Returned channels: {return_channels}')
                    # {"aiIndex":0,"aiMode":0,"aiValueRaw":26,"aiValueScaled":0.003967,"aiValueRawMin":0,"aiValueRawMax":12345,"aiValueScaledMin":0,"aiValueScaledMax":1.883726,"aiResetMinValue":0,"aiResetMaxValue":0,"aiStatus":0,"aiBurnoutValue":2}

                    # output = [f"{channel['aiIndex']},{channel['aiMode']},{channel['aiValueRaw']},{channel['aiValueScaled']}" for channel in return_channels]
                    return [f"{channel['aiIndex']},{channel['aiMode']},{channel['aiValueRaw']},{channel['aiValueScaled']}" for channel in return_channels]

            except KeyboardInterrupt:
                logging.warning('Keyboard interrupt recieved, quitting.')
                return

            except Exception as err:
                logging.warning('Problem retrieving data from device: %s', self.address)
                logging.debug("URL: %s", url)
                logging.debug(str(err))
