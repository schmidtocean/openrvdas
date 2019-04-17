#!/usr/bin/env python3
"""LoggerManagers get their desired state of the world via a ServerAPI
instance and attempt to start/stop loggers with the desired configs
by dispatching requests to a local LoggerRunner and/or any remote
LoggerRunners connected via websocket.

To run the LoggerManager from the command line with (using the default
of an InMemoryServerAPI):

  server/logger_manager.py

If an initial configuration is specified on the command line, as
below:

  server/logger_manager.py --config test/configs/sample_cruise.yaml

the configuration will be loaded and set to its default mode. If a
--mode argument is included, it will be used in place of the default
mode.

If the LoggerManager is created with a websocket specification
(host:port), it will accept connections from LoggerRunners. It
expects the LoggerRunners to identify themselves with a host_id, and
will dispatch any configs listing that host_id to the appropriate
LoggerRunner. Configs that have no host_id specified will continue to
be dispatched to the local LoggerRunner; configs specifying a host_id
that doesn't match any connected LoggerRunner will not be run:

  server/logger_manager.py --websocket localhost:8765

A LoggerRunner that would connect to the above LoggerManager could be
launched via:

  server/logger_runner.py --websocket localhost:8765 \
      --host_id knud.host

By default, the LoggerManager will initialize a command line API that
reads from stdin. If logger_manager.py is to be run in a context
where stdin is not available (i.e. as part of a script), then it
should be called with the --no-console flag.

The -v flag may be specified on any of the above command lines to
increase diagnostic verbosity to "INFO". Repeating the flag sets
verbosity to "DEBUG".

For the LoggerManager and LoggerRunner, the -V (capitalized) flag
increases verbosity of the loggers being run.

Typing "help" at the command prompt will list available commands.

#######################################################
To try out the scripts, open four(!) terminal windows.

1. In the first terminal, start the LoggerManager with a websocket server:

   server/logger_manager.py --websocket localhost:8765 -v

2. In a second terminal, start a LoggerRunner that will try to connect
   to the websocket on the LoggerManager you've started.

   server/logger_runner.py --websocket localhost:8765 \
         --host_id knud.host -v

   Note that this LoggerRunner is identifies its host as "knud.host";
   if you look at test/configs/sample_cruise.yaml, you'll notice that
   the configs for the "knud" logger have a host restriction of
   "knud.host", meaning that our LoggerManager should try to dispatch
   those configs to this LoggerRunner.

3. The sample configuration that we're going to load and run is
   configured to read from simulated serial ports. To create those
   simulated ports and start feeding data to them, use a third
   terminal window to run:

   logger/utils/simulate_serial.py --config test/serial_sim.yaml -v

4. Finally, we'd like to be able to easily glimpse the data that the
   loggers are producing. The sample configuration tells the loggers
   to write to UDP port 6224 when running, so use the fourth terminal
   to run a Listener that will monitor that port. The '-' filename
   tells the Listener to write to stdout (see listen.py --help for all
   Listener options):

   logger/listener/listen.py --network :6224 --write_file -

5. Whew! Now try a few commands in the terminal running the
   LoggerManager (you can type 'help' for a full list):

   # Load a cruise configuration

   command? load_configuration test/configs/sample_cruise.yaml

   # Change cruise modes

   command? get_modes
     Modes for NBP1700: off, port, underway

   command? set_active_mode port
     (You should notice data appearing in the Listener window.)

   command? set_active_mode underway
     (You should notice more data appearing in the Listener window, and
      the LoggerRunner in the second window should leap into action.)

   command? set_active_mode off

   # Manually change logger configurations

   command? get_loggers
     Loggers: knud, gyr1, mwx1, s330, eng1, rtmp

   command? get_logger_configs s330
     Configs for s330: s330->off, s330->net, s330->file/net/db

   command? set_active_logger_config s330 s330->net

   command? set_active_mode off

   command? quit

   When setting the mode to port, you should notice data appearing in
   the listener window, and should see diagnostic output in the
   LoggerManager window.

   When setting the mode to underway, you should see more data
   appearing in the listener window (due to more logger configs
   running), and should see the LoggerRunner leap into action as the
   LoggerManager dispatches the configs for "knud.host" to it.

"""
import asyncio
import getpass  # to get username
import json
import logging
import os
import pprint
import queue
import signal
import socket  # to get hostname
import sys
import threading
import time
from urllib.parse import unquote
import websockets

