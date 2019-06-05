from pacman.model.routing_info.base_key_and_mask import BaseKeyAndMask
from six import iteritems
try:
    from collections.abc import defaultdict
except ImportError:
    from collections import defaultdict
import math
import struct
import sys
import numpy
import scipy.stats  # @UnresolvedImport
from scipy import special  # @UnresolvedImport
from spinn_utilities.helpful_functions import get_valid_components
from pacman.model.graphs.application.application_vertex import (
    ApplicationVertex)
from data_specification.enums import DataType
from spinn_front_end_common.utilities.helpful_functions import (
    locate_memory_region_for_placement)
from spinn_front_end_common.utilities.globals_variables import get_simulator
from spynnaker.pyNN.models.neuron.generator_data import GeneratorData
from spynnaker.pyNN.exceptions import SynapticConfigurationException
from spynnaker.pyNN.models.neural_projections.connectors import (
    OneToOneConnector, AbstractGenerateConnectorOnMachine)
from spynnaker.pyNN.models.neural_projections import ProjectionApplicationEdge
from spynnaker.pyNN.models.neuron import master_pop_table_generators
from spynnaker.pyNN.models.neuron.synapse_dynamics import (
    SynapseDynamicsStatic, AbstractSynapseDynamicsStructural,
    AbstractGenerateOnMachine)
from spynnaker.pyNN.models.neuron.synapse_io import SynapseIORowBased
from spynnaker.pyNN.models.spike_source.spike_source_poisson_vertex import (
    SpikeSourcePoissonVertex)
from spynnaker.pyNN.models.utility_models import DelayExtensionVertex
from spynnaker.pyNN.utilities.constants import (
    POPULATION_BASED_REGIONS, POSSION_SIGMA_SUMMATION_LIMIT)
from spynnaker.pyNN.utilities.utility_calls import (
    get_maximum_probable_value, get_n_bits)
from spynnaker.pyNN.utilities.running_stats import RunningStats

TIME_STAMP_BYTES = 4

# TODO: Make sure these values are correct (particularly CPU cycles)
_SYNAPSES_BASE_DTCM_USAGE_IN_BYTES = 28
_SYNAPSES_BASE_SDRAM_USAGE_IN_BYTES = 0
_SYNAPSES_BASE_N_CPU_CYCLES_PER_NEURON = 10
_SYNAPSES_BASE_N_CPU_CYCLES = 8

# 4 for n_edges
# 8 for post_vertex_slice.lo_atom, post_vertex_slice.n_atoms
# 4 for n_synapse_types
# 4 for n_synapse_type_bits
# 4 for n_synapse_index_bits
_SYNAPSES_BASE_GENERATOR_SDRAM_USAGE_IN_BYTES = 4 + 8 + 4 + 4 + 4

# Amount to scale synapse SDRAM estimate by to make sure the synapses fit
_SYNAPSE_SDRAM_OVERSCALE = 1.1

_ONE_WORD = struct.Struct("<I")


class SynapticManager(object):
    """ Deals with synapses
    """
    # pylint: disable=too-many-arguments, too-many-locals
    __slots__ = [
        "_delay_key_index",
        "_n_synapse_types",
        "_one_to_one_connection_dtcm_max_bytes",
        "_poptable_type",
        "_pre_run_connection_holders",
        "_retrieved_blocks",
        "_ring_buffer_sigma",
        "_spikes_per_second",
        "_synapse_dynamics",
        "_synapse_io",
        "_weight_scales",
        "_ring_buffer_shifts",
        "_gen_on_machine",
        "_max_row_info"]

    def __init__(self, n_synapse_types, ring_buffer_sigma, spikes_per_second,
                 config, population_table_type=None, synapse_io=None):
        self._n_synapse_types = n_synapse_types
        self._ring_buffer_sigma = ring_buffer_sigma
        self._spikes_per_second = spikes_per_second

        # Get the type of population table
        self._poptable_type = population_table_type
        if population_table_type is None:
            population_table_type = ("MasterPopTableAs" + config.get(
                "MasterPopTable", "generator"))
            algorithms = get_valid_components(
                master_pop_table_generators, "master_pop_table_as")
            self._poptable_type = algorithms[population_table_type]()

        # Get the synapse IO
        self._synapse_io = synapse_io
        if synapse_io is None:
            self._synapse_io = SynapseIORowBased()

        if self._ring_buffer_sigma is None:
            self._ring_buffer_sigma = config.getfloat(
                "Simulation", "ring_buffer_sigma")

        if self._spikes_per_second is None:
            self._spikes_per_second = config.getfloat(
                "Simulation", "spikes_per_second")

        # Prepare for dealing with STDP - there can only be one (non-static)
        # synapse dynamics per vertex at present
        self._synapse_dynamics = SynapseDynamicsStatic()

        # Keep the details once computed to allow reading back
        self._weight_scales = dict()
        self._ring_buffer_shifts = None
        self._delay_key_index = dict()
        self._retrieved_blocks = dict()

        # A list of connection holders to be filled in pre-run, indexed by
        # the edge the connection is for
        self._pre_run_connection_holders = defaultdict(list)

        # Limit the DTCM used by one-to-one connections
        self._one_to_one_connection_dtcm_max_bytes = config.getint(
            "Simulation", "one_to_one_connection_dtcm_max_bytes")

        # Whether to generate on machine or not for a given vertex slice
        self._gen_on_machine = dict()

        # A map of synapse information to maximum row / delayed row length and
        # size in bytes
        self._max_row_info = dict()

    @property
    def synapse_dynamics(self):
        return self._synapse_dynamics

    @synapse_dynamics.setter
    def synapse_dynamics(self, synapse_dynamics):

        # We can always override static dynamics or None
        if isinstance(self._synapse_dynamics, SynapseDynamicsStatic):
            self._synapse_dynamics = synapse_dynamics

        # We can ignore a static dynamics trying to overwrite a plastic one
        elif isinstance(synapse_dynamics, SynapseDynamicsStatic):
            pass

        # Otherwise, the dynamics must be equal
        elif not synapse_dynamics.is_same_as(self._synapse_dynamics):
            raise SynapticConfigurationException(
                "Synapse dynamics must match exactly when using multiple edges"
                "to the same population")

    @property
    def ring_buffer_sigma(self):
        return self._ring_buffer_sigma

    @ring_buffer_sigma.setter
    def ring_buffer_sigma(self, ring_buffer_sigma):
        self._ring_buffer_sigma = ring_buffer_sigma

    @property
    def spikes_per_second(self):
        return self._spikes_per_second

    @spikes_per_second.setter
    def spikes_per_second(self, spikes_per_second):
        self._spikes_per_second = spikes_per_second

    def get_maximum_delay_supported_in_ms(self, machine_time_step):
        return self._synapse_io.get_maximum_delay_supported_in_ms(
            machine_time_step)

    @property
    def vertex_executable_suffix(self):
        return self._synapse_dynamics.get_vertex_executable_suffix()

    def add_pre_run_connection_holder(
            self, connection_holder, edge, synapse_info):
        self._pre_run_connection_holders[edge, synapse_info].append(
            connection_holder)

    def get_n_cpu_cycles(self):
        # TODO: Calculate this correctly
        return 0

    def get_dtcm_usage_in_bytes(self):
        # TODO: Calculate this correctly
        return 0

    def _get_synapse_params_size(self):
        return (_SYNAPSES_BASE_SDRAM_USAGE_IN_BYTES +
                (4 * self._n_synapse_types))

    def _get_static_synaptic_matrix_sdram_requirements(self):

        # 4 for address of direct addresses, and
        # 4 for the size of the direct addresses matrix in bytes
        return 8

    def _get_max_row_info(
            self, synapse_info, post_vertex_slice, app_edge,
            machine_time_step):
        """ Get the maximum size of each row for a given slice of the vertex
        """
        key = (synapse_info, post_vertex_slice.lo_atom,
               post_vertex_slice.hi_atom)
        if key not in self._max_row_info:
            self._max_row_info[key] = self._synapse_io.get_max_row_info(
                synapse_info, post_vertex_slice,
                app_edge.n_delay_stages, self._poptable_type,
                machine_time_step, app_edge)
        return self._max_row_info[key]

    def _get_synaptic_blocks_size(
            self, post_vertex_slice, in_edges, machine_time_step):
        """ Get the size of the synaptic blocks in bytes
        """
        memory_size = self._get_static_synaptic_matrix_sdram_requirements()

        for in_edge in in_edges:
            if isinstance(in_edge, ProjectionApplicationEdge):
                for synapse_info in in_edge.synapse_information:
                    max_row_info = self._get_max_row_info(
                        synapse_info, post_vertex_slice, in_edge,
                        machine_time_step)
                    n_atoms = in_edge.pre_vertex.n_atoms
                    memory_size = self._poptable_type.get_next_allowed_address(
                        memory_size)
                    memory_size += max_row_info.undelayed_max_bytes * n_atoms
                    memory_size = self._poptable_type.get_next_allowed_address(
                        memory_size)
                    memory_size += (
                        max_row_info.delayed_max_bytes * n_atoms *
                        in_edge.n_delay_stages)

        return int(memory_size * _SYNAPSE_SDRAM_OVERSCALE)

    def _get_size_of_generator_information(self, in_edges):
        """ Get the size of the synaptic expander parameters
        """
        gen_on_machine = False
        size = 0
        for in_edge in in_edges:
            if isinstance(in_edge, ProjectionApplicationEdge):
                for synapse_info in in_edge.synapse_information:

                    # Get the number of likely vertices
                    max_atoms = sys.maxsize
                    edge_pre_vertex = in_edge.pre_vertex
                    if (isinstance(edge_pre_vertex, ApplicationVertex)):
                        max_atoms = in_edge.pre_vertex.get_max_atoms_per_core()
                    if in_edge.pre_vertex.n_atoms < max_atoms:
                        max_atoms = in_edge.pre_vertex.n_atoms
                    n_edge_vertices = int(math.ceil(
                        float(in_edge.pre_vertex.n_atoms) / float(max_atoms)))

                    # Get the size
                    connector = synapse_info.connector
                    dynamics = synapse_info.synapse_dynamics
