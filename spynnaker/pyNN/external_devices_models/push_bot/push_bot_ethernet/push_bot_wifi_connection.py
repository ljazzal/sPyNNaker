# Copyright (c) 2017-2019 The University of Manchester
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import logging
import select
import socket
from six import raise_from
from spinn_utilities.overrides import overrides
from spinn_utilities.ping import Ping
from spinnman.connections.abstract_classes import Listenable, Connection
from spinnman.exceptions import SpinnmanIOException, SpinnmanTimeoutException
from spinn_front_end_common.utilities.constants import BYTES_PER_KB

logger = logging.getLogger(__name__)
# A set of connections that have already been made
_existing_connections = dict()


def get_pushbot_wifi_connection(remote_host, remote_port=56000):
    """ Get an existing connection to a PushBot, or make a new one.

    :param str remote_host: The IP address of the PushBot
    :param int remote_port: The port number of the PushBot (default 56000)
    """
    key = (remote_host, remote_port)
    if key not in _existing_connections:
        _existing_connections[key] = \
            PushBotWIFIConnection(remote_host, remote_port)
    return _existing_connections[key]


class PushBotWIFIConnection(Connection, Listenable):
    """ A connection to a PushBot via Wi-Fi.
    """
    __slots__ = [
        "__local_ip_address",
        "__local_port",
        "__remote_ip_address",
        "__remote_port",
        "__socket"]

    RECV_SIZE = 1 * BYTES_PER_KB

    def __init__(self, remote_host, remote_port=56000):
        """
        :param str remote_host: The IP address of the PushBot
        :param int remote_port: The port number of the PushBot (default 56000)
        :raise SpinnmanIOException:
            If there is an error setting up the communication channel
        """
        try:
            # Create a TCP Socket
            self.__socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        except Exception as e:  # pylint: disable=broad-except
            raise_from(SpinnmanIOException(
                "Error setting up socket: {}".format(e)), e)

        # Get the port to connect to
        self.__remote_port = int(remote_port)

        # Get the host to connect to
        self.__remote_ip_address = socket.gethostbyname(remote_host)

        try:
            logger.info("Trying to connect to the PushBot via Wi-Fi")
            # Connect the socket
            self.__socket.connect(
                (self.__remote_ip_address, self.__remote_port))
            logger.info("Succeeded in connecting to PushBot via Wi-Fi")

        except Exception as e:  # pylint: disable=broad-except
            raise_from(SpinnmanIOException(
                "Error binding socket to {}:{}: {}".format(
                    self.__remote_ip_address, self.__remote_port, e)), e)

        # Get the details of where the socket is connected
        try:
            self.__local_ip_address, self.__local_port =\
                self.__socket.getsockname()

            # Ensure that a standard address is used for the INADDR_ANY
            # hostname
            if (self.__local_ip_address is None
                    or self.__local_ip_address == ""):
                self.__local_ip_address = "0.0.0.0"
        except Exception as e:  # pylint: disable=broad-except
            raise_from(SpinnmanIOException(
                "Error querying socket: {}".format(e)), e)

        # Set a general timeout on the socket
        self.__socket.settimeout(0)

    @overrides(Connection.is_connected)
    def is_connected(self):
        return Ping.host_is_reachable(self.__remote_ip_address)

    @property
    def local_ip_address(self):
        """ The local IP address to which the connection is bound, \
            as a dotted string, e.g. `0.0.0.0`

        :rtype: str
        """
        return self.__local_ip_address

    @property
    def local_port(self):
        """ The local port to which the connection is bound.

        :rtype: int
        """
        return self.__local_port

    @property
    def remote_ip_address(self):
        """ The remote IP address to which the connection is connected, \
            as a dotted string, or None if not connected remotely

        :rtype: str or None
        """
        return self.__remote_ip_address

    @property
    def remote_port(self):
        """ The remote port to which the connection is connected, \
            or None if not connected remotely

        :rtype: int or None
        """
        return self.__remote_port

    def receive(self, timeout=None):
        """ Receive data from the connection

        :param timeout: The timeout, or None to wait forever
        :type timeout: float or None
        :return: The data received
        :rtype: bytes
        :raise SpinnmanTimeoutException:
            If a timeout occurs before any data is received
        :raise SpinnmanIOException: If an error occurs receiving the data
        """
        try:
            self.__socket.settimeout(timeout)
            return self.__socket.recv(self.RECV_SIZE)
        except socket.timeout:
            raise SpinnmanTimeoutException("receive", timeout)
        except Exception as e:  # pylint: disable=broad-except
            raise_from(SpinnmanIOException(str(e)), e)

    def send(self, data):
        """ Send data down this connection

        :param bytearray data: The data to be sent
        :raise SpinnmanIOException: If there is an error sending the data
        """
        try:
            self.__socket.send(data)
        except Exception as e:  # pylint: disable=broad-except
            raise_from(SpinnmanIOException(str(e)), e)

    @overrides(Connection.close)
    def close(self):
        try:
            self.__socket.shutdown(socket.SHUT_WR)
        except Exception:  # pylint: disable=broad-except
            pass
        self.__socket.close()

    @overrides(Listenable.is_ready_to_receive, extend_defaults=True)
    def is_ready_to_receive(self, timeout=0):
        return bool(select.select([self.__socket], [], [], timeout)[0])

    @overrides(Listenable.get_receive_method)
    def get_receive_method(self):
        return self.receive