from os.path import dirname, realpath; sys.path.append(dirname(dirname(realpath(__file__))))

from logger.utils.read_config import read_config
from logger.utils.stderr_logging import setUpStdErrLogging, StdErrLoggingHandler
from logger.writers.text_file_writer import TextFileWriter
from logger.writers.network_writer import NetworkWriter
from server.server_api import ServerAPI
from server.logger_runner import LoggerRunner
#from server.data_server import DataServer

# Number of times we'll try a failing logger before giving up
DEFAULT_MAX_TRIES = 3

SOURCE_NAME = 'LoggerManager'
USER = getpass.getuser()
HOSTNAME = socket.gethostname()

############################
def kill_handler(self, signum):
  """Translate an external signal (such as we'd get from os.kill) into a
  KeyboardInterrupt, which will signal the start() loop to exit nicely."""
  raise KeyboardInterrupt('Received external kill signal')

############################
class WriteToAPILoggingHandler(logging.Handler):
  """Allow us to save Python logging.* messages to API backing store."""
  def __init__(self, api):
    super().__init__()

    API_LOGGING_FORMAT = '%(filename)s:%(lineno)d %(message)s'    
    self.api = api
    self.formatter = logging.Formatter(API_LOGGING_FORMAT)

  def emit(self, record):
    self.api.message_log(source='Logger', user='(%s@%s)' % (USER, HOSTNAME),
                         log_level=record.levelno,
                         message=self.formatter.format(record))