#                    weights = synapse_info.weight
#                    delays = synapse_info.delay
                    connector_gen = isinstance(
                        connector, AbstractGenerateConnectorOnMachine) and \
                        connector.generate_on_machine(
                            synapse_info.weight, synapse_info.delay)
                    synapse_gen = isinstance(
                        dynamics, AbstractGenerateOnMachine)
                    if connector_gen and synapse_gen:
                        gen_on_machine = True
                        gen_size = sum((
                            GeneratorData.BASE_SIZE,
                            connector.gen_delay_params_size_in_bytes(
                                synapse_info.delay),
                            connector.gen_weight_params_size_in_bytes(
                                synapse_info.weight),
                            connector.gen_connector_params_size_in_bytes,
                            dynamics.gen_matrix_params_size_in_bytes
                        ))
                        size += gen_size * n_edge_vertices
        if gen_on_machine:
            size += _SYNAPSES_BASE_GENERATOR_SDRAM_USAGE_IN_BYTES
            size += self._n_synapse_types * 4
        return size

    def _get_synapse_dynamics_parameter_size(self, vertex_slice,
                                             in_edges=None):
        """ Get the size of the synapse dynamics region
        """
        # Does the size of the parameters area depend on presynaptic
        # connections in any way?
        if isinstance(self.synapse_dynamics,
                      AbstractSynapseDynamicsStructural):
            return self._synapse_dynamics.get_parameters_sdram_usage_in_bytes(
                vertex_slice.n_atoms, self._n_synapse_types,
                in_edges=in_edges)
        else:
            return self._synapse_dynamics.get_parameters_sdram_usage_in_bytes(
                vertex_slice.n_atoms, self._n_synapse_types)

    def get_sdram_usage_in_bytes(
            self, vertex_slice, in_edges, machine_time_step):
        return (
            self._get_synapse_params_size() +
            self._get_synapse_dynamics_parameter_size(vertex_slice,
                                                      in_edges=in_edges) +
            self._get_synaptic_blocks_size(
                vertex_slice, in_edges, machine_time_step) +
            self._poptable_type.get_master_population_table_size(
                vertex_slice, in_edges) +
            self._get_size_of_generator_information(in_edges))

    def _reserve_memory_regions(
            self, spec, machine_vertex, vertex_slice,
            machine_graph, all_syn_block_sz, graph_mapper):
        spec.reserve_memory_region(
            region=POPULATION_BASED_REGIONS.SYNAPSE_PARAMS.value,
            size=self._get_synapse_params_size(),
            label='SynapseParams')

        master_pop_table_sz = \
            self._poptable_type.get_exact_master_population_table_size(
                machine_vertex, machine_graph, graph_mapper)
        if master_pop_table_sz > 0:
            spec.reserve_memory_region(
                region=POPULATION_BASED_REGIONS.POPULATION_TABLE.value,
                size=master_pop_table_sz, label='PopTable')
        if all_syn_block_sz > 0:
            spec.reserve_memory_region(
                region=POPULATION_BASED_REGIONS.SYNAPTIC_MATRIX.value,
                size=all_syn_block_sz, label='SynBlocks')

        synapse_dynamics_sz = \
            self._get_synapse_dynamics_parameter_size(
                vertex_slice,
                machine_graph.get_edges_ending_at_vertex(machine_vertex))
        if synapse_dynamics_sz != 0:
            spec.reserve_memory_region(
                region=POPULATION_BASED_REGIONS.SYNAPSE_DYNAMICS.value,
                size=synapse_dynamics_sz, label='synapseDynamicsParams')

    @staticmethod
    def _ring_buffer_expected_upper_bound(
            weight_mean, weight_std_dev, spikes_per_second,
            machine_timestep, n_synapses_in, sigma):
        """ Provides expected upper bound on accumulated values in a ring\
            buffer element.

        Requires an assessment of maximum Poisson input rate.

        Assumes knowledge of mean and SD of weight distribution, fan-in\
        and timestep.

        All arguments should be assumed real values except n_synapses_in\
        which will be an integer.

        :param weight_mean: Mean of weight distribution (in either nA or\
            microSiemens as required)
        :param weight_std_dev: SD of weight distribution
        :param spikes_per_second: Maximum expected Poisson rate in Hz
        :param machine_timestep: in us
        :param n_synapses_in: No of connected synapses
        :param sigma: How many SD above the mean to go for upper bound; a\
            good starting choice is 5.0. Given length of simulation we can\
            set this for approximate number of saturation events.
        """
        # E[ number of spikes ] in a timestep
        steps_per_second = 1000000.0 / machine_timestep
        average_spikes_per_timestep = (
            float(n_synapses_in * spikes_per_second) / steps_per_second)

        # Exact variance contribution from inherent Poisson variation
        poisson_variance = average_spikes_per_timestep * (weight_mean ** 2)

        # Upper end of range for Poisson summation required below
        # upper_bound needs to be an integer
        upper_bound = int(round(average_spikes_per_timestep +
                                POSSION_SIGMA_SUMMATION_LIMIT *
                                math.sqrt(average_spikes_per_timestep)))

        # Closed-form exact solution for summation that gives the variance
        # contributed by weight distribution variation when modulated by
        # Poisson PDF.  Requires scipy.special for gamma and incomplete gamma
        # functions. Beware: incomplete gamma doesn't work the same as
        # Mathematica because (1) it's regularised and needs a further
        # multiplication and (2) it's actually the complement that is needed
        # i.e. 'gammaincc']

        weight_variance = 0.0

        if weight_std_dev > 0:
            lngamma = special.gammaln(1 + upper_bound)
            gammai = special.gammaincc(
                1 + upper_bound, average_spikes_per_timestep)

            big_ratio = (math.log(average_spikes_per_timestep) * upper_bound -
                         lngamma)

            if -701.0 < big_ratio < 701.0 and big_ratio != 0.0:
                log_weight_variance = (
                    -average_spikes_per_timestep +
                    math.log(average_spikes_per_timestep) +
                    2.0 * math.log(weight_std_dev) +
                    math.log(math.exp(average_spikes_per_timestep) * gammai -
                             math.exp(big_ratio)))
                weight_variance = math.exp(log_weight_variance)

        # upper bound calculation -> mean + n * SD
        return ((average_spikes_per_timestep * weight_mean) +
                (sigma * math.sqrt(poisson_variance + weight_variance)))

    def _get_ring_buffer_to_input_left_shifts(
            self, application_vertex, application_graph, machine_timestep,
            weight_scale):
        """ Get the scaling of the ring buffer to provide as much accuracy as\
            possible without too much overflow
        """
        weight_scale_squared = weight_scale * weight_scale
        n_synapse_types = self._n_synapse_types
        running_totals = [RunningStats() for _ in range(n_synapse_types)]
        delay_running_totals = [RunningStats() for _ in range(n_synapse_types)]
        total_weights = numpy.zeros(n_synapse_types)
        biggest_weight = numpy.zeros(n_synapse_types)
        weights_signed = False
        rate_stats = [RunningStats() for _ in range(n_synapse_types)]
        steps_per_second = 1000000.0 / machine_timestep

        for app_edge in application_graph.get_edges_ending_at_vertex(
                application_vertex):
            if isinstance(app_edge, ProjectionApplicationEdge):
                for synapse_info in app_edge.synapse_information:
                    synapse_type = synapse_info.synapse_type
                    synapse_dynamics = synapse_info.synapse_dynamics
                    connector = synapse_info.connector

                    weight_mean = (
                        synapse_dynamics.get_weight_mean(
                            connector, synapse_info.weight) * weight_scale)
                    n_connections = \
                        connector.get_n_connections_to_post_vertex_maximum()
                    weight_variance = synapse_dynamics.get_weight_variance(
                        connector, synapse_info.weight) * weight_scale_squared
                    running_totals[synapse_type].add_items(
                        weight_mean, weight_variance, n_connections)

                    delay_variance = synapse_dynamics.get_delay_variance(
                        connector, synapse_info.delay)
                    delay_running_totals[synapse_type].add_items(
                        0.0, delay_variance, n_connections)

                    weight_max = (synapse_dynamics.get_weight_maximum(
                        connector, synapse_info.weight) * weight_scale)
                    biggest_weight[synapse_type] = max(
                        biggest_weight[synapse_type], weight_max)

                    spikes_per_tick = max(
                        1.0, self._spikes_per_second / steps_per_second)
                    spikes_per_second = self._spikes_per_second
                    if isinstance(app_edge.pre_vertex,
                                  SpikeSourcePoissonVertex):
                        rate = app_edge.pre_vertex.max_rate
                        # If non-zero rate then use it; otherwise keep default
                        if (rate != 0):
                            spikes_per_second = rate
                        if hasattr(spikes_per_second, "__getitem__"):
                            spikes_per_second = numpy.max(spikes_per_second)
                        elif get_simulator().is_a_pynn_random(
                                spikes_per_second):
                            spikes_per_second = get_maximum_probable_value(
                                spikes_per_second, app_edge.pre_vertex.n_atoms)
                        prob = 1.0 - (
                            (1.0 / 100.0) / app_edge.pre_vertex.n_atoms)
                        spikes_per_tick = spikes_per_second / steps_per_second
                        spikes_per_tick = scipy.stats.poisson.ppf(
                            prob, spikes_per_tick)
                    rate_stats[synapse_type].add_items(
                        spikes_per_second, 0, n_connections)
                    total_weights[synapse_type] += spikes_per_tick * (
                        weight_max * n_connections)

                    if synapse_dynamics.are_weights_signed():
                        weights_signed = True

        max_weights = numpy.zeros(n_synapse_types)
        for synapse_type in range(n_synapse_types):
            stats = running_totals[synapse_type]
            rates = rate_stats[synapse_type]
            if delay_running_totals[synapse_type].variance == 0.0:
                max_weights[synapse_type] = max(total_weights[synapse_type],
                                                biggest_weight[synapse_type])
            else:
                max_weights[synapse_type] = min(
                    self._ring_buffer_expected_upper_bound(
                        stats.mean, stats.standard_deviation, rates.mean,
                        machine_timestep, stats.n_items,
                        self._ring_buffer_sigma),
                    total_weights[synapse_type])
                max_weights[synapse_type] = max(
                    max_weights[synapse_type], biggest_weight[synapse_type])

        # Convert these to powers
        max_weight_powers = (
            0 if w <= 0 else int(math.ceil(max(0, math.log(w, 2))))
            for w in max_weights)

        # If 2^max_weight_power equals the max weight, we have to add another
        # power, as range is 0 - (just under 2^max_weight_power)!
        max_weight_powers = (
            w + 1 if (2 ** w) <= a else w
            for w, a in zip(max_weight_powers, max_weights))

        # If we have synapse dynamics that uses signed weights,
        # Add another bit of shift to prevent overflows
        if weights_signed:
            max_weight_powers = (m + 1 for m in max_weight_powers)

        return list(max_weight_powers)

    @staticmethod
    def _get_weight_scale(ring_buffer_to_input_left_shift):
        """ Return the amount to scale the weights by to convert them from \
            floating point values to 16-bit fixed point numbers which can be \
            shifted left by ring_buffer_to_input_left_shift to produce an\
            s1615 fixed point number
        """
        return float(math.pow(2, 16 - (ring_buffer_to_input_left_shift + 1)))

    def _write_synapse_parameters(
            self, spec, ring_buffer_shifts, post_vertex_slice, weight_scale):
        # Get the ring buffer shifts and scaling factors

        spec.switch_write_focus(POPULATION_BASED_REGIONS.SYNAPSE_PARAMS.value)

        spec.write_array(ring_buffer_shifts)

        weight_scales = numpy.array([
            self._get_weight_scale(r) * weight_scale
            for r in ring_buffer_shifts])
        return weight_scales

    def _write_pop_table_padding(self, spec, next_block_start_address):
        next_block_allowed_address = self._poptable_type\
            .get_next_allowed_address(next_block_start_address)
        padding = next_block_allowed_address - next_block_start_address
        if padding != 0:

            # Pad out data file with the added alignment bytes:
            spec.comment("\nWriting population table required padding\n")
            self._write_padding(spec, padding, 0xDD)
            return next_block_allowed_address
        return next_block_start_address

    def _write_padding(self, spec, length, value):
        spec.set_register_value(register_id=15, data=length)
        spec.write_repeated_value(
            data=value, repeats=15, repeats_is_register=True,
            data_type=DataType.UINT8)

    def _write_synaptic_matrix_and_master_population_table(
            self, spec, post_slices, post_slice_index, machine_vertex,
            post_vertex_slice, all_syn_block_sz, weight_scales,
            master_pop_table_region, synaptic_matrix_region,
            direct_matrix_region, routing_info,
            graph_mapper, machine_graph, machine_time_step):
        """ Simultaneously generates both the master population table and
            the synaptic matrix.
        """
        spec.comment(
            "\nWriting Synaptic Matrix and Master Population Table:\n")

        # Track writes inside the synaptic matrix region:
        block_addr = 0

        # Get the application projection edges incoming to this machine vertex
        in_machine_edges = machine_graph.get_edges_ending_at_vertex(
            machine_vertex)
        in_edges_by_app_edge = defaultdict(list)
        for edge in in_machine_edges:
            app_edge = graph_mapper.get_application_edge(edge)
            if isinstance(app_edge, ProjectionApplicationEdge):
                in_edges_by_app_edge[app_edge].append(edge)

        # Set up the master population table
        self._poptable_type.initialise_table(spec, master_pop_table_region)

        # Set up for single synapses - write the offset of the single synapses
        # initially 0
        single_synapses = list()
        spec.switch_write_focus(synaptic_matrix_region)
        single_addr = 0

        # Store a list of synapse info to be generated on the machine
        generate_on_machine = list()

        # For each machine edge in the vertex, create a synaptic list
        for app_edge, m_edges in iteritems(in_edges_by_app_edge):

            spec.comment("\nWriting matrix for edge:{}\n".format(
                app_edge.label))
            app_key_info = self.__app_key_and_mask(
                graph_mapper, m_edges, routing_info)
            d_app_key_info = self.__delay_app_key_and_mask(
                graph_mapper, m_edges, app_edge)
            pre_slices = graph_mapper.get_slices(app_edge.pre_vertex)

            for synapse_info in app_edge.synapse_information:

                connector = synapse_info.connector
                dynamics = synapse_info.synapse_dynamics

                # If we can generate the connector on the machine, do so
                if (isinstance(
                        connector, AbstractGenerateConnectorOnMachine) and
                        connector.generate_on_machine(
                            synapse_info.weight, synapse_info.delay) and
                        isinstance(dynamics, AbstractGenerateOnMachine) and
                        dynamics.generate_on_machine and
                        self.__is_app_edge_direct(
                            app_edge, synapse_info, m_edges, graph_mapper,
                            post_vertex_slice, single_addr)):
                    generate_on_machine.append(
                        (app_edge, m_edges, synapse_info, app_key_info,
                         d_app_key_info, pre_slices))
                else:
                    block_addr, single_addr = self.__write_matrix(
                        m_edges, graph_mapper, synapse_info, pre_slices,
                        post_slices, post_slice_index, post_vertex_slice,
                        app_edge, weight_scales, machine_time_step,
                        app_key_info, d_app_key_info, block_addr, single_addr,
                        spec, master_pop_table_region, all_syn_block_sz,
                        single_synapses, routing_info)

        # Skip blocks that will be written on the machine, but add them
        # to the master population table
        generator_data = list()
        for gen_data in generate_on_machine:
            (app_edge, m_edges, synapse_info, app_key_info, d_app_key_info,
             pre_slices) = gen_data
            block_addr = self.__write_on_chip_matrix_data(
                m_edges, graph_mapper, synapse_info, pre_slices, post_slices,
                post_slice_index, post_vertex_slice, app_edge,
                machine_time_step, app_key_info, d_app_key_info, block_addr,
                spec, master_pop_table_region, all_syn_block_sz,
                generator_data, routing_info)

        # Finish the master population table
        self._poptable_type.finish_master_pop_table(
            spec, master_pop_table_region)

        # Write the size and data of single synapses to the direct region
        if single_synapses:
            single_data = numpy.concatenate(single_synapses)
            spec.reserve_memory_region(
                region=direct_matrix_region,
                size=(len(single_data) * 4) + 4,
                label='DirectMatrix')
            spec.switch_write_focus(direct_matrix_region)
            spec.write_value(len(single_data) * 4)
            spec.write_array(single_data)
        else:
            spec.reserve_memory_region(
                region=direct_matrix_region, size=4, label="DirectMatrix")
            spec.switch_write_focus(direct_matrix_region)
            spec.write_value(0)

        return generator_data

    def __is_app_edge_direct(
            self, app_edge, synapse_info, m_edges, graph_mapper,
            post_vertex_slice, single_addr):
        next_single_addr = single_addr
        for m_edge in m_edges:
            pre_slice = graph_mapper.get_slice(m_edge.pre_vertex)
            if not self.__is_direct(
                    next_single_addr, synapse_info.connector, pre_slice,
                    post_vertex_slice, app_edge.n_delay_stages > 0):
                return False
            next_single_addr += pre_slice.n_atoms * 4

    def __write_matrix(
            self, m_edges, graph_mapper, synapse_info, pre_slices, post_slices,
            post_slice_index, post_vertex_slice, app_edge, weight_scales,
            machine_time_step, app_key_info, delay_app_key_info, block_addr,
            single_addr, spec, master_pop_table_region, all_syn_block_sz,
            single_synapses, routing_info):
        # Write the synaptic matrix for an incoming application vertex
        max_row_info = self._get_max_row_info(
            synapse_info, post_vertex_slice, app_edge, machine_time_step)
        is_undelayed = bool(max_row_info.undelayed_max_n_synapses)
        is_delayed = bool(max_row_info.delayed_max_n_synapses)
        undelayed_matrix_data = list()
        delayed_matrix_data = list()
        for m_edge in m_edges:
            # Get a synaptic matrix for each machine edge
            pre_idx = graph_mapper.get_machine_vertex_index(m_edge.pre_vertex)
            pre_slice = graph_mapper.get_slice(m_edge.pre_vertex)
            (row_data, delayed_row_data) = self.__get_row_data(
                synapse_info, pre_slices, pre_idx, post_slices,
                post_slice_index, pre_slice, post_vertex_slice, app_edge,
                self._n_synapse_types, weight_scales, machine_time_step,
                m_edge, max_row_info)
            # If there is a single edge here, we allow the one-to-one direct
            # matrix to be used by using write_machine_matrix; it will make
            # no difference if this isn't actually a direct edge since there
            # is only one anyway...
            if row_data.size and (app_key_info is None or len(m_edges) == 1):
                r_info = routing_info.get_routing_info_for_edge(m_edge)
                block_addr, single_addr = self.__write_machine_matrix(
                    block_addr, single_addr, spec, master_pop_table_region,
                    max_row_info.undelayed_max_n_synapses,
                    max_row_info.undelayed_max_words, r_info, row_data,
                    synapse_info.connector, pre_slice, post_vertex_slice,
                    single_synapses, all_syn_block_sz, is_delayed)
            elif is_undelayed:
                # If there is an app_key, save the data to be written later
                # Note: row_data will not be blank here since we told it to
                # generate a matrix of a given size
                undelayed_matrix_data.append(
                    (m_edge, pre_slice, row_data))
            if delay_app_key_info is None and delayed_row_data.size:
                delay_key = (app_edge.pre_vertex,
                             pre_slice.lo_atom, pre_slice.hi_atom)
                r_info = self._delay_key_index[delay_key]
                block_addr, single_addr = self.__write_machine_matrix(
                    block_addr, single_addr, spec, master_pop_table_region,
                    max_row_info.delayed_max_n_synapses,
                    max_row_info.delayed_max_words, r_info, delayed_row_data,
                    synapse_info.connector, pre_slice, post_vertex_slice,
                    single_synapses, all_syn_block_sz, True)
            elif is_delayed:
                # If there is a delay_app_key, save the data for delays
                # Note delayed_row_data will not be blank as above.
                delayed_matrix_data.append(
                    (m_edge, pre_slice, delayed_row_data))

        # If there is an app key, add a single matrix and entry
        # to the population table but also put in padding
        # between tables when necessary
        if app_key_info is not None and len(m_edges) > 1 and is_undelayed:
            block_addr = self.__write_app_matrix(
                block_addr, spec, master_pop_table_region,
                max_row_info.undelayed_max_words,
                max_row_info.undelayed_max_bytes, app_key_info,
                undelayed_matrix_data, all_syn_block_sz, 1)
        if delay_app_key_info is not None and is_delayed:
            block_addr = self.__write_app_matrix(
                block_addr, spec, master_pop_table_region,
                max_row_info.delayed_max_words, max_row_info.delayed_max_bytes,
                delay_app_key_info, delayed_matrix_data, all_syn_block_sz,
                app_edge.n_delay_stages)

        return block_addr, single_addr

    def __write_app_matrix(
            self, block_addr, spec, master_pop_table_region, max_words,
            max_bytes, app_key_info, matrix_data, all_syn_block_sz, n_ranges):
        # Write a matrix for the whole application vertex with padding in the
        # appropriate places to make the keys work
        block_addr = self._write_pop_table_padding(spec, block_addr)
        self._poptable_type.update_master_population_table(
            spec, block_addr, max_words, app_key_info.key_and_mask,
            app_key_info.core_mask, app_key_info.core_shift,
            app_key_info.n_neurons, master_pop_table_region)
        # Implicit assumption that no machine-level row_data is ever empty;
        # this must be true in the current code, because the row length is
        # fixed for all synaptic matrices from the same source application
        # vertex
        for _, pre_slice, row_data in matrix_data:
            spec.write_array(row_data)
            n_rows = pre_slice.n_atoms * n_ranges
            block_addr = block_addr + (max_bytes * n_rows)
            if block_addr > all_syn_block_sz:
                raise Exception(
                    "Too much synaptic memory has been written: {} of {} "
                    .format(block_addr, all_syn_block_sz))
        return block_addr

    def __write_machine_matrix(
            self, block_addr, single_addr, spec, master_pop_table_region,
            max_synapses, max_words, r_info, row_data, connector, pre_slice,
            post_vertex_slice, single_synapses, all_syn_block_sz, is_delayed):
        # Write a matrix for an incoming machine vertex
        if max_synapses == 1 and self.__is_direct(
                single_addr, connector, pre_slice, post_vertex_slice,
                is_delayed):
            single_rows = row_data.reshape(-1, 4)[:, 3]
            self._poptable_type.update_master_population_table(
                spec, single_addr, max_words,
                r_info.first_key_and_mask, 0, 0, 0, master_pop_table_region,
                is_single=True)
            single_synapses.append(single_rows)
            single_addr = single_addr + (len(single_rows) * 4)
        else:
            block_addr = self._write_pop_table_padding(spec, block_addr)
            self._poptable_type.update_master_population_table(
                spec, block_addr, max_words,
                r_info.first_key_and_mask, 0, 0, 0, master_pop_table_region)
            spec.write_array(row_data)
            block_addr = block_addr + (len(row_data) * 4)
            if block_addr > all_syn_block_sz:
                raise Exception(
                    "Too much synaptic memory has been written: {} of {} "
                    .format(block_addr, all_syn_block_sz))
        return block_addr, single_addr

    @staticmethod
    def __count_trailing_0s(mask):
        # Count zeros at the LSB of a number
        # NOTE assumes a 32-bit number
        for i in range(32):
            if mask & (1 << i):
                return i
        return 32

    def __check_keys_adjacent(self, keys, mask, mask_size):
        # Check that keys are all adjacent
        key_increment = (1 << mask_size)
        last_key = None
        last_slice = None
        for i, (key, v_slice) in enumerate(keys):
            if last_key is None:
                last_key = key
                last_slice = v_slice
            elif (last_key + key_increment) != key:
                return False
            elif (i + 1) < len(keys) and last_slice.n_atoms != v_slice.n_atoms:
                return False
            elif (last_slice.hi_atom + 1) != v_slice.lo_atom:
                return False
            last_key = key
            last_slice = v_slice
        return True

    def __get_app_key_and_mask(self, keys, mask, mask_size):
        # The key is the smallest key, the mask is the one that fits all the
        # keys
        key = keys[0][0]
        n_extra_mask_bits = int(math.ceil(math.log(len(keys), 2)))
        core_mask = (((2 ** n_extra_mask_bits) - 1))
        new_mask = mask & ~(core_mask << mask_size)
        return key, new_mask, core_mask

    def __app_key_and_mask(self, graph_mapper, m_edges, routing_info):
        # Work out if the keys allow the machine vertices to be merged
        mask = None
        keys = list()

        # Can be merged only of all the masks are the same
        for m_edge in m_edges:
            rinfo = routing_info.get_routing_info_for_edge(m_edge)
            vertex_slice = graph_mapper.get_slice(m_edge.pre_vertex)
            if rinfo is None:
                return None
            if mask is not None and rinfo.first_mask != mask:
                return None
            mask = rinfo.first_mask
            keys.append((rinfo.first_key, vertex_slice))

        if mask is None:
            return None

        # Can be merged only if keys are adjacent outside the mask
        keys = sorted(keys, key=lambda item: item[0])
        mask_size = self.__count_trailing_0s(mask)
        if not self.__check_keys_adjacent(keys, mask, mask_size):
            return None

        app_key, app_mask, core_mask = self.__get_app_key_and_mask(
            keys, mask, mask_size)
        return _AppKeyInfo(app_key, app_mask, core_mask, mask_size,
                           keys[0][1].n_atoms)

    def __delay_app_key_and_mask(self, graph_mapper, m_edges, app_edge):
        # Work out if the keys allow the machine vertices to be
        # merged
        mask = None
        keys = list()

        # Can be merged only of all the masks are the same
        for m_edge in m_edges:
            pre_vertex_slice = graph_mapper.get_slice(m_edge.pre_vertex)
            delay_info_key = (app_edge.pre_vertex, pre_vertex_slice.lo_atom,
                              pre_vertex_slice.hi_atom)
            rinfo = self._delay_key_index.get(delay_info_key, None)
            if rinfo is None:
                return None
            if mask is not None and rinfo.first_mask != mask:
                return None
            mask = rinfo.first_mask
            keys.append((rinfo.first_key, pre_vertex_slice))

        # Can be merged only if keys are adjacent outside the mask
        keys = sorted(keys)
        mask_size = self.__count_trailing_0s(mask)
        if not self.__check_keys_adjacent(keys, mask, mask_size):
            return None

        app_key, app_mask, core_mask = self.__get_app_key_and_mask(
            keys, mask, mask_size)
        return _AppKeyInfo(app_key, app_mask, core_mask, mask_size,
                           keys[0][1].n_atoms * app_edge.n_delay_stages)

    def __write_on_chip_matrix_data(
            self, m_edges, graph_mapper, synapse_info, pre_slices, post_slices,
            post_slice_index, post_vertex_slice, app_edge, machine_time_step,
            app_key_info, delay_app_key_info, block_addr, spec,
            master_pop_table_region, all_syn_block_sz, generator_data,
            routing_info):
        # Write the data to generate a matrix on-chip
        max_row_info = self._get_max_row_info(
            synapse_info, post_vertex_slice, app_edge, machine_time_step)
        is_undelayed = bool(max_row_info.undelayed_max_n_synapses)
        is_delayed = bool(max_row_info.delayed_max_n_synapses)

        # Create initial master population table entries if a single
        # matrix is to be created for the whole application vertex
        syn_block_addr = 0xFFFFFFFF
        if is_undelayed and app_key_info is not None:
            block_addr, syn_block_addr = self.__reserve_mpop_block(
                block_addr, spec, master_pop_table_region,
                max_row_info.undelayed_max_bytes,
                max_row_info.undelayed_max_words, app_key_info,
                all_syn_block_sz, app_edge.pre_vertex.n_atoms)
            syn_max_addr = block_addr
        delay_block_addr = 0xFFFFFFFF
        if is_delayed and delay_app_key_info is not None:
            block_addr, delay_block_addr = self.__reserve_mpop_block(
                block_addr, spec, master_pop_table_region,
                max_row_info.delayed_max_bytes, max_row_info.delayed_max_words,
                delay_app_key_info, all_syn_block_sz,
                app_edge.pre_vertex.n_atoms * app_edge.n_delay_stages)
            delay_max_addr = block_addr

        for m_edge in m_edges:
            syn_mat_offset = syn_block_addr
            d_mat_offset = delay_block_addr
            pre_idx = graph_mapper.get_machine_vertex_index(m_edge.pre_vertex)
            pre_slice = graph_mapper.get_slice(m_edge.pre_vertex)

            # Write the information needed to generate delays
            self.__write_on_chip_delay_data(
                max_row_info, app_edge, pre_slices, pre_idx, post_slices,
                post_slice_index, pre_slice, post_vertex_slice, synapse_info,
                machine_time_step)

            if is_undelayed and app_key_info is not None:
                # If there is a single matrix for the app vertex, jump over the
                # matrix and any padding space
                syn_block_addr = self.__next_app_syn_block_addr(
                    syn_block_addr, pre_slice.n_atoms,
                    max_row_info.undelayed_max_bytes, syn_max_addr)
            elif is_undelayed:
                # If there isn't a single matrix, add master population table
                # entries for each incoming machine vertex
                r_info = routing_info.get_routing_info_for_edge(m_edge)
                m_key_info = _AppKeyInfo(
                    r_info.first_key, r_info.first_mask, 0, 0, 0)
                block_addr, syn_mat_offset = self.__reserve_mpop_block(
                    block_addr, spec, master_pop_table_region,
                    max_row_info.undelayed_max_bytes,
                    max_row_info.undelayed_max_words, m_key_info,
                    all_syn_block_sz, pre_slice.n_atoms)
            # Do the same as the above for delay vertices too
            if is_delayed and delay_app_key_info is not None:
                delay_block_addr = self.__next_app_syn_block_addr(
                    delay_block_addr,
                    pre_slice.n_atoms * app_edge.n_delay_stages,
                    max_row_info.delayed_max_bytes, delay_max_addr)
            elif is_delayed:
                delay_key = (app_edge.pre_vertex, pre_slice.lo_atom,
                             pre_slice.hi_atom)
                r_info = self._delay_key_index[delay_key]
                m_key_info = _AppKeyInfo(
                    r_info.first_key, r_info.first_mask, 0, 0, 0)
                block_addr, d_mat_offset = self.__reserve_mpop_block(
                    block_addr, spec, master_pop_table_region,
                    max_row_info.delayed_max_bytes,
                    max_row_info.delayed_max_words, m_key_info,
                    all_syn_block_sz,
                    pre_slice.n_atoms * app_edge.n_delay_stages)

            # Create the generator data and note it exists for this post vertex
            generator_data.append(GeneratorData(
                syn_mat_offset // 4, d_mat_offset // 4,
                max_row_info.undelayed_max_words,
                max_row_info.delayed_max_words,
                max_row_info.undelayed_max_n_synapses,
                max_row_info.delayed_max_n_synapses, pre_slices, pre_idx,
                post_slices, post_slice_index, pre_slice, post_vertex_slice,
                synapse_info, app_edge.n_delay_stages + 1, machine_time_step))
            key = (post_vertex_slice.lo_atom, post_vertex_slice.hi_atom)
            self._gen_on_machine[key] = True
        return block_addr

    def __reserve_mpop_block(
            self, block_addr, spec, master_pop_table_region, max_bytes,
            max_words, app_key_info, all_syn_block_sz, n_rows):
        # Reserve a block in the master population table
        block_addr = self._poptable_type.get_next_allowed_address(
            block_addr)
        self._poptable_type.update_master_population_table(
            spec, block_addr, max_words, app_key_info.key_and_mask,
            app_key_info.core_mask, app_key_info.core_shift,
            app_key_info.n_neurons, master_pop_table_region)
        syn_block_addr = block_addr
        block_addr += max_bytes * n_rows
        if block_addr > all_syn_block_sz:
            raise Exception(
                "Too much synaptic memory has been reserved: {} of {}".format(
                    block_addr, all_syn_block_sz))
        return block_addr, syn_block_addr

    def __next_app_syn_block_addr(
            self, block_addr, n_rows, max_bytes, max_pos):
        # Get the next block address after the sub-table
        block_addr += (max_bytes * n_rows)
        if block_addr > max_pos:
            raise Exception(
                "Too much synaptic memory has been reserved: {} of {}".format(
                    block_addr, max_pos))
        return block_addr

    def __write_on_chip_delay_data(
            self, max_row_info, app_edge, pre_slices, pre_slice_index,
            post_slices, post_slice_index, pre_vertex_slice, post_vertex_slice,
            synapse_info, machine_time_step):
        # If delay edge exists, tell this about the data too, so it can
        # generate its own data
        if (max_row_info.delayed_max_n_synapses > 0 and
                app_edge.delay_edge is not None):
            app_edge.delay_edge.pre_vertex.add_generator_data(
                max_row_info.undelayed_max_n_synapses,
                max_row_info.delayed_max_n_synapses,
                pre_slices, pre_slice_index, post_slices, post_slice_index,
                pre_vertex_slice, post_vertex_slice, synapse_info,
                app_edge.n_delay_stages + 1, machine_time_step)
        elif max_row_info.delayed_max_n_synapses != 0:
            raise Exception(
                "Found delayed items but no delay "
                "machine edge for {}".format(app_edge.label))

    def __get_row_data(
            self, synapse_info, pre_slices, pre_slice_idx, post_slices,
            post_slice_index, pre_vertex_slice, post_vertex_slice, app_edge,
            n_synapse_types, weight_scales, machine_time_step, machine_edge,
            max_row_info):
        (row_data, delayed_row_data, delayed_source_ids,
         delay_stages) = self._synapse_io.get_synapses(
            synapse_info, pre_slices, pre_slice_idx, post_slices,
            post_slice_index, pre_vertex_slice, post_vertex_slice,
            app_edge.n_delay_stages, n_synapse_types, weight_scales,
            machine_time_step, app_edge, machine_edge, max_row_info)

        if app_edge.delay_edge is not None:
            app_edge.delay_edge.pre_vertex.add_delays(
                pre_vertex_slice, delayed_source_ids, delay_stages)
        elif delayed_source_ids.size != 0:
            raise Exception(
                "Found delayed source IDs but no delay "
                "machine edge for {}".format(app_edge.label))

        if (app_edge, synapse_info) in self._pre_run_connection_holders:
            for conn_holder in self._pre_run_connection_holders[
                    app_edge, synapse_info]:
                conn_holder.add_connections(self._synapse_io.read_synapses(
                    synapse_info, pre_vertex_slice, post_vertex_slice,
                    max_row_info.undelayed_max_words,
                    max_row_info.delayed_max_words, n_synapse_types,
                    weight_scales, row_data, delayed_row_data,
                    app_edge.n_delay_stages, machine_time_step))
                conn_holder.finish()

        return (row_data, delayed_row_data)

    def __is_direct(
            self, single_addr, connector, pre_vertex_slice, post_vertex_slice,
            is_delayed):
        """ Determine if the given connection can be done with a "direct"\
            synaptic matrix - this must have an exactly 1 entry per row
        """
        return (
            not is_delayed and
            isinstance(connector, OneToOneConnector) and
            (single_addr + (pre_vertex_slice.n_atoms * 4) <=
                self._one_to_one_connection_dtcm_max_bytes) and
            (pre_vertex_slice.lo_atom == post_vertex_slice.lo_atom) and
            (pre_vertex_slice.hi_atom == post_vertex_slice.hi_atom))

    def _get_ring_buffer_shifts(
            self, application_vertex, application_graph, machine_timestep,
            weight_scale):
        """ Get the ring buffer shifts for this vertex
        """
        if self._ring_buffer_shifts is None:
            self._ring_buffer_shifts = \
                self._get_ring_buffer_to_input_left_shifts(
                    application_vertex, application_graph, machine_timestep,
                    weight_scale)
        return self._ring_buffer_shifts

    def write_data_spec(
            self, spec, application_vertex, post_vertex_slice, machine_vertex,
            placement, machine_graph, application_graph, routing_info,
            graph_mapper, weight_scale, machine_time_step, placements):
        # Create an index of delay keys into this vertex
        for m_edge in machine_graph.get_edges_ending_at_vertex(machine_vertex):
            app_edge = graph_mapper.get_application_edge(m_edge)
            if isinstance(app_edge.pre_vertex, DelayExtensionVertex):
                pre_vertex_slice = graph_mapper.get_slice(
                    m_edge.pre_vertex)
                self._delay_key_index[app_edge.pre_vertex.source_vertex,
                                      pre_vertex_slice.lo_atom,
                                      pre_vertex_slice.hi_atom] = \
                    routing_info.get_routing_info_for_edge(m_edge)

        post_slices = graph_mapper.get_slices(application_vertex)
        post_slice_idx = graph_mapper.get_machine_vertex_index(machine_vertex)

        # Reserve the memory
        in_edges = application_graph.get_edges_ending_at_vertex(
            application_vertex)
        all_syn_block_sz = self._get_synaptic_blocks_size(
            post_vertex_slice, in_edges, machine_time_step)
        self._reserve_memory_regions(
            spec, machine_vertex, post_vertex_slice, machine_graph,
            all_syn_block_sz, graph_mapper)

        ring_buffer_shifts = self._get_ring_buffer_shifts(
            application_vertex, application_graph, machine_time_step,
            weight_scale)
        weight_scales = self._write_synapse_parameters(
            spec, ring_buffer_shifts, post_vertex_slice, weight_scale)

        gen_data = self._write_synaptic_matrix_and_master_population_table(
            spec, post_slices, post_slice_idx, machine_vertex,
            post_vertex_slice, all_syn_block_sz, weight_scales,
            POPULATION_BASED_REGIONS.POPULATION_TABLE.value,
            POPULATION_BASED_REGIONS.SYNAPTIC_MATRIX.value,
            POPULATION_BASED_REGIONS.DIRECT_MATRIX.value,
            routing_info, graph_mapper, machine_graph, machine_time_step)

        if isinstance(self._synapse_dynamics,
                      AbstractSynapseDynamicsStructural):
            self._synapse_dynamics.write_parameters(
                spec,
                POPULATION_BASED_REGIONS.SYNAPSE_DYNAMICS.value,
                machine_time_step, weight_scales,
                application_graph=application_graph,
                machine_graph=machine_graph,
                app_vertex=application_vertex, post_slice=post_vertex_slice,
                machine_vertex=machine_vertex,
                graph_mapper=graph_mapper, routing_info=routing_info)
        else:
            self._synapse_dynamics.write_parameters(
                spec,
                POPULATION_BASED_REGIONS.SYNAPSE_DYNAMICS.value,
                machine_time_step, weight_scales)

        self._weight_scales[placement] = weight_scales

        self._write_on_machine_data_spec(
            spec, post_vertex_slice, weight_scales, gen_data)

    def clear_connection_cache(self):
        self._retrieved_blocks = dict()

    def get_connections_from_machine(
            self, transceiver, placement, machine_edge, graph_mapper,
            routing_infos, synapse_info, machine_time_step,
            using_extra_monitor_cores, placements=None, data_receiver=None,
            sender_extra_monitor_core_placement=None,
            extra_monitor_cores_for_router_timeout=None,
            handle_time_out_configuration=True, fixed_routes=None):
        app_edge = graph_mapper.get_application_edge(machine_edge)
        if not isinstance(app_edge, ProjectionApplicationEdge):
            return None

        # Get details for extraction
        pre_vertex_slice = graph_mapper.get_slice(machine_edge.pre_vertex)
        post_vertex_slice = graph_mapper.get_slice(machine_edge.post_vertex)

        # Get the key for the pre_vertex
        key = routing_infos.get_first_key_for_edge(machine_edge)

        # Get the key for the delayed pre_vertex
        delayed_key = None
        if app_edge.delay_edge is not None:
            delayed_key = self._delay_key_index[
                app_edge.pre_vertex, pre_vertex_slice.lo_atom,
                pre_vertex_slice.hi_atom].first_key

        # Get the block for the connections from the pre_vertex
        master_pop_table, direct_synapses, indirect_synapses = \
            self.__compute_addresses(transceiver, placement)
        data, max_row_length = self._retrieve_synaptic_block(
            transceiver, placement, master_pop_table, indirect_synapses,
            direct_synapses, key, pre_vertex_slice.n_atoms, synapse_info.index,
            using_extra_monitor_cores, placements, data_receiver,
            sender_extra_monitor_core_placement,
            extra_monitor_cores_for_router_timeout, fixed_routes)

        # Get the block for the connections from the delayed pre_vertex
        delayed_data = None
        delayed_max_row_len = 0
        if delayed_key is not None:
            delayed_data, delayed_max_row_len = self._retrieve_synaptic_block(
                transceiver, placement, master_pop_table, indirect_synapses,
                direct_synapses, delayed_key,
                pre_vertex_slice.n_atoms * app_edge.n_delay_stages,
                synapse_info.index, using_extra_monitor_cores, placements,
                data_receiver, sender_extra_monitor_core_placement,
                extra_monitor_cores_for_router_timeout,
                handle_time_out_configuration, fixed_routes)

        # Convert the blocks into connections
        return self._synapse_io.read_synapses(
            synapse_info, pre_vertex_slice, post_vertex_slice,
            max_row_length, delayed_max_row_len, self._n_synapse_types,
            self._weight_scales[placement], data, delayed_data,
            app_edge.n_delay_stages, machine_time_step)

    def __compute_addresses(self, transceiver, placement):
        """ Helper for computing the addresses of the master pop table and\
            synaptic-matrix-related bits.
        """
        master_pop_table = locate_memory_region_for_placement(
            placement, POPULATION_BASED_REGIONS.POPULATION_TABLE.value,
            transceiver)
        synaptic_matrix = locate_memory_region_for_placement(
            placement, POPULATION_BASED_REGIONS.SYNAPTIC_MATRIX.value,
            transceiver)
        direct_synapses = locate_memory_region_for_placement(
            placement, POPULATION_BASED_REGIONS.DIRECT_MATRIX.value,
            transceiver) + 4
        return master_pop_table, direct_synapses, synaptic_matrix

    def _retrieve_synaptic_block(
            self, transceiver, placement, master_pop_table_address,
            indirect_synapses_address, direct_synapses_address,
            key, n_rows, index, using_extra_monitor_cores, placements=None,
            data_receiver=None, sender_extra_monitor_core_placement=None,
            extra_monitor_cores_for_router_timeout=None,
            handle_time_out_configuration=True, fixed_routes=None):
        """ Read in a synaptic block from a given processor and vertex on\
            the machine
        """
        # See if we have already got this block
        if (placement, key, index) in self._retrieved_blocks:
            return self._retrieved_blocks[placement, key, index]

        items = self._poptable_type.extract_synaptic_matrix_data_location(
            key, master_pop_table_address, transceiver,
            placement.x, placement.y)
        if index >= len(items):
            return None, None

        max_row_length, synaptic_block_offset, is_single = items[index]
        if max_row_length == 0:
            return None, None

        block = None
        if max_row_length > 0 and synaptic_block_offset is not None:
            # if exploiting the extra monitor cores, need to set the machine
            # for data extraction mode
            if using_extra_monitor_cores and handle_time_out_configuration:
                data_receiver.set_cores_for_data_extraction(
                    transceiver, extra_monitor_cores_for_router_timeout,
                    placements)

            # read in the synaptic block
            if not is_single:
                block = self.__read_multiple_synaptic_blocks(
                    transceiver, data_receiver, placement, n_rows,
                    max_row_length,
                    indirect_synapses_address + synaptic_block_offset,
                    using_extra_monitor_cores,
                    sender_extra_monitor_core_placement, fixed_routes)
            else:
                block, max_row_length = self.__read_single_synaptic_block(
                    transceiver, data_receiver, placement, n_rows,
                    direct_synapses_address + synaptic_block_offset,
                    using_extra_monitor_cores,
                    sender_extra_monitor_core_placement, fixed_routes)

            if using_extra_monitor_cores and handle_time_out_configuration:
                data_receiver.unset_cores_for_data_extraction(
                    transceiver, extra_monitor_cores_for_router_timeout,
                    placements)

        self._retrieved_blocks[placement, key, index] = (block, max_row_length)
        return block, max_row_length

    def __read_multiple_synaptic_blocks(
            self, transceiver, data_receiver, placement, n_rows,
            max_row_length, address, using_extra_monitor_cores,
            sender_extra_monitor_core_placement, fixed_routes):
        """ Read in an array of synaptic blocks.
        """
        # calculate the synaptic block size in bytes
        synaptic_block_size = self._synapse_io.get_block_n_bytes(
            max_row_length, n_rows)

        # read in the synaptic block
        if using_extra_monitor_cores:
            return data_receiver.get_data(
                transceiver, sender_extra_monitor_core_placement, address,
                synaptic_block_size, fixed_routes)
        return transceiver.read_memory(
            placement.x, placement.y, address, synaptic_block_size)

    def __read_single_synaptic_block(
            self, transceiver, data_receiver, placement, n_rows, address,
            using_extra_monitor_cores, sender_extra_monitor_core_placement,
            fixed_routes):
        """ Read in a single synaptic block.
        """
        # The data is one per row
        synaptic_block_size = n_rows * 4

        # read in the synaptic row data
        if using_extra_monitor_cores:
            single_block = data_receiver.get_data(
                transceiver, sender_extra_monitor_core_placement, address,
                synaptic_block_size, fixed_routes)
        else:
            single_block = transceiver.read_memory(
                placement.x, placement.y, address, synaptic_block_size)

        # Convert the block into a set of rows
        numpy_block = numpy.zeros((n_rows, 4), dtype="uint32")
        numpy_block[:, 3] = numpy.asarray(
            single_block, dtype="uint8").view("uint32")
        numpy_block[:, 1] = 1
        return bytearray(numpy_block.tobytes()), 1

    # inherited from AbstractProvidesIncomingPartitionConstraints
    def get_incoming_partition_constraints(self):
        return self._poptable_type.get_edge_constraints()

    def _write_on_machine_data_spec(
            self, spec, post_vertex_slice, weight_scales, generator_data):
        """ Write the data spec for the synapse expander

        :param spec: The specification to write to
        :param post_vertex_slice: The slice of the vertex being written
        :param weight_scales: scaling of weights on each synapse
        """
        if not generator_data:
            return

        n_bytes = (
            _SYNAPSES_BASE_GENERATOR_SDRAM_USAGE_IN_BYTES +
            (self._n_synapse_types * 4))
        for data in generator_data:
            n_bytes += data.size

        spec.reserve_memory_region(
            region=POPULATION_BASED_REGIONS.CONNECTOR_BUILDER.value,
            size=n_bytes, label="ConnectorBuilderRegion")
        spec.switch_write_focus(
            region=POPULATION_BASED_REGIONS.CONNECTOR_BUILDER.value)

        spec.write_value(len(generator_data))
        spec.write_value(post_vertex_slice.lo_atom)
        spec.write_value(post_vertex_slice.n_atoms)
        spec.write_value(self._n_synapse_types)
        spec.write_value(get_n_bits(self._n_synapse_types))
        n_neuron_id_bits = get_n_bits(post_vertex_slice.n_atoms)
        spec.write_value(n_neuron_id_bits)
        for w in weight_scales:
            spec.write_value(int(w), data_type=DataType.INT32)

        for data in generator_data:
            spec.write_array(data.gen_data)

    def gen_on_machine(self, vertex_slice):
        """ True if the synapses should be generated on the machine
        """
        key = (vertex_slice.lo_atom, vertex_slice.hi_atom)
        return self._gen_on_machine.get(key, False)


class _AppKeyInfo(object):

    __slots__ = ["app_key", "app_mask", "core_mask", "core_shift", "n_neurons"]

    def __init__(self, app_key, app_mask, core_mask, core_shift, n_neurons):
        self.app_key = app_key
        self.app_mask = app_mask
        self.core_mask = core_mask
        self.core_shift = core_shift
        self.n_neurons = n_neurons

    @property
    def key_and_mask(self):
        return BaseKeyAndMask(self.app_key, self.app_mask)
