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


@add_metaclass(AbstractBase)
class AbstractSynapseIO(object):
    # pylint: disable=too-many-arguments

    __slots__ = ()

    @abstractmethod
    def get_maximum_delay_supported_in_ms(self, vertex_time_step):
        """ Get the maximum delay supported by the synapse representation \
            before extensions are required, or None if any delay is supported
        """

    def get_max_row_info(
            self, synapse_info, post_vertex_slice, n_delay_stages,
            population_table, vertex_time_step, in_edge):
        """ Get the information about the maximum lengths of delayed and\
            undelayed rows in bytes (including header), words (without header)\
            and number of synapses
        """

    @abstractmethod
    def get_synapses(
            self, synapse_info, pre_slices, pre_slice_index,
            post_slices, post_slice_index, pre_vertex_slice,
            post_vertex_slice, n_delay_stages, population_table,
            n_synapse_types, weight_scales, vertex_time_step,
            app_edge, machine_edge):
        """ Get the synapses as an array of words for non-delayed synapses and\
            an array of words for delayed synapses
        """

    @abstractmethod
    def read_synapses(
            self, synapse_info, pre_vertex_slice, post_vertex_slice,
            max_row_length, delayed_max_row_length, n_synapse_types,
            weight_scales, data, delayed_data, n_delay_stages,
            vertex_time_step):
        """ Read the synapses for a given projection synapse information\
            object out of the given data
        """

    @abstractmethod
    def get_block_n_bytes(self, max_row_length, n_rows):
        """ Get the number of bytes in a block given the max row length and\
            number of rows
        """
