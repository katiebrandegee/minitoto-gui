import configparser
import os

_config_file = os.path.join(os.path.dirname(
    __file__), 'camera_config.ini')

class LucidCameraConfig:

    _config_section = "Camera"
    _instance = None

    def __new__(cls, config_file=_config_file):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialize(config_file)
        return cls._instance

    def _initialize(self, config_file):
        config = self.parse_config_file(config_file)
        self._throughput_limit = int(config.get(self._config_section, "throughput_limit"))
        self._max_resend_requests = int(config.get(self._config_section, "max_resend_requests"))
        self._max_brightness_error = float(config.get(self._config_section, "max_brightness_error"))

    def parse_config_file(self, file_path):
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Configuration file not found: {file_path}")

        config = configparser.ConfigParser()
        try:
            config.read(file_path)
        except configparser.Error as e:
            raise Exception(f"Failed to parse the configuration file: {file_path}") from e

        return config

    @property
    def throughput_limit(self) -> int:
        return self._throughput_limit

    @property
    def max_resend_requests(self) -> int:
        return self._max_resend_requests

    @property
    def max_brightness_error(self) -> float:
        return self._max_brightness_error
