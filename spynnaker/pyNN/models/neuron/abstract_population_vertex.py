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
import sys
import math
import numpy
from collections import defaultdict

from spinn_utilities.log import FormatAdapter
from spinn_utilities.overrides import overrides
from spinn_utilities.progress_bar import ProgressBar
from data_specification.enums.data_type import DataType
from pacman.model.constraints.key_allocator_constraints import (
    ContiguousKeyRangeContraint)
from spinn_utilities.config_holder import (
    get_config_int, get_config_float, get_config_bool, get_config_str)

from pacman.model.resources import MultiRegionSDRAM

from spinn_front_end_common.abstract_models import (
    AbstractChangableAfterRun, AbstractProvidesOutgoingPartitionConstraints,
    AbstractCanReset, AbstractRewritesDataSpecification)
from spinn_front_end_common.abstract_models.impl import (
    ProvidesKeyToAtomMappingImpl, TDMAAwareApplicationVertex)
from spinn_front_end_common.interface.provenance import (
    AbstractProvidesLocalProvenanceData)
from spinn_front_end_common.utilities.constants import (
    BYTES_PER_WORD, SYSTEM_BYTES_REQUIREMENT)
from spinn_front_end_common.utilities.exceptions import ConfigurationException
from spinn_front_end_common.interface.profiling.profile_utils import (
    get_profile_region_size)
from spinn_front_end_common.interface.buffer_management\
    .recording_utilities import (
       get_recording_header_size, get_recording_data_constant_size)
from spinn_front_end_common.interface.provenance import (
    ProvidesProvenanceDataFromMachineImpl)
from spinn_front_end_common.utilities.utility_objs\
    .provenance_data_item import ProvenanceDataItem

from spynnaker.pyNN.models.common import (
    AbstractSpikeRecordable, AbstractNeuronRecordable, AbstractEventRecordable,
    NeuronRecorder)
from spynnaker.pyNN.models.abstract_models import (
    AbstractPopulationInitializable, AbstractAcceptsIncomingSynapses,
    AbstractPopulationSettable, AbstractContainsUnits, HasSynapses)
from spynnaker.pyNN.exceptions import (
    InvalidParameterType, SynapticConfigurationException)
from spynnaker.pyNN.utilities.ranged import (
    SpynnakerRangeDictionary)
from spynnaker.pyNN.utilities.utility_calls import float_gcd
from spynnaker.pyNN.models.neuron.synapse_dynamics import (
    AbstractSynapseDynamics, AbstractSynapseDynamicsStructural,
    SynapseDynamicsSTDP, SynapseDynamicsStructuralStatic)
from .synapse_io import get_max_row_info
from .master_pop_table import MasterPopTableAsBinarySearch
from .generator_data import GeneratorData
from .synaptic_matrices import SYNAPSES_BASE_GENERATOR_SDRAM_USAGE_IN_BYTES

logger = FormatAdapter(logging.getLogger(__name__))

# TODO: Make sure these values are correct (particularly CPU cycles)
_NEURON_BASE_DTCM_USAGE_IN_BYTES = 9 * BYTES_PER_WORD
_NEURON_BASE_N_CPU_CYCLES_PER_NEURON = 22
_NEURON_BASE_N_CPU_CYCLES = 10

# 1 for number of neurons
# 1 for number of synapse types
# 1 for number of neuron bits
# 1 for number of synapse type bits
# 1 for number of delay bits
# 1 for drop late packets,
# 1 for incoming spike buffer size
_SYNAPSES_BASE_SDRAM_USAGE_IN_BYTES = 7 * BYTES_PER_WORD