################################################################################
class LoggerManager:
  ############################
  def __init__(self, api=None, websocket=None, broadcast_status=None,
               host_id=None, interval=0.5, max_tries=3,
               logger_log_level=logging.WARNING):
    """Read desired/current logger configs from Django DB and try to run the
    loggers specified in those configs.

    api - ServerAPI (or subclass) instance by which LoggerManager will get
          its data store updates

    websocket - optional host:port on which to open a websocket server
          for LoggerRunners to connect to for dispatches of logger
          configs they should run.

    broadcast_status - 'Network port on which to broadcast logger status
          updates. If cruise configuration includes a display server, this
          should match the port monitored by that server, so that clients
          can receive status updates.

    host_id - optional id by which we identify ourselves. Tasks that
          include a "host_id" specification will only be dispatched to
          the matching host. For now, all tasks without a host_id
          specification will be run on the local machine.

    interval - number of seconds to sleep between checking/updating loggers

    max_tries - number of times to try a failed server before giving up

    logger_log_level - At what logging level our component loggers
          should operate.
    """
    # Set signal to catch SIGTERM and convert it into a
    # KeyboardInterrupt so we can shut things down gracefully.
    try:
      signal.signal(signal.SIGTERM, kill_handler)
    except ValueError:
      logging.warning('LoggerManager not running in main thread; '
                      'shutting down with Ctl-C may not work.')

    # api class must be subclass of ServerAPI
    if not issubclass(type(api), ServerAPI):
      raise ValueError('Passed api "%s" must be subclass of ServerAPI' % api)
    self.api = api
    self.host_id = host_id or None
    self.interval = interval
    self.max_tries = max_tries
    self.logger_log_level = logger_log_level

    # Have we been given a network port on which to broadcast status updates?
    if broadcast_status:
      self.status_writer = NetworkWriter(broadcast_status)
    else:
      self.status_writer = None

    self.quit_flag = False

    # Keep track of old configs so we only send updates to the
    # LoggerRunners when things change.
    self.old_configs = {}
    self.config_lock = threading.Lock()

    self.update_configs_thread = None

    # Has caller directed us to launch a Websocket server where other
    # LoggerRunners can connect?
    self.websocket = websocket

    # If so, we're going to want to make sure it and our LoggerRunner
    # (run in a separate thread) can use the same event loop
    self.event_loop = asyncio.get_event_loop()

    # Websocket-related stuff below. Client_id 0 refers to our local
    # LoggerRunner process, which we manage in a separate thread.
    self.client_map_lock = threading.Lock()
    self.next_client_id = 1  # id we will assign to next client that connects
    self.client_map = {}     # client_id -> websocket
    self.host_id_map = {}    # client_id -> host name, if we have it
    self.send_queue = {}     # client_id->queue for messages to send to ws
    self.receive_queue = {}  # client_id->queue for messages received from ws

    # LoggerRunners attached via /logger_runner path. We'll send them
    # configurations and read status updates from them.
    self.logger_runner_clients = set()

  ############################
  def start(self):
    """Start the threads that make up the LoggerManager operation: a local
    LoggerRunner, the configuration update loop and optionally, a
    websocket server that remote LoggerRunners and web clients can
    connect to. Start all threads as daemons so that they'll
    automatically terminate if the main thread does.
    """
    # Start the local LoggerRunner in its own thread.
    local_logger_thread = threading.Thread(
      target=self.local_logger_runner, daemon=True)
    local_logger_thread.start()

    # Update configs in a separate thread.
    self.update_configs_thread = threading.Thread(
      target=self.update_configs_loop, daemon=True)
    self.update_configs_thread.start()

    # If broadcasting our status, start doing that in a separate thread.
    if self.status_writer:
      self.broadcast_status_thread = threading.Thread(
        target=self._broadcast_status_loop, daemon=True)
      self.broadcast_status_thread.start()

    # If we've got a websocket specification, launch websocket
    # server in its own separate thread.
    if self.websocket:
      try:
        host, port_str = self.websocket.split(':')
        if not host:
          host = '0.0.0.0'
        self.websocket_server = websockets.serve(self._serve_websocket,
                                                 host, int(port_str))
        self.event_loop.run_until_complete(self.websocket_server)
        event_loop_thread = threading.Thread(target=self.event_loop.run_forever,
                                             daemon=True)
        event_loop_thread.start()
      except OSError:
        logging.warning('Failed to open websocket %s:%s', host, port_str)
        sys.exit(1)
      except ValueError as e:
        logging.error('--websocket "%s" not in host:port format',
                      self.websocket)
        sys.exit(1)

  ############################
  def quit(self):
    """Exit the loop and shut down all loggers."""
    self.quit_flag = True
    self.logger_runner.quit()

  ##########################
  def local_logger_runner(self):
    """Create and run a local LoggerRunner as client_id 0."""
    client_id = 0
    with self.client_map_lock:
      self.host_id_map[client_id] = self.host_id
      self.send_queue[client_id] = queue.Queue()
      self.receive_queue[client_id] = queue.Queue()
      self.logger_runner_clients.add(client_id)

    # Some of the loggers may require an event loop. We're running in
    # a separate thread, so we need to explicitly set our event loop,
    # using the one we stored during init().
    self.logger_runner = LoggerRunner(max_tries=self.max_tries,
                                      event_loop=self.event_loop,
                                      logger_log_level=self.logger_log_level)
    # Instead of calling the LoggerRunner.run(), we iterate ourselves,
    # checking whether there are commands we want to push to the
    # LoggerRunner and doing updates to retrieve status reports.
    while not self.quit_flag:
      try:
        message = self.send_queue[client_id].get_nowait()
        if message.strip():
          logging.debug('Got message: %s', message.strip())
          self.logger_runner.parse_command(message)
      except queue.Empty:
        logging.debug('No messages for local LoggerRunner')
      except ValueError:
        pass

      status = self.logger_runner.check_loggers(manage=True, clear_errors=False)
      message = {'status': status}
      self._process_logger_runner_message(client_id, message)

      time.sleep(self.interval)

  ############################
  @asyncio.coroutine
  async def _serve_websocket(self, websocket, path):
    """Serve requests from clients who connect to us via websocket."""

    with self.client_map_lock:
      client_id = self.next_client_id
      self.next_client_id += 1

      logging.info('New client #%d attached: %s', client_id, path)
      self.client_map[client_id] = websocket
      self.send_queue[client_id] = queue.Queue()
      self.receive_queue[client_id] = queue.Queue()

    # Remote LoggerRunner has connected. Its "producer" is simple: we
    # just send it whatever is in its send_queue. Its consumer is a
    # little more complicated, as we want to process what we've
    # received as soon as we get it.
    if path.find('/logger_runner/') == 0:
      host_id = unquote(path[len('/logger_runner/'):])
      logging.info('New LoggerRunner %s, (id #%d)', host_id, client_id)
      with self.client_map_lock:
        self.logger_runner_clients.add(client_id)
      # Create 'futures' for sender and receiver - see following:
      # http://cheat.readthedocs.io/en/latest/python/asyncio.html
      sender = self._queued_sender(client_id)
      receiver = self._logger_runner_receiver(client_id)

      await self._handle_client_connection(client_id=client_id, sender=sender,
                                           receiver=receiver, host_id=host_id)
      # Clean up when connection closes
      with self.client_map_lock:
        self.logger_runner_clients.discard(client_id)

    else:
      # Client wants something unknown. Complain and return
      logging.warning('Unknown status request: "%s"', path)

    # When client disconnects, delete the queues it was using
    with self.client_map_lock:
      logging.info('WebsocketServer client #%d completed', client_id)
      del self.client_map[client_id]
      if client_id in self.send_queue: del self.send_queue[client_id]
      if client_id in self.receive_queue: del self.receive_queue[client_id]

  ############################
  @asyncio.coroutine
  async def _handle_client_connection(self, client_id, sender=None,
                                      receiver=None, host_id=None):
    """Handle a websocket client that has connected. Note that we expect
    the sender and receiver, if passed, to be 'futures', that is,
    called instantiations of async coroutines. Yeah, it's all still a
    little magic to me, but see the docs the following for insight:
    http://cheat.readthedocs.io/en/latest/python/asyncio.html
    """
    # Do we have a host id?
    if host_id is not None:
      with self.client_map_lock:
        self.host_id_map[client_id] = host_id

    # Create reader/writer tasks to send/receive data to/from websocket
    tasks = []
    if sender is not None:
      # Task that produces data from somewhere and sends to websocket
      tasks.append(asyncio.ensure_future(sender))
    if receiver is not None:
      # Task that receives data from websocket and does something with it
      tasks.append(asyncio.ensure_future(receiver))

    # Wait until one (or both) tasks finish
    done, pending = await asyncio.wait(
      tasks, return_when=asyncio.FIRST_COMPLETED)

    # Clean up the uncompleted task(s) and entries we created.
    for task in pending:
      task.cancel()
    if host_id is not None:
      with self.client_map_lock:
        del self.host_id_map[client_id]

  ############################
  # Methods below are senders/receivers for various websocket clients.

  ############################
  async def _queued_sender(self, client_id):
    """Iteratively pull messages from the client's send_queue and send to
    its websocket.
    """
    websocket = self.client_map.get(client_id, None)
    if not websocket:
      raise ValueError('No websocket for client_id %s!' % client_id)
    while not self.quit_flag:
      try:
        message = self.send_queue[client_id].get_nowait()
        if message.strip():
          logging.debug('Sending message to client #%d: %s',
                        client_id, message)
        await websocket.send(message)
      except websockets.ConnectionClosed:
        logging.info('Client %d connection closed', client_id)
        return
      except queue.Empty:
        await asyncio.sleep(0.1)

  ############################
  def _broadcast_status_loop(self):
    """Iteratively grab status messages from the api and send them out as
    JSON to whatever writer we're using to broadcast our logger
    statuses. In theory we could be much more efficient and directly
    grab status updates in _process_logger_runner_messages() when we
    get them from the LoggerRunners.
    """    
    # We stash previous_configs so that we know not to send them if
    # they haven't changed since last check. We keep the raw
    # previous_status separately, because we have to do some
    # processing to get it into a form that's useful for our clients,
    # and we want do avoid doing that processing if we can.
    previous_cruise_def = {}
    previous_logger_status = {}

    while not self.quit_flag:
      # Sleep for a bit before going around (also, before we try the
      # first time, to let the LoggerManager start up).
      time.sleep(self.interval)
      
      cruise_def_changed = status_changed = False
      try:
        cruise_def = {
          'loggers': self.api.get_loggers(),
          'modes':   self.api.get_modes(),
          'mode':    self.api.get_active_mode()
          }
      except (AttributeError, ValueError):
        logging.info('No cruise definition found')
        cruise_def = {}

      if not cruise_def == previous_cruise_def:
        cruise_def_changed = True
        previous_cruise_def = cruise_def

      # We expect status to be a dict of timestamp:{logger status
      # dict} entries. We may have multiple entries if we have
      # multiple LoggerRunners, e.g., if some have connected via
      # websockets. If we don't have any yet, work with a dummy entry.
      status = self.api.get_status() or {0: {}}
      timestamp = 0
      logger_status = {}
      for next_timestamp, next_logger_status in status.items():
        timestamp = max(timestamp, next_timestamp)
        logger_status.update(next_logger_status)

      # Has anything changed with logger statuses?
      if not logger_status == previous_logger_status:
        previous_logger_status = logger_status
        status_changed = True

      #########
      # If nothing has changed, just send a heartbeat timestamp
      if not cruise_def_changed and not status_changed:
        status_message = {'data_id':'logger_status',
                          'timestamp': timestamp,
                          'fields': {}}
        self.status_writer.write(json.dumps(status_message))
        continue

      #########
      # If we're here, something changed, either in cruise definition
      # or status; send out updates for all in small packets.

      # Send list of loggers
      loggers = cruise_def['loggers']
      status_message = {'data_id':'logger_status',
                        'timestamp': timestamp,
                        'fields': {'status:logger_list':
                                   [logger for logger in loggers]}}
      self.status_writer.write(json.dumps(status_message))

      # Send list of modes and current mode
      status_message = {'data_id':'logger_status',
                        'timestamp': timestamp,
                        'fields': {'status:mode_list': cruise_def['modes'],
                                   'status:mode': cruise_def['mode']}}
      self.status_writer.write(json.dumps(status_message))

      # Send one logger status per message, so we don't blow past the
      # packet size limit if we're broadcasting UDP
      for logger in loggers:
        status = logger_status.get(logger, None)
        if not status:
          logging.warning('Skipping logger %s', logger)
          continue        
        status_message = {
          'data_id':'logger_status',
          'timestamp': timestamp,
          'fields': {
            'status:logger:' + logger: {
              'configs': loggers[logger].get('configs', []),
              'config': status.get('config', None),
              'failed': status.get('failed', None),
              'running': status.get('running', None)
            }
          }
        }
        self.status_writer.write(json.dumps(status_message))

  ##########################
  async def _queued_receiver(self, client_id):
    """Iteratively read messages from websocket and place result in
    client's receive_queue.
    """
    websocket = self.client_map.get(client_id, None)
    if not websocket:
      raise ValueError('No websocket for client_id %s!' % client_id)
    while not self.quit_flag:
      message = await websocket.recv()
      logging.debug('Received message from client #%d: %s', client_id, message)
      self.receive_queue[client_id].put(message)

  ##########################
  async def _logger_runner_receiver(self, client_id):
    """Iteratively read messages from websocket and process received
    status and error updates.
    """
    websocket = self.client_map.get(client_id, None)
    if not websocket:
      raise ValueError('No websocket for client_id %s!' % client_id)
    while not self.quit_flag:
      message_str = await websocket.recv()
      message = json.loads(message_str)
      self._process_logger_runner_message(client_id, message)

  ##########################
  def _process_logger_runner_message(self, client_id, message):
    """Process a message received from a LoggerRunner. We expect
    message to be a dict of
    {
      'status': {
        logger_id: {errors: [], running,  failed},
        logger_id: {...},
        logger_id: {...}
      },
      'errors': {}   # if any errors to report
    }
    """
    logging.debug('LoggerRunner %s sent fields: %s',
                  client_id or 'local', ', '.join(message.keys()))
    status = message.get('status', None)
    errors = message.get('errors', None)
    if status:
      self.api.update_status(status)
    if errors:
      logging.error('Errors from client %s: %s', client_id or 'local', errors)

  ############################
  def update_configs_loop(self):
    """Iteratively check the API for updated configs and send them to the
    appropriate LoggerRunners.
    """
    while not self.quit_flag:
      self.update_configs()
      time.sleep(self.interval)

  ############################
  def update_configs(self):
    """Check the API for updated configs and send them to the appropriate
    LoggerRunners.
    """
    # Get latest configs. The call will throw a value error if no
    # configuration is loaded.
    with self.config_lock:
      try:
        new_configs = self.api.get_logger_configs()
      except (AttributeError, ValueError):
        return

      # If configs haven't changed, we're done - go home.
      if new_configs == self.old_configs:
        return

      self.old_configs = new_configs

    # Sort our configurations for dispatch.
    config_map = {}
    for logger, config in new_configs.items():

      # If there is a host restriction, set up a dict for configs
      # restricted to that host. If no restriction, file config
      # under key self.host_id (which may be 'None') to run locally.
      logging.debug('Config for logger %s: %s',
                      logger, config)
      if config is None:
        continue
      host_id = config.get('host_id', self.host_id)
      if not host_id in config_map:
        config_map[host_id] = {}
      config_map[host_id][logger] = config

    # Dispatch the partitioned configs to local/websocket-attached clients
    self.dispatch_configs(config_map)

  ############################
  def dispatch_configs(self, config_map):
    """We're passed a dict mapping host_ids to sets of configs. Look up
    corresponding client_id for each host and dispatch configs to it.
    """
    with self.client_map_lock:
      # First, see if there are any configs we're supposed to dispatch
      # for which we don't have the appropriate host.
      hosts = set(self.host_id_map.values())
      for desired_host in config_map:
        if not desired_host in hosts:
          logging.warning('Unable to dispatch configs to "%s" - no such host',
                          desired_host)
      # For each of our registered clients, see if we have any configs
      # in the config_map for them to run. If not, assign them an
      # empty config ({}) so that they're not running anything.
      for client_id in self.logger_runner_clients:
        if not client_id in self.host_id_map:
          raise ValueError('Client #%d has no host id?!?' % client_id)
        host_id = self.host_id_map[client_id]
        desired_config = config_map.get(host_id, {})
        command = 'set_configs ' + json.dumps(desired_config)
        self.send_queue[client_id].put(command)

