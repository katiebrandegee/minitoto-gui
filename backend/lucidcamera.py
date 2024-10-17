from __future__ import annotations
import time
import numpy as np
import numpy.typing as npt
import cv2 as cv
from loguru import logger
from datetime import datetime

from arena_api.system import system
from arena_api.buffer import BufferFactory
import arena_api.enums

from .lucidcamera_config import LucidCameraConfig

config = LucidCameraConfig()


class NoCameraException(Exception):
    pass


class WrongImageBrightness(Exception):
    pass


class LucidCamera:

    def __init__(self, ip_address: str | None, target_brightness: int = 128, is_color: bool = True) -> None:
        self._ip_address = ip_address
        self._device = None
        self._is_color = is_color
        self._target_brightness = target_brightness
        self._target_adjustment = 0.85
        self._is_color = None
        self.connect()

    def connect(self) -> bool:
        """
        Connect to a Lucid Vision camera.
        Must be called before get_image().
        Returns True for success, False for failure.
        """
        logger.info(f"Connecting to camera at IP address {self._ip_address}")

        if len(system.device_infos) < 1:
            logger.warning("No connected cameras!")
            return False

        # find the camera with matching IP address
        devices = []
        device_ip = None
        if self._ip_address == None:
            device_info = system.device_infos[0]
            devices = system.create_device(device_info)
            device_ip = device_info['ip']
        else:
            for device_info in system.device_infos:
                if device_info['ip'] == self._ip_address:
                    devices = system.create_device(device_info)
                    device_ip = self._ip_address
                    break

        if len(devices) < 1:
            logger.warning(f"Could not connect to camera at IP address {self._ip_address}")
            return False
        self._device = devices[0]

        nodemap = self._device.nodemap
        nodemap["UserSetSelector"].value = "Default"
        nodemap["UserSetLoad"].execute()
        nodemap.get_node("AcquisitionMode").value = "SingleFrame"
        nodemap.get_node("ExposureAuto").value = "Continuous"
        nodemap.get_node("GainAuto").value = "Continuous"
        try:
            nodemap.get_node("PixelFormat").value = "BayerRG8"
            nodemap.get_node("ColorTransformationEnable").value = False
            self._is_color = True
            logger.debug("Color camera detected")
        except ValueError:
            nodemap.get_node("PixelFormat").value = "Mono8"
            self._is_color = False
            logger.debug("Mono camera detected")
        nodemap.get_node("TargetBrightness").value = int(self._target_adjustment*self._target_brightness)

        nodemap.get_node("DeviceLinkThroughputLimitMode").value = "On"
        nodemap.get_node("DeviceLinkThroughputLimit").value = config.throughput_limit

        tl_stream_nodemap = self._device.tl_stream_nodemap
        tl_stream_nodemap['StreamAutoNegotiatePacketSize'].value = True
        tl_stream_nodemap['StreamPacketResendEnable'].value = True
        tl_stream_nodemap["StreamBufferHandlingMode"].value = "NewestOnly"
        tl_stream_nodemap["StreamMaxNumResendRequestsPerImage"].value = 10000

        self._device.start_stream()

        # Collect a dummy image to initialize AGC
        buffer = self._device.get_buffer()
        self._device.requeue_buffer(buffer)

        logger.info(f"Connected to camera at IP address {device_ip}")
        return True

    def set_target_brightness(self, target_brightness: int) -> None:
        self._target_brightness = target_brightness

        self._device.nodemap.get_node("TargetBrightness").value = int(
            self._target_adjustment*self._target_brightness)

    def disconnect(self) -> bool:
        """
        Disconnect from a Lucid Vision camera.
        Returns True for success, False for failure.
        """
        if self._device is not None:
            self._device.stop_stream()
            system.destroy_device(self._device)
            self._device = None
            logger.info("Disconnected from camera")
        return True

    def get_image(self, output_filename=None) -> npt.NDArray:
        """
        Get an image from the connected camera, save it to disk, and return it.
        @param output_filename: the name of the file to save the image to.
            The file format is determined from the extension.
        """
        logger.debug("Image requested")

        if self._device is None:
            logger.debug("Connecting to camera")
            self.connect()

        if self._device is None:
            logger.error("Camera not connected, cannot get image")
            raise NoCameraException

        if not self._device.is_connected():
            logger.debug("Reconnecting to camera")
            self.disconnect()
            self.connect()

        if (self._device is None) or (not self._device.is_connected()):
            logger.error("Camera not connected, cannot get image")
            raise NoCameraException

        # Capture images until we get one with acceptable brightness (may have to wait for AGC)
        num_retries = 0
        max_num_retries = 30
        while True:
            time.sleep(1.0/self._device.nodemap["AcquisitionFrameRate"].value)  # make sure a new image has been collected since the start of this function
            self._device.nodemap["AcquisitionStart"].execute()
            buffer = self._device.get_buffer()

            while buffer.is_incomplete:
                logger.warning("Image buffer was incomplete, retrying")
                self._device.requeue_buffer(buffer)
                self._device.nodemap["AcquisitionStart"].execute()
                buffer = self._device.get_buffer()

            logger.info(f"Received {buffer.width}x{buffer.height} image")

            if self._is_color:
                buffer_out = BufferFactory.convert(buffer, arena_api.enums.PixelFormat.BGR8)
                channels = 3
            else:
                buffer_out = BufferFactory.convert(buffer, arena_api.enums.PixelFormat.Mono8)
                channels = 1
            self._device.requeue_buffer(buffer)

            bytes_per_pixel = int(buffer_out.bits_per_pixel / 8)
            row_size_in_bytes = buffer_out.width * bytes_per_pixel
            image_size_in_bytes = buffer_out.height * row_size_in_bytes
            image_data = buffer_out.data

            t1 = time.time()
            # Fill in the numpy array one line at a time se we can sleep(0) and give other threads a turn during this long process
            time.sleep(0.0)  # allow other threads a turn
            nparray = np.empty(image_size_in_bytes, dtype=np.uint8)
            for i in range(buffer_out.height):
                nparray[i*row_size_in_bytes:(i+1)*row_size_in_bytes] = np.asarray(image_data[i*row_size_in_bytes:(i+1)*row_size_in_bytes], dtype=np.uint8)
                time.sleep(0)
            t2 = time.time()
            logger.debug(f"Converted image to numpy array in {t2-t1:.3f}s")

            if channels > 1:
                img = nparray.reshape((buffer_out.height, buffer_out.width, channels))
            else:
                img = nparray.reshape((buffer_out.height, buffer_out.width))

            BufferFactory.destroy(buffer_out)

            img_mean = np.mean(img)
            if img_mean < self._target_brightness * (1 - config.max_brightness_error):
                self._target_adjustment *= (1 + config.max_brightness_error / 2)
                brightness_cmd = min(255, int(self._target_adjustment*self._target_brightness))
                logger.debug(f"Image is too dark (mean={img_mean:.2f}, desired={self._target_brightness}), re-capturing with TargetBrightness={brightness_cmd}")
                self._device.nodemap.get_node("TargetBrightness").value = brightness_cmd
            elif img_mean > self._target_brightness * (1 + config.max_brightness_error):
                self._target_adjustment *= (1 - config.max_brightness_error / 2)
                brightness_cmd = min(255, int(self._target_adjustment*self._target_brightness))
                logger.debug(
                    f"Image is too bright (mean={img_mean:.2f}, desired={self._target_brightness}), re-capturing with TargetBrightness={brightness_cmd}")
                self._device.nodemap.get_node("TargetBrightness").value = brightness_cmd
            else:
                logger.debug(f"Captured image with mean={img_mean:.2f}")
                break

            if num_retries >= max_num_retries:
                logger.warning(f"Failed to collect image with correct brightness after {num_retries} retries")
                raise WrongImageBrightness

            num_retries += 1

        if output_filename is not None:
            cv.imwrite(output_filename, img)
            logger.debug(f"Saved image to {output_filename}")

        return img
