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

from six import add_metaclass
from spinn_utilities.abstract_base import AbstractBase, abstractmethod
from pacman.exceptions import PacmanConfigurationException
from spynnaker.pyNN.extra_algorithms.splitter_components import (
    AbstractSpynnakerSplitterDelay)


@add_metaclass(AbstractBase)
class AbstractAcceptsIncomingSynapses(object):
    """ Indicates an object that can be a post-vertex in a PyNN projection.

    Note: See verify_splitter
    """
    __slots__ = ()

    @abstractmethod
    def get_synapse_id_by_target(self, target):
        """ Get the ID of a synapse given the name.

        :param str target: The name of the synapse
        :rtype: int
        """

    @abstractmethod
    def set_synapse_dynamics(self, synapse_dynamics):
        """ Set the synapse dynamics of this vertex.

        :param AbstractSynapseDynamics synapse_dynamics:
        """

    @abstractmethod
    def get_connections_from_machine(
            self, transceiver, placements, app_edge, synapse_info):
        # pylint: disable=too-many-arguments
        """ Get the connections from the machine post-run.

        :param ~spinnman.transceiver.Transceiver transceiver:
            How to read the connection data
        :param ~pacman.model.placements.Placements placements:
            Where the connection data is on the machine
        :param ProjectionApplicationEdge app_edge:
            The edge for which the data is being read
        :param SynapseInformation synapse_info:
            The specific projection within the edge
        """

    @abstractmethod
    def clear_connection_cache(self):
        """ Clear the connection data stored in the vertex so far.
        """

    def verify_splitter(self, splitter):
        """
        Check that the spliiter implements the API(s) expected by the\
        SynapticMatrices

        Any Vertex that implements this api should override
        ApplicationVertex.splitter method to also call this function

        :param splitter:
        :type splitter:
            ~spynnaker.pyNN.extra_algorithms.splitter_components.AbstractSpynnakerSplitterDelay
        :raise: PacmanConfigurationException is the spliiter is not an instance
             of AbstractSpynnakerSplitterDelay
        """
        # Delayed import to avoid cicular dependency
        from spynnaker.pyNN.extra_algorithms.splitter_components import (
            AbstractSpynnakerSplitterDelay)
        if not isinstance(splitter, AbstractSpynnakerSplitterDelay):
            raise PacmanConfigurationException(
                "The splitter needs to be an instance of "
                "----------------AbstractSpynnakerSplitterDelay")
