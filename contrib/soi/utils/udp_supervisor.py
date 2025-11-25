#!/usr/bin/env python3
"""
Custom Supervisor for UDP Forwarder
Wrapper around LoggerRunner to handle templated/nested configurations
without modifying core OpenRVDAS files
"""
import logging
import sys
import time
import argparse

from logger.utils.stderr_logging import DEFAULT_LOGGING_FORMAT
from logger.utils.read_config import read_config, expand_cruise_definition
from server.logger_runner import LoggerRunner


class CustomLoggerSupervisor:
    def __init__(self, configs, stderr_file_pattern, max_tries=3, interval=1):
        self.configs = configs
        self.stderr_file_pattern = stderr_file_pattern
        self.max_tries = max_tries
        self.interval = interval

        self.runners = {}
        self.restart_counts = {}
        self.last_started = {}
        self.quit_flag = False

    def run(self):
        logging.info(f"Supervisor starting {len(self.configs)} loggers...")

        # Initial Start
        for name, config in self.configs.items():
            if config is None:
                logging.warning(f"Skipping logger {name} (Config is None)")
                continue
            self._start_logger(name, config)

        # Monitor Loop
        while not self.quit_flag:
            self._check_loggers()
            time.sleep(self.interval)

    def _start_logger(self, name, config):
        stderr = self.stderr_file_pattern.format(logger=name)
        logging.info(f"Starting logger: {name}")

        runner = LoggerRunner(config=config, name=name, stderr_filename=stderr)
        runner.start()

        self.runners[name] = runner
        self.last_started[name] = time.time()

    def _check_loggers(self):
        for name, runner in self.runners.items():
            if runner.is_alive():
                continue

            # If we are here the logger died
            logging.warning(f"Logger {name} is dead.")

            stderr_path = self.stderr_file_pattern.format(logger=name)
            logging.warning(f"  -> To see why, check the log: {stderr_path}")

            # Restart Logic
            count = self.restart_counts.get(name, 0)
            last = self.last_started.get(name, 0)

            # Reset count if it's been alive for >60s
            if time.time() - last > 60:
                count = 0

            if count >= self.max_tries:
                if not runner.is_failed():
                    logging.error(f"Logger {name} failed too many times. Giving up.")
                    runner.failed = True  # Mark as failed locally
                continue

            logging.info(f"Restarting {name} (Attempt {count + 1})")
            self.restart_counts[name] = count + 1
            # Check if config exists before restarting
            if name in self.configs and self.configs[name]:
                self._start_logger(name, self.configs[name])

    def quit(self):
        self.quit_flag = True
        for runner in self.runners.values():
            runner.quit()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    parser.add_argument("--mode", required=True)
    parser.add_argument("-v", "--verbosity", action="count", default=0)
    args = parser.parse_args()

    # Setup Logging
    level = logging.INFO if args.verbosity > 0 else logging.WARNING
    logging.basicConfig(format=DEFAULT_LOGGING_FORMAT, level=level)

    # 1. Load Config
    raw_config = read_config(args.config)
    config = expand_cruise_definition(raw_config)

    # 2. Extract Mode
    mode_map = config.get("modes", {}).get(args.mode)
    if not mode_map:
        logging.error(f"Mode {args.mode} not found.")
        sys.exit(1)

    # 3. Extract Nested Configs
    run_configs = {}
    all_loggers = config.get("loggers", {})

    for logger_name, config_name in mode_map.items():
        if config_name is True:
            config_name = "on"
        elif config_name is False:
            config_name = "off"

        # Calculate possible expanded names
        arrow_config_name = f"{logger_name}->{config_name}"
        hyphen_config_name = f"{logger_name}-{config_name}"

        # Try finding it in the nested template structure first
        if logger_name in all_loggers and "configs" in all_loggers[logger_name]:
            configs_container = all_loggers[logger_name]["configs"]

            # HANDLE DICTIONARY (Standard)
            if isinstance(configs_container, dict):
                # Try exact match, arrow match, or hyphen match
                found = (
                    configs_container.get(config_name)
                    or configs_container.get(arrow_config_name)
                    or configs_container.get(hyphen_config_name)
                )
                run_configs[logger_name] = found

            # HANDLE LIST (Legacy/Parsed) - Robust check for string vs dict
            elif isinstance(configs_container, list):
                found_config = None
                for c in configs_container:
                    c_name = c.get("name") if isinstance(c, dict) else c

                    # Match against 'on', 'logger->on', or 'logger-on'
                    if c_name in [config_name, arrow_config_name, hyphen_config_name]:
                        if isinstance(c, dict):
                            found_config = c
                        elif isinstance(c, str):
                            found_config = config.get("configs", {}).get(c)
                        break

                run_configs[logger_name] = found_config

            if not run_configs.get(logger_name):
                logging.error(
                    f"Could not find config '{config_name}' (or '{hyphen_config_name}') inside logger '{logger_name}'"
                )
                # DEBUG: Print available keys to help user
                if isinstance(configs_container, dict):
                    logging.error(f"Available keys: {list(configs_container.keys())}")
                elif isinstance(configs_container, list):
                    names = [
                        c.get("name") if isinstance(c, dict) else c
                        for c in configs_container
                    ]
                    logging.error(f"Available names: {names}")

        # Fallback to global config
        elif "configs" in config and config_name in config["configs"]:
            run_configs[logger_name] = config["configs"][config_name]
        else:
            logging.error(f"Could not find logger '{logger_name}'")

    # 4. Run Supervisor
    sup = CustomLoggerSupervisor(
        configs=run_configs, stderr_file_pattern="/var/log/openrvdas/{logger}.stderr"
    )
    try:
        sup.run()
    except KeyboardInterrupt:
        sup.quit()