################################################################################
################################################################################
if __name__ == '__main__':
  import argparse
  import atexit
  import readline

  from server.server_api_command_line import ServerAPICommandLine

  parser = argparse.ArgumentParser()
  parser.add_argument('--config', dest='config', action='store',
                      help='Name of configuration file to load.')
  parser.add_argument('--mode', dest='mode', action='store', default=None,
                      help='Optional name of mode to start system in.')

  parser.add_argument('--database', dest='database', action='store',
                      choices=['memory', 'django', 'hapi'],
                      default='memory', help='What backing store database '
                      'to use.')

  parser.add_argument('--broadcast_status', dest='broadcast_status',
                      action='store', default=None,
                      help='Network port on which to broadcast logger status '
                      'updates. If cruise configuration includes a display '
                      'server, this should match the port monitored by that '
                      'server, so that clients can receive status updates.')

  # Optional address for websocket server from which we'll accept
  # connections from LoggerRunners willing to accept dispatched
  # configs.
  parser.add_argument('--websocket', dest='websocket', action='store',
                      help='Host:port on which to open a websocket server '
                      'for LoggerRunners that are willing to accept config '
                      'dispatches. If host is omitted (e.g. '
                      '"--websocket :8765"), accept connections on any of '
                      'the server\'s network interfaces.')
  parser.add_argument('--host_id', dest='host_id', action='store', default='',
                      help='Host ID by which we identify ourselves')

  parser.add_argument('--interval', dest='interval', action='store',
                      type=float, default=1,
                      help='How many seconds to sleep between logger checks.')
  parser.add_argument('--max_tries', dest='max_tries', action='store', type=int,
                      default=DEFAULT_MAX_TRIES,
                      help='Number of times to retry failed loggers.')

  parser.add_argument('--no-console', dest='no_console', default=False,
                      action='store_true', help='Run without a console '
                      'that reads commands from stdin.')

  parser.add_argument('--stderr_file', dest='stderr_file', default=None,
                      help='Optional file to which stderr messages should '
                      'be written.')
  parser.add_argument('-v', '--verbosity', dest='verbosity',
                      default=0, action='count',
                      help='Increase output verbosity')
  parser.add_argument('-V', '--logger_verbosity', dest='logger_verbosity',
                      default=0, action='count',
                      help='Increase output verbosity of component loggers')
  args = parser.parse_args()

  # Set up logging first of all
  LOG_LEVELS ={0:logging.WARNING, 1:logging.INFO, 2:logging.DEBUG}
  log_level = LOG_LEVELS[min(args.verbosity, max(LOG_LEVELS))]
  setUpStdErrLogging(log_level=log_level)
  if args.stderr_file:
    stderr_writers = [TextFileWriter(args.stderr_file)]
    logging.getLogger().addHandler(StdErrLoggingHandler(stderr_writers))
    
  # What level do we want our component loggers to write?
  logger_log_level = LOG_LEVELS[min(args.logger_verbosity, max(LOG_LEVELS))]

  ############################
  # Instantiate API - a Are we using an in-memory store or Django
  # database as our backing store? Do our imports conditionally, so
  # they don't actually have to have Django if they're not using it.
  if args.database == 'django':
    from django_gui.django_server_api import DjangoServerAPI
    api = DjangoServerAPI()
  elif args.database == 'memory':
    from server.in_memory_server_api import InMemoryServerAPI
    api = InMemoryServerAPI()
  elif args.database == 'hapi':
    from hapi.hapi_server_api import HapiServerAPI
    api = HapiServerAPI()
  else:
    raise ValueError('Illegal arg for --database: "%s"' % args.database)

  # Now that API is defined, tack on one more logging handler: one
  # that passes messages to API.
  # TODO: decide if we even need this.
  logging.getLogger().addHandler(WriteToAPILoggingHandler(api))

  ############################
  # Create our LoggerManager
  logger_manager = LoggerManager(api=api, websocket=args.websocket,
                                 broadcast_status=args.broadcast_status,
                                 host_id=args.host_id,
                                 interval=args.interval,
                                 max_tries=args.max_tries,
                                 logger_log_level=logger_log_level)

  # Register a callback: when api.set_active_mode() or api.set_config()
  # have completed, they call api.signal_update(). We're registering
  # update_configs() with the API so that it gets called when the api
  # signals that an update has occurred.
  api.on_update(callback=logger_manager.update_configs)
  api.on_quit(callback=logger_manager.quit)

  ############################
  # Start all the various LoggerManager threads running
  logger_manager.start()

  ############################
  # If they've given us an initial configuration, get and load it.
  if args.config:
    config = read_config(args.config)
    api.load_configuration(config)
    api.message_log(source=SOURCE_NAME, user='(%s@%s)' % (USER, HOSTNAME),
                    log_level=api.INFO,
                    message='started with: %s' % args.config)
  if args.mode:
    if not args.config:
      raise ValueError('Argument --mode can only be used with --config')
    api.set_active_mode(args.mode)
    api.message_log(source=SOURCE_NAME, user='(%s@%s)' % (USER, HOSTNAME),
                    log_level=api.INFO,
                    message='initial mode (%s@%s): %s' % (USER, HOSTNAME, args.mode))

  try:
    # If no console, just wait for the configuration update thread to
    # end as a signal that we're done.
    if args.no_console:
      logging.warning('--no-console specified; waiting for LoggerManager '
                   'to exit.')
      if logger_manager.update_configs_thread:
        logger_manager.update_configs_thread.join()
      else:
        logging.warning('LoggerManager has no update_configs_thread? '
                        'Exiting...')

    else:
      # Create reader to read/process commands from stdin. Note: this
      # needs to be in main thread for Ctl-C termination to be properly
      # caught and processed, otherwise interrupts go to the wrong places.

      # Set up command line interface to get commands. Start by
      # reading history file, if one exists, to get past commands.
      hist_filename = '.openrvdas_logger_manager_history'
      hist_path = os.path.join(os.path.expanduser('~'), hist_filename)
      try:
        readline.read_history_file(hist_path)
        # default history len is -1 (infinite), which may grow unruly
        readline.set_history_length(1000)
      except (FileNotFoundError, PermissionError):
        pass
      atexit.register(readline.write_history_file, hist_path)

      command_line_reader = ServerAPICommandLine(api=api)
      command_line_reader.run()

  except KeyboardInterrupt:
    pass
  logging.debug('Done with logger_manager.py - exiting')