class AbstractPopulationVertex(
        TDMAAwareApplicationVertex, AbstractContainsUnits,
        AbstractSpikeRecordable, AbstractNeuronRecordable,
        AbstractEventRecordable, AbstractProvidesOutgoingPartitionConstraints,
        AbstractPopulationInitializable, AbstractPopulationSettable,
        AbstractChangableAfterRun, AbstractAcceptsIncomingSynapses,
        ProvidesKeyToAtomMappingImpl, AbstractCanReset,
        AbstractProvidesLocalProvenanceData):
    """ Underlying vertex model for Neural Populations.
        Not actually abstract.
    """

    __slots__ = [
        "__all_single_syn_sz",
        "__change_requires_mapping",
        "__change_requires_data_generation",
        "__incoming_spike_buffer_size",
        "__n_atoms",
        "__n_profile_samples",
        "__neuron_impl",
        "__neuron_recorder",
        "__synapse_recorder",
        "_parameters",  # See AbstractPyNNModel
        "__pynn_model",
        "_state_variables",  # See AbstractPyNNModel
        "__initial_state_variables",
        "__has_run",
        "__updated_state_variables",
        "__ring_buffer_sigma",
        "__spikes_per_second",
        "__drop_late_spikes",
        "__incoming_projections",
        "__synapse_dynamics",
        "__max_row_info",
        "__self_projection",
        "__weight_scales",
        "__min_weights",
        "__min_weights_auto",
        "__weight_random_sigma",
        "__max_stdp_spike_delta",
        "__weight_provenance"]

    #: recording region IDs
    _SPIKE_RECORDING_REGION = 0

    #: the size of the runtime SDP port data region
    _RUNTIME_SDP_PORT_SIZE = BYTES_PER_WORD

    #: The Buffer traffic type
    _TRAFFIC_IDENTIFIER = "BufferTraffic"

    _C_MAIN_BASE_N_CPU_CYCLES = 0
    _NEURON_BASE_N_CPU_CYCLES_PER_NEURON = 22
    _NEURON_BASE_N_CPU_CYCLES = 10
    _SYNAPSE_BASE_N_CPU_CYCLES_PER_NEURON = 22
    _SYNAPSE_BASE_N_CPU_CYCLES = 10

    # 5 elements before the start of global parameters
    # 1. has key, 2. key, 3. n atoms, 4. n_atoms_peak 5. n_synapse_types
    BYTES_TILL_START_OF_GLOBAL_PARAMETERS = 5 * BYTES_PER_WORD

    def __init__(
            self, n_neurons, label, constraints, max_atoms_per_core,
            spikes_per_second, ring_buffer_sigma, min_weights,
            weight_random_sigma, max_stdp_spike_delta,
            incoming_spike_buffer_size, neuron_impl, pynn_model,
            drop_late_spikes, splitter):
        """
        :param int n_neurons: The number of neurons in the population
        :param str label: The label on the population
        :param list(~pacman.model.constraints.AbstractConstraint) constraints:
            Constraints on where a population's vertices may be placed.
        :param int max_atoms_per_core:
            The maximum number of atoms (neurons) per SpiNNaker core.
        :param spikes_per_second: Expected spike rate
        :type spikes_per_second: float or None
        :param ring_buffer_sigma:
            How many SD above the mean to go for upper bound of ring buffer
            size; a good starting choice is 5.0. Given length of simulation
            we can set this for approximate number of saturation events.
        :type ring_buffer_sigma: float or None
        :param min_weights: minimum weight list
        :type min_weights: float or None
        :param weight_random_sigma: sigma value for ?
        :type weight_random_sigma: float or None
        :param max_stdp_spike_delta: delta
        :type max_stdp_spike_delta: float or None
        :param incoming_spike_buffer_size:
        :type incoming_spike_buffer_size: int or None
        :param bool drop_late_spikes: control flag for dropping late packets.
        :param AbstractNeuronImpl neuron_impl:
            The (Python side of the) implementation of the neurons themselves.
        :param AbstractPyNNNeuronModel pynn_model:
            The PyNN neuron model that this vertex is working on behalf of.
        :param splitter: splitter object
        :type splitter: None or
            ~pacman.model.partitioner_splitters.abstract_splitters.AbstractSplitterCommon
        """

        # pylint: disable=too-many-arguments, too-many-locals
        super().__init__(label, constraints, max_atoms_per_core, splitter)

        self.__n_atoms = self.round_n_atoms(n_neurons, "n_neurons")

        # buffer data
        self.__incoming_spike_buffer_size = incoming_spike_buffer_size

        if incoming_spike_buffer_size is None:
            self.__incoming_spike_buffer_size = get_config_int(
                "Simulation", "incoming_spike_buffer_size")

        # Limit the DTCM used by one-to-one connections
        self.__all_single_syn_sz = get_config_int(
            "Simulation", "one_to_one_connection_dtcm_max_bytes")

        self.__ring_buffer_sigma = ring_buffer_sigma
        if self.__ring_buffer_sigma is None:
            self.__ring_buffer_sigma = get_config_float(
                "Simulation", "ring_buffer_sigma")

        self.__spikes_per_second = spikes_per_second
        if self.__spikes_per_second is None:
            self.__spikes_per_second = get_config_float(
                "Simulation", "spikes_per_second")

        self.__drop_late_spikes = drop_late_spikes
        if self.__drop_late_spikes is None:
            self.__drop_late_spikes = get_config_bool(
                "Simulation", "drop_late_spikes")

        self.__neuron_impl = neuron_impl
        self.__pynn_model = pynn_model
        self._parameters = SpynnakerRangeDictionary(n_neurons)
        self.__neuron_impl.add_parameters(self._parameters)
        self.__initial_state_variables = SpynnakerRangeDictionary(n_neurons)
        self.__neuron_impl.add_state_variables(self.__initial_state_variables)
        self._state_variables = self.__initial_state_variables.copy()

        # Set up for recording
        neuron_recordable_variables = list(
            self.__neuron_impl.get_recordable_variables())
        record_data_types = dict(
            self.__neuron_impl.get_recordable_data_types())
        self.__neuron_recorder = NeuronRecorder(
            neuron_recordable_variables, record_data_types,
            [NeuronRecorder.SPIKES], n_neurons, [], {}, [], {})
        self.__synapse_recorder = NeuronRecorder(
            [], {}, [],
            n_neurons, [NeuronRecorder.PACKETS],
            {NeuronRecorder.PACKETS: NeuronRecorder.PACKETS_TYPE},
            [NeuronRecorder.REWIRING],
            {NeuronRecorder.REWIRING: NeuronRecorder.REWIRING_TYPE})

        # bool for if state has changed.
        self.__change_requires_mapping = True
        self.__change_requires_data_generation = False
        self.__has_run = False

        # Set up for profiling
        self.__n_profile_samples = get_config_int(
            "Reports", "n_profile_samples")

        # Set up for incoming
        self.__incoming_projections = list()
        self.__max_row_info = dict()
        self.__self_projection = None

        # Prepare for dealing with STDP - there can only be one (non-static)
        # synapse dynamics per vertex at present
        self.__synapse_dynamics = None

        # Store (local) weight scales
        self.__weight_scales = None

        # Read the minimum weight if not set; this might *still* be None,
        # meaning "auto calculate"; the number of weights needs to match
        # the number of synapse types
        self.__min_weights = min_weights
        if self.__min_weights is None:
            config_min_weights = get_config_str("Simulation", "min_weights")
            if config_min_weights is not None:
                self.__min_weights = [float(v)
                                      for v in config_min_weights.split(',')]
        self.__min_weights_auto = True
        if self.__min_weights is not None:
            self.__min_weights_auto = False
            n_synapse_types = self.__neuron_impl.get_n_synapse_types()
            if len(self.__min_weights) != n_synapse_types:
                raise SynapticConfigurationException(
                    "The number of minimum weights provided ({}) does not"
                    " match the number of synapse types ({})".format(
                        self.__min_weights, n_synapse_types))

        # Read the other minimum weight configuration parameters
        self.__weight_random_sigma = weight_random_sigma
        if self.__weight_random_sigma is None:
            self.__weight_random_sigma = get_config_float(
                "Simulation", "weight_random_sigma")
        self.__max_stdp_spike_delta = max_stdp_spike_delta
        if self.__max_stdp_spike_delta is None:
            self.__max_stdp_spike_delta = get_config_float(
                "Simulation", "max_stdp_spike_delta")

        # Store weight provenance information mapping from
        # (real weight, represented weight) -> projections
        self.__weight_provenance = defaultdict(list)

    @property
    def synapse_dynamics(self):
        """ The synapse dynamics used by the synapses e.g. plastic or static.
            Settable.

        :rtype: AbstractSynapseDynamics or None
        """
        return self.__synapse_dynamics

    @synapse_dynamics.setter
    def synapse_dynamics(self, synapse_dynamics):
        """ Set the synapse dynamics.  Note that after setting, the dynamics
            might not be the type set as it can be combined with the existing
            dynamics in exciting ways.

        :param AbstractSynapseDynamics synapse_dynamics:
            The synapse dynamics to set
        """
        if self.__synapse_dynamics is None:
            self.__synapse_dynamics = synapse_dynamics
        else:
            self.__synapse_dynamics = self.__synapse_dynamics.merge(
                synapse_dynamics)

    def add_incoming_projection(self, projection):
        """ Add a projection incoming to this vertex

        :param PyNNProjectionCommon projection:
            The new projection to add
        """
        # Reset the ring buffer shifts as a projection has been added
        self.__change_requires_mapping = True
        self.__incoming_projections.append(projection)
        if projection._projection_edge.pre_vertex == self:
            self.__self_projection = projection

    @property
    def self_projection(self):
        """ Get any projection from this vertex to itself

        :rtype: PyNNProjectionCommon or None
        """
        return self.__self_projection

    @property
    @overrides(TDMAAwareApplicationVertex.n_atoms)
    def n_atoms(self):
        return self.__n_atoms

    @overrides(TDMAAwareApplicationVertex.get_n_cores)
    def get_n_cores(self):
        return len(self._splitter.get_out_going_slices()[0])

    @property
    def size(self):
        """ The number of neurons in the vertex

        :rtype: int
        """
        return self.__n_atoms

    @property
    def all_single_syn_size(self):
        """ The maximum amount of DTCM to use for single synapses

        :rtype: int
        """
        return self.__all_single_syn_sz

    @property
    def incoming_spike_buffer_size(self):
        """ The size of the incoming spike buffer to be used on the cores

        :rtype: int
        """
        return self.__incoming_spike_buffer_size

    @property
    def parameters(self):
        """ The parameters of the neurons in the population

        :rtype: SpyNNakerRangeDictionary
        """
        return self._parameters

    @property
    def state_variables(self):
        """ The state variables of the neuron in the population

        :rtype: SpyNNakerRangeDicationary
        """
        return self._state_variables

    @property
    def neuron_impl(self):
        """ The neuron implementation

        :rtype: AbstractNeuronImpl
        """
        return self.__neuron_impl

    @property
    def n_profile_samples(self):
        """ The maximum number of profile samples to report

        :rtype: int
        """
        return self.__n_profile_samples

    @property
    def neuron_recorder(self):
        """ The recorder for neurons

        :rtype: NeuronRecorder
        """
        return self.__neuron_recorder

    @property
    def synapse_recorder(self):
        """ The recorder for synapses

        :rtype: SynapseRecorder
        """
        return self.__synapse_recorder

    @property
    def drop_late_spikes(self):
        """ Whether spikes should be dropped if not processed in a timestep

        :rtype: bool
        """
        return self.__drop_late_spikes

    def set_has_run(self):
        """ Set the flag has run so initialize only affects state variables

        :rtype: None
        """
        self.__has_run = True

    @property
    @overrides(AbstractChangableAfterRun.requires_mapping)
    def requires_mapping(self):
        return self.__change_requires_mapping

    @property
    @overrides(AbstractChangableAfterRun.requires_data_generation)
    def requires_data_generation(self):
        return self.__change_requires_data_generation

    @overrides(AbstractChangableAfterRun.mark_no_changes)
    def mark_no_changes(self):
        self.__change_requires_mapping = False
        self.__change_requires_data_generation = False

    def get_sdram_usage_for_neuron_params(self, vertex_slice):
        """ Calculate the SDRAM usage for just the neuron parameters region.

        :param ~pacman.model.graphs.common.Slice vertex_slice:
            the slice of atoms.
        :return: The SDRAM required for the neuron region
        """
        return (
            self.BYTES_TILL_START_OF_GLOBAL_PARAMETERS +
            (self.__neuron_impl.get_n_synapse_types() * BYTES_PER_WORD) +
            self.tdma_sdram_size_in_bytes +
            self.__neuron_impl.get_sdram_usage_in_bytes(vertex_slice.n_atoms))

    @overrides(AbstractSpikeRecordable.is_recording_spikes)
    def is_recording_spikes(self):
        return self.__neuron_recorder.is_recording(NeuronRecorder.SPIKES)

    @overrides(AbstractSpikeRecordable.set_recording_spikes)
    def set_recording_spikes(
            self, new_state=True, sampling_interval=None, indexes=None):
        self.set_recording(
            NeuronRecorder.SPIKES, new_state, sampling_interval, indexes)

    @overrides(AbstractEventRecordable.is_recording_events)
    def is_recording_events(self, variable):
        return self.__synapse_recorder.is_recording(variable)

    @overrides(AbstractEventRecordable.set_recording_events)
    def set_recording_events(
            self, variable, new_state=True, sampling_interval=None,
            indexes=None):
        self.set_recording(
            variable, new_state, sampling_interval, indexes)

    @overrides(AbstractSpikeRecordable.get_spikes)
    def get_spikes(self, placements, buffer_manager):
        return self.__neuron_recorder.get_spikes(
            self.label, buffer_manager, placements, self,
            NeuronRecorder.SPIKES)

    @overrides(AbstractEventRecordable.get_events)
    def get_events(
            self, variable, placements, buffer_manager):
        return self.__synapse_recorder.get_events(
            self.label, buffer_manager, placements, self, variable)

    @overrides(AbstractNeuronRecordable.get_recordable_variables)
    def get_recordable_variables(self):
        variables = list()
        variables.extend(self.__neuron_recorder.get_recordable_variables())
        variables.extend(self.__synapse_recorder.get_recordable_variables())
        return variables

    def __raise_var_not_supported(self, variable):
        """ Helper to indicate that recording a variable is not supported

        :param str variable: The variable to report as unsupported
        """
        msg = ("Variable {} is not supported. Supported variables are"
               "{}".format(variable, self.get_recordable_variables()))
        raise ConfigurationException(msg)

    @overrides(AbstractNeuronRecordable.is_recording)
    def is_recording(self, variable):
        if self.__neuron_recorder.is_recordable(variable):
            return self.__neuron_recorder.is_recording(variable)
        if self.__synapse_recorder.is_recordable(variable):
            return self.__synapse_recorder.is_recording(variable)
        self.__raise_var_not_supported(variable)

    @overrides(AbstractNeuronRecordable.set_recording)
    def set_recording(self, variable, new_state=True, sampling_interval=None,
                      indexes=None):
        if self.__neuron_recorder.is_recordable(variable):
            self.__neuron_recorder.set_recording(
                variable, new_state, sampling_interval, indexes)
        elif self.__synapse_recorder.is_recordable(variable):
            self.__synapse_recorder.set_recording(
                variable, new_state, sampling_interval, indexes)
        else:
            self.__raise_var_not_supported(variable)
        self.__change_requires_mapping = not self.is_recording(variable)

    @overrides(AbstractNeuronRecordable.get_data)
    def get_data(
            self, variable, n_machine_time_steps, placements, buffer_manager):
        # pylint: disable=too-many-arguments
        if self.__neuron_recorder.is_recordable(variable):
            return self.__neuron_recorder.get_matrix_data(
                self.label, buffer_manager, placements, self, variable,
                n_machine_time_steps)
        elif self.__synapse_recorder.is_recordable(variable):
            return self.__synapse_recorder.get_matrix_data(
                self.label, buffer_manager, placements, self, variable,
                n_machine_time_steps)
        self.__raise_var_not_supported(variable)

    @overrides(AbstractNeuronRecordable.get_neuron_sampling_interval)
    def get_neuron_sampling_interval(self, variable):
        if self.__neuron_recorder.is_recordable(variable):
            return self.__neuron_recorder.get_neuron_sampling_interval(
                variable)
        elif self.__synapse_recorder.is_recordable(variable):
            return self.__synapse_recorder.get_neuron_sampling_interval(
                variable)
        self.__raise_var_not_supported(variable)

    @overrides(AbstractSpikeRecordable.get_spikes_sampling_interval)
    def get_spikes_sampling_interval(self):
        return self.__neuron_recorder.get_neuron_sampling_interval("spikes")

    @overrides(AbstractEventRecordable.get_events_sampling_interval)
    def get_events_sampling_interval(self, variable):
        return self.__neuron_recorder.get_neuron_sampling_interval(variable)

    @overrides(AbstractPopulationInitializable.initialize)
    def initialize(self, variable, value, selector=None):
        if variable not in self._state_variables:
            raise KeyError(
                "Vertex does not support initialisation of"
                " parameter {}".format(variable))
        if self.__has_run:
            self._state_variables[variable].set_value_by_selector(
                selector, value)
            logger.warning(
                "initializing {} after run and before reset only changes the "
                "current state and will be lost after reset".format(variable))
        else:
            # set the inital values
            self.__initial_state_variables[variable].set_value_by_selector(
                selector, value)
            # Update the sate variables in case asked for
            self._state_variables.copy_into(self.__initial_state_variables)
        for vertex in self.machine_vertices:
            if isinstance(vertex, AbstractRewritesDataSpecification):
                vertex.set_reload_required(True)

    @property
    def initialize_parameters(self):
        """ The names of parameters that have default initial values.

        :rtype: iterable(str)
        """
        return self.__pynn_model.default_initial_values.keys()

    def _get_parameter(self, variable):
        """ Get a neuron parameter value

        :param str variable: The variable to get the value of
        """
        if variable.endswith("_init"):
            # method called with "V_init"
            key = variable[:-5]
            if variable in self._state_variables:
                # variable is v and parameter is v_init
                return variable
            elif key in self._state_variables:
                # Oops neuron defines v and not v_init
                return key
        else:
            # method called with "v"
            if variable + "_init" in self._state_variables:
                # variable is v and parameter is v_init
                return variable + "_init"
            if variable in self._state_variables:
                # Oops neuron defines v and not v_init
                return variable

        # parameter not found for this variable
        raise KeyError("No variable {} found in {}".format(
            variable, self.__neuron_impl.model_name))

    @overrides(AbstractPopulationInitializable.get_initial_value)
    def get_initial_value(self, variable, selector=None):
        parameter = self._get_parameter(variable)

        ranged_list = self._state_variables[parameter]
        if selector is None:
            return ranged_list
        return ranged_list.get_values(selector)

    @property
    def conductance_based(self):
        """
        :rtype: bool
        """
        return self.__neuron_impl.is_conductance_based

    @overrides(AbstractPopulationSettable.get_value)
    def get_value(self, key):
        """ Get a property of the overall model.
        """
        if key not in self._parameters:
            raise InvalidParameterType(
                "Population {} does not have parameter {}".format(
                    self.__neuron_impl.model_name, key))
        return self._parameters[key]

    @overrides(AbstractPopulationSettable.set_value)
    def set_value(self, key, value):
        """ Set a property of the overall model.
        """
        if key not in self._parameters:
            raise InvalidParameterType(
                "Population {} does not have parameter {}".format(
                    self.__neuron_impl.model_name, key))
        self._parameters.set_value(key, value)
        for vertex in self.machine_vertices:
            if isinstance(vertex, AbstractRewritesDataSpecification):
                vertex.set_reload_required(True)

    @property
    def weight_scale(self):
        """
        :rtype: float
        """
        return self.__neuron_impl.get_global_weight_scale()

    @property
    def ring_buffer_sigma(self):
        return self.__ring_buffer_sigma

    @ring_buffer_sigma.setter
    def ring_buffer_sigma(self, ring_buffer_sigma):
        self.__ring_buffer_sigma = ring_buffer_sigma

    @property
    def spikes_per_second(self):
        return self.__spikes_per_second

    @spikes_per_second.setter
    def spikes_per_second(self, spikes_per_second):
        self.__spikes_per_second = spikes_per_second

    def set_synapse_dynamics(self, synapse_dynamics):
        """ Set the synapse dynamics of this population

        :param AbstractSynapseDynamics synapse_dynamics:
            The synapse dynamics to set
        """
        self.synapse_dynamics = synapse_dynamics

    def clear_connection_cache(self):
        """ Flush the cache of connection information; needed for a second run
        """
        for post_vertex in self.machine_vertices:
            if isinstance(post_vertex, HasSynapses):
                post_vertex.clear_connection_cache()
                post_vertex._app_vertex.reset_min_weights()

    def reset_min_weights(self):
        """ Reset min_weights if set to auto-calculate
        """
        if self.__min_weights_auto:
            self.__min_weights = None

    @overrides(AbstractProvidesOutgoingPartitionConstraints.
               get_outgoing_partition_constraints)
    def get_outgoing_partition_constraints(self, partition):
        """ Gets the constraints for partitions going out of this vertex.

        :param partition: the partition that leaves this vertex
        :return: list of constraints
        """
        return [ContiguousKeyRangeContraint()]

    @overrides(AbstractNeuronRecordable.clear_recording)
    def clear_recording(self, variable, buffer_manager, placements):
        if variable == NeuronRecorder.SPIKES:
            index = len(self.__neuron_impl.get_recordable_variables())
        elif variable == NeuronRecorder.REWIRING:
            index = len(self.__neuron_impl.get_recordable_variables()) + 1
        else:
            index = (
                self.__neuron_impl.get_recordable_variable_index(variable))
        self._clear_recording_region(buffer_manager, placements, index)

    @overrides(AbstractSpikeRecordable.clear_spike_recording)
    def clear_spike_recording(self, buffer_manager, placements):
        self._clear_recording_region(
            buffer_manager, placements,
            len(self.__neuron_impl.get_recordable_variables()))

    @overrides(AbstractEventRecordable.clear_event_recording)
    def clear_event_recording(self, buffer_manager, placements):
        self._clear_recording_region(
            buffer_manager, placements,
            len(self.__neuron_impl.get_recordable_variables()) + 1)

    def _clear_recording_region(
            self, buffer_manager, placements, recording_region_id):
        """ Clear a recorded data region from the buffer manager.

        :param buffer_manager: the buffer manager object
        :param placements: the placements object
        :param recording_region_id: the recorded region ID for clearing
        :rtype: None
        """
        for machine_vertex in self.machine_vertices:
            placement = placements.get_placement_of_vertex(machine_vertex)
            buffer_manager.clear_recorded_data(
                placement.x, placement.y, placement.p, recording_region_id)

    @overrides(AbstractContainsUnits.get_units)
    def get_units(self, variable):
        if variable == NeuronRecorder.SPIKES:
            return NeuronRecorder.SPIKES
        if variable == NeuronRecorder.PACKETS:
            return "count"
        if self.__neuron_impl.is_recordable(variable):
            return self.__neuron_impl.get_recordable_units(variable)
        if variable not in self._parameters:
            raise Exception("Population {} does not have parameter {}".format(
                self.__neuron_impl.model_name, variable))
        return self.__neuron_impl.get_units(variable)

    def describe(self):
        """ Get a human-readable description of the cell or synapse type.

        The output may be customised by specifying a different template
        together with an associated template engine
        (see :py:mod:`pyNN.descriptions`).

        If template is None, then a dictionary containing the template context
        will be returned.

        :rtype: dict(str, ...)
        """
        parameters = dict()
        for parameter_name in self.__pynn_model.default_parameters:
            parameters[parameter_name] = self.get_value(parameter_name)

        context = {
            "name": self.__neuron_impl.model_name,
            "default_parameters": self.__pynn_model.default_parameters,
            "default_initial_values": self.__pynn_model.default_parameters,
            "parameters": parameters,
        }
        return context

    def get_synapse_id_by_target(self, target):
        """ Get the id of synapse using its target name

        :param str target: The synapse to get the id of
        """
        return self.__neuron_impl.get_synapse_id_by_target(target)

    def __str__(self):
        return "{} with {} atoms".format(self.label, self.n_atoms)

    def __repr__(self):
        return self.__str__()

    @overrides(AbstractCanReset.reset_to_first_timestep)
    def reset_to_first_timestep(self):
        # Mark that reset has been done, and reload state variables
        self.__has_run = False
        self._state_variables.copy_into(self.__initial_state_variables)
        for vertex in self.machine_vertices:
            if isinstance(vertex, AbstractRewritesDataSpecification):
                vertex.set_reload_required(True)

        # If synapses change during the run,
        if (self.__synapse_dynamics is not None and
                self.__synapse_dynamics.changes_during_run):
            self.__change_requires_data_generation = True
            for vertex in self.machine_vertices:
                if isinstance(vertex, AbstractRewritesDataSpecification):
                    vertex.set_reload_required(True)

    # TODO: The upcoming functions replace the ring_buffer bound calculations
    # and use minimum weights instead; it may be that a mixture of the two
    # methods is necessary in the long run
    def __get_closest_weight(self, value):
        """ Get the best representation of the weight so that both weight and
            1 / w work

        :param float value: value to get the closest weight of
        """
        if abs(value) < 1.0:
            return DataType.S1615.closest_representable_value(value)
        return 1 / (
            DataType.S1615.closest_representable_value_above(1 / value))

    def __calculate_min_weights(self, incoming_projections):
        """ Calculate the minimum weights required to best represent all the
            possible weights coming into this vertex

        :param list(~.Projection) incoming_projections: incoming proj to vertex

        :return: list of minimum weights
        :rtype: list(float)
        """
        # Initialise to a maximum value
        min_weights = [sys.maxsize for _ in range(
            self.__neuron_impl.get_n_synapse_types())]

        # Get the (global) weight_scale from the input_type in the neuron_impl
        weight_scale = self.__neuron_impl.get_global_weight_scale()

        for proj in incoming_projections:
            synapse_info = proj._synapse_information
            synapse_type = synapse_info.synapse_type
            connector = synapse_info.connector
            synapse_dynamics = synapse_info.synapse_dynamics

            weight_min = connector.get_weight_minimum(
                synapse_info.weights, self.__weight_random_sigma, synapse_info)
            weight_min *= weight_scale
            if weight_min != 0 and not numpy.isnan(weight_min):
                weight_min = float_gcd(min_weights[synapse_type], weight_min)
                min_weights[synapse_type] = min(
                    min_weights[synapse_type], weight_min)

            if isinstance(synapse_dynamics, SynapseDynamicsSTDP):
                min_delta = synapse_dynamics.get_weight_min_delta(
                    self.__max_stdp_spike_delta)
                min_delta *= weight_scale
                if min_delta is not None and min_delta != 0:
                    # This also depends on the earlier calculated minimum
                    min_delta = float_gcd(min_delta, weight_min)
                    min_weights[synapse_type] = min(
                        min_weights[synapse_type], min_delta)
            elif isinstance(synapse_dynamics, SynapseDynamicsStructuralStatic):
                weight_min = synapse_dynamics.initial_weight
                weight_min *= weight_scale
                if weight_min != 0:
                    weight_min = float_gcd(min_weights[synapse_type],
                                           weight_min)
                    min_weights[synapse_type] = min(
                        min_weights[synapse_type], weight_min)

        # Convert values to their closest representable value to ensure
        # that division works for the minimum value
        min_weights = [self.__get_closest_weight(m)
                       if m != sys.maxsize else 0 for m in min_weights]

        # The minimum weight shouldn't be 0 unless set above (and then it
        # doesn't matter that we use the min as there are no weights); so
        # set the weight to the smallest representable value if 0
        min_weights = [m if m > 0 else DataType.S1615.decode_from_int(1)
                       for m in min_weights]

        self.__check_weights(min_weights, weight_scale, incoming_projections)

        return min_weights

    def __check_weights(
            self, min_weights, weight_scale, incoming_projections):
        """ Warn the user about weights that can't be represented properly
            where possible

        :param ~numpy.ndarray min_weights: Minimum weights per synapse type
        :param float weight_scale: The weight_scale from the synapse input_type
        :param list(~.Projection) incoming_projections: A list of incoming proj
        """
        for proj in incoming_projections:
            synapse_info = proj._synapse_information
            weights = synapse_info.weights
            synapse_type = synapse_info.synapse_type
            min_weight = min_weights[synapse_type]
            if not isinstance(weights, str):
                if numpy.isscalar(weights):
                    self.__check_weight(
                        min_weight, weights, weight_scale, proj, synapse_info)
                elif hasattr(weights, "__getitem__"):
                    for w in weights:
                        self.__check_weight(
                            min_weight, w, weight_scale, proj, synapse_info)

    def __check_weight(
            self, min_weight, weight, weight_scale, projection,
            synapse_info):
        """ Warn the user about a weight that can't be represented properly
            where possible

        :param float min_weight: Minimum weight value
        :param float weight: weight value being checked
        :param float weight_scale: The weight_scale from the synapse input_type
        :param ~.Projection projection: The projection
        :param ~.SynapseInformation synapse_info: The synapse information
        """
        r_weight = weight * weight_scale / min_weight
        r_weight = (DataType.UINT16.closest_representable_value(
            r_weight) * min_weight) / weight_scale
        if weight != r_weight:
            self.__weight_provenance[weight, r_weight].append(
                (projection, synapse_info))

    def get_min_weights(self, incoming_projections):
        """ Calculate the minimum weights required to best represent all the
            possible weights coming into this vertex

        :param list(~.Projection) incoming_projections: incoming proj to vertex

        :return: list of minimum weights
        :rtype: list(float)
        """
        if self.__min_weights is None:
            self.__min_weights = self.__calculate_min_weights(
                incoming_projections)
        return self.__min_weights

    def get_weight_scales(self, min_weights):
        """ Get the weight scaling to apply to weights in synapses

        :param list(int) min_weights:
            The min weights to convert to weight scales
        :rtype: list(int)
        """
        weight_scale = self.__neuron_impl.get_global_weight_scale()
        self.__weight_scales = numpy.array(
            [(1 / w) * weight_scale if w != 0 else 0 for w in min_weights])
        return self.__weight_scales

    @overrides(AbstractAcceptsIncomingSynapses.get_connections_from_machine)
    def get_connections_from_machine(
            self, transceiver, placements, app_edge, synapse_info):
        # Start with something in the list so that concatenate works
        connections = [numpy.zeros(
                0, dtype=AbstractSynapseDynamics.NUMPY_CONNECTORS_DTYPE)]
        progress = ProgressBar(
            len(self.machine_vertices),
            "Getting synaptic data between {} and {}".format(
                app_edge.pre_vertex.label, app_edge.post_vertex.label))
        for post_vertex in progress.over(self.machine_vertices):
            if isinstance(post_vertex, HasSynapses):
                placement = placements.get_placement_of_vertex(post_vertex)
                connections.extend(post_vertex.get_connections_from_machine(
                    transceiver, placement, app_edge, synapse_info))
        return numpy.concatenate(connections)

    def get_synapse_params_size(self):
        """ Get the size of the synapse parameters in bytes

        :rtype: int
        """
        return (_SYNAPSES_BASE_SDRAM_USAGE_IN_BYTES +
                (BYTES_PER_WORD * self.__neuron_impl.get_n_synapse_types()))

    def get_synapse_dynamics_size(self, vertex_slice):
        """ Get the size of the synapse dynamics region

        :param ~pacman.model.graphs.common.Slice vertex_slice:
            The slice of the vertex to get the usage of
        :rtype: int
        """
        if self.__synapse_dynamics is None:
            return 0

        return self.__synapse_dynamics.get_parameters_sdram_usage_in_bytes(
            vertex_slice.n_atoms, self.__neuron_impl.get_n_synapse_types())

    def get_structural_dynamics_size(self, vertex_slice, incoming_projections):
        """ Get the size of the structural dynamics region

        :param ~pacman.model.graphs.common.Slice vertex_slice:
            The slice of the vertex to get the usage of
        :param list(~spynnaker.pyNN.models.Projection) incoming_projections:
            The projections to consider in the calculations
        """
        if self.__synapse_dynamics is None:
            return 0

        if not isinstance(
                self.__synapse_dynamics, AbstractSynapseDynamicsStructural):
            return 0

        return self.__synapse_dynamics\
            .get_structural_parameters_sdram_usage_in_bytes(
                incoming_projections, vertex_slice.n_atoms)

    def get_synapses_size(self, vertex_slice, incoming_projections):
        """ Get the maximum SDRAM usage for the synapses on a vertex slice

        :param ~pacman.model.graphs.common.Slice vertex_slice:
            The slice of the vertex to get the usage of
        :param list(~spynnaker.pyNN.models.Projection) incoming_projections:
            The projections to consider in the calculations
        """
        addr = 2 * BYTES_PER_WORD
        for proj in incoming_projections:
            addr = self.__add_matrix_size(addr, proj, vertex_slice)
        return addr

    def __add_matrix_size(self, addr, projection, vertex_slice):
        """ Add to the address the size of the matrices for the projection to
            the vertex slice

        :param int addr: The address to start from
        :param ~spynnaker.pyNN.models.Projection: The projection to add
        :param ~pacman.model.graphs.common.Slice vertex_slice:
            The slice projected to
        :rtype: int
        """
        synapse_info = projection._synapse_information
        app_edge = projection._projection_edge

        max_row_info = self.get_max_row_info(
            synapse_info, vertex_slice, app_edge)

        vertex = app_edge.pre_vertex
        n_sub_atoms = int(min(vertex.get_max_atoms_per_core(), vertex.n_atoms))
        n_sub_edges = int(math.ceil(vertex.n_atoms / n_sub_atoms))

        if max_row_info.undelayed_max_n_synapses > 0:
            size = n_sub_atoms * max_row_info.undelayed_max_bytes
            for _ in range(n_sub_edges):
                addr = MasterPopTableAsBinarySearch.get_next_allowed_address(
                    addr)
                addr += size
        if max_row_info.delayed_max_n_synapses > 0:
            size = (n_sub_atoms * max_row_info.delayed_max_bytes *
                    app_edge.n_delay_stages)
            for _ in range(n_sub_edges):
                addr = MasterPopTableAsBinarySearch.get_next_allowed_address(
                    addr)
                addr += size
        return addr

    def get_max_row_info(self, synapse_info, vertex_slice, app_edge):
        """ Get maximum row length data

        :param SynapseInformation synapse_info: Information about synapses
        :param ~pacman.model.graphs.common.Slice vertex_slice:
            The slice projected to
        :param ProjectionApplicationEdge app_edge: The edge of the projection
        """
        key = (app_edge, synapse_info, vertex_slice)
        if key in self.__max_row_info:
            return self.__max_row_info[key]
        max_row_info = get_max_row_info(
            synapse_info, vertex_slice, app_edge.n_delay_stages, app_edge)
        self.__max_row_info[key] = max_row_info
        return max_row_info

    def get_synapse_expander_size(self, incoming_projections):
        """ Get the size of the synapse expander region in bytes

        :param list(~spynnaker.pyNN.models.Projection) incoming_projections:
            The projections to consider in the calculations
        :rtype: int
        """
        size = 0
        for proj in incoming_projections:
            synapse_info = proj._synapse_information
            app_edge = proj._projection_edge
            n_sub_edges = len(
                app_edge.pre_vertex.splitter.get_out_going_slices()[0])
            if not n_sub_edges:
                vertex = app_edge.pre_vertex
                max_atoms = float(min(vertex.get_max_atoms_per_core(),
                                      vertex.n_atoms))
                n_sub_edges = int(math.ceil(vertex.n_atoms / max_atoms))
            size += self.__generator_info_size(synapse_info) * n_sub_edges

        # If anything generates data, also add some base information
        if size:
            size += SYNAPSES_BASE_GENERATOR_SDRAM_USAGE_IN_BYTES
            size += (self.__neuron_impl.get_n_synapse_types() *
                     DataType.U3232.size)
        return size

    @staticmethod
    def __generator_info_size(synapse_info):
        """ The number of bytes required by the generator information

        :param SynapseInformation synapse_info: The synapse information to use

        :rtype: int
        """
        if not synapse_info.may_generate_on_machine():
            return 0

        connector = synapse_info.connector
        dynamics = synapse_info.synapse_dynamics
        gen_size = sum((
            GeneratorData.BASE_SIZE,
            connector.gen_delay_params_size_in_bytes(synapse_info.delays),
            connector.gen_weight_params_size_in_bytes(synapse_info.weights),
            connector.gen_connector_params_size_in_bytes,
            dynamics.gen_matrix_params_size_in_bytes
        ))
        return gen_size

    @property
    def synapse_executable_suffix(self):
        """ The suffix of the executable name due to the type of synapses \
            in use.

        :rtype: str
        """
        if self.__synapse_dynamics is None:
            return ""
        return self.__synapse_dynamics.get_vertex_executable_suffix()

    @property
    def neuron_recordables(self):
        """ Get the names of variables that can be recorded by the neuron

        :rtype: list(str)
        """
        return self.__neuron_recorder.get_recordable_variables()

    @property
    def synapse_recordables(self):
        """ Get the names of variables that can be recorded by the synapses

        :rtype: list(str)
        """
        return self.__synapse_recorder.get_recordable_variables()

    def get_common_constant_sdram(
            self, n_record, n_provenance, common_regions):
        """ Get the amount of SDRAM used by common parts

        :param int n_record: The number of recording regions
        :param int n_provenance: The number of provenance items
        :param CommonRegions common_regions: Region IDs
        :rtype: int
        """
        sdram = MultiRegionSDRAM()
        sdram.add_cost(common_regions.system, SYSTEM_BYTES_REQUIREMENT)
        sdram.add_cost(
            common_regions.recording,
            get_recording_header_size(n_record) +
            get_recording_data_constant_size(n_record))
        sdram.add_cost(
            common_regions.provenance,
            ProvidesProvenanceDataFromMachineImpl.get_provenance_data_size(
                n_provenance))
        sdram.add_cost(
            common_regions.profile,
            get_profile_region_size(self.__n_profile_samples))
        return sdram

    def get_neuron_variable_sdram(self, vertex_slice):
        """ Get the amount of SDRAM per timestep used by neuron parts

        :param ~pacman.model.graphs.common.Slice vertex_slice:
            The slice of neurons to get the size of

        :rtype: int
        """
        return self.__neuron_recorder.get_variable_sdram_usage(vertex_slice)

    def get_synapse_variable_sdram(self, vertex_slice):
        """ Get the amount of SDRAM per timestep used by synapse parts

        :param ~pacman.model.graphs.common.Slice vertex_slice:
            The slice of neurons to get the size of

        :rtype: int
        """
        if isinstance(self.__synapse_dynamics,
                      AbstractSynapseDynamicsStructural):
            self.__synapse_recorder.set_max_rewires_per_ts(
                self.__synapse_dynamics.get_max_rewires_per_ts())
        return self.__synapse_recorder.get_variable_sdram_usage(vertex_slice)

    def get_neuron_constant_sdram(self, vertex_slice, neuron_regions):
        """ Get the amount of fixed SDRAM used by neuron parts

        :param ~pacman.model.graphs.common.Slice vertex_slice:
            The slice of neurons to get the size of
        :param NeuronRegions neuron_regions: Region IDs
        :rtype: int
        """
        sdram = MultiRegionSDRAM()
        sdram.add_cost(
            neuron_regions.neuron_params,
            self.get_sdram_usage_for_neuron_params(vertex_slice))
        sdram.add_cost(
            neuron_regions.neuron_recording,
            self.__neuron_recorder.get_metadata_sdram_usage_in_bytes(
                vertex_slice))
        return sdram

    def get_common_dtcm(self):
        """ Get the amount of DTCM used by common parts

        :rtype: int
        """
        # TODO: Get some real numbers here
        return 0

    def get_neuron_dtcm(self, vertex_slice):
        """ Get the amount of DTCM used by neuron parts

        :param ~pacman.model.graphs.common.Slice vertex_slice:
            The slice of neurons to get the size of

        :rtype: int
        """
        return (
            self.__neuron_impl.get_dtcm_usage_in_bytes(vertex_slice.n_atoms) +
            self.__neuron_recorder.get_dtcm_usage_in_bytes(vertex_slice)
        )

    def get_synapse_dtcm(self, vertex_slice):
        """ Get the amount of DTCM used by synapse parts

        :param ~pacman.model.graphs.common.Slice vertex_slice:
            The slice of neurons to get the size of

        :rtype: int
        """
        return self.__synapse_recorder.get_dtcm_usage_in_bytes(vertex_slice)

    def get_common_cpu(self):
        """ Get the amount of CPU used by common parts

        :rtype: int
        """
        return self._C_MAIN_BASE_N_CPU_CYCLES

    def get_neuron_cpu(self, vertex_slice):
        """ Get the amount of CPU used by neuron parts

        :param ~pacman.model.graphs.common.Slice vertex_slice:
            The slice of neurons to get the size of

        :rtype: int
        """
        return (
            self._NEURON_BASE_N_CPU_CYCLES +
            (self._NEURON_BASE_N_CPU_CYCLES_PER_NEURON *
             vertex_slice.n_atoms) +
            self.__neuron_recorder.get_n_cpu_cycles(vertex_slice.n_atoms) +
            self.__neuron_impl.get_n_cpu_cycles(vertex_slice.n_atoms))

    def get_synapse_cpu(self, vertex_slice):
        """ Get the amount of CPU used by synapse parts

        :param ~pacman.model.graphs.common.Slice vertex_slice:
            The slice of neurons to get the size of

        :rtype: int
        """
        return (
            self._SYNAPSE_BASE_N_CPU_CYCLES +
            (self._SYNAPSE_BASE_N_CPU_CYCLES_PER_NEURON *
             vertex_slice.n_atoms) +
            self.__synapse_recorder.get_n_cpu_cycles(vertex_slice.n_atoms))

    @property
    def incoming_projections(self):
        """ The projections that target this population vertex

        :rtype: list(~spynnaker.pyNN.models.projection.Projection)
        """
        return self.__incoming_projections

    @overrides(AbstractProvidesLocalProvenanceData.get_local_provenance_data)
    def get_local_provenance_data(self):
        prov_items = list()
        synapse_names = list(self.__neuron_impl.get_synapse_targets())

        # Record the min weight used for each synapse type
        for i, weight in enumerate(self.__min_weights):
            prov_items.append(ProvenanceDataItem(
                [self._label, "min_weight_{}".format(synapse_names[i])],
                weight))

        # Report any known weights that couldn't be represented
        for (weight, r_weight) in self.__weight_provenance:
            proj_info = self.__weight_provenance[weight, r_weight]
            for i, (proj, s_info) in enumerate(proj_info):
                prov_items.append(ProvenanceDataItem(
                    [self._label, proj.label,
                     s_info.connector.__class__.__name__,
                     "weight_representation"], r_weight,
                    report=(i == 0),
                    message="Weight of {} could not be represented precisely;"
                            " a weight of {} was used instead".format(
                                weight, r_weight)))

        return prov_items
