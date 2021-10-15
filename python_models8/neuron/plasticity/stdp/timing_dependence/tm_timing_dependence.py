from spinn_utilities.overrides import overrides
from data_specification.enums import DataType
from spinn_front_end_common.utilities.constants import BYTES_PER_SHORT, BYTES_PER_WORD
from spinn_front_end_common.utilities.globals_variables import (
    machine_time_step_ms)
from spynnaker.pyNN.models.neuron.plasticity.stdp.common import (
    float_to_fixed, get_exp_lut_array)
from spynnaker.pyNN.models.neuron.plasticity.stdp.timing_dependence import (
    AbstractTimingDependence)
from spynnaker.pyNN.models.neuron.plasticity.stdp.synapse_structure import (
    SynapseStructureWeightOnly)


class TsodyksMarkramTimingDependence(AbstractTimingDependence):
    __slots__ = [
        "_a_minus",
        "_a_plus",
        "_tau_d",
        "_tau_d_data",
        "_tau_f",
        "_tau_f_data",
        "_tau_syn",
        "_tau_syn_data",
        "_synapse_structure"]

    NUM_PARAMETERS = 2

    # noinspection PyPep8Naming
    def __init__(
            self,

            # TODO: update parameters
            tau_f,
            tau_d,
            tau_syn=1.0,

            A_plus=1.0, A_minus=1.0):

        # TODO: Store any parameters
        self._tau_f = tau_f
        self._tau_d = tau_d
        self._tau_syn = tau_syn

        # TODO: Update to match the synapse structure in the C code
        self._synapse_structure = SynapseStructureWeightOnly()

        # Are these in the c code?
        self._a_plus = A_plus
        self._a_minus = A_minus

            # provenance data
        ts = machine_time_step_ms()
        self._tau_f_data = get_exp_lut_array(ts, self._tau_f)
        self._tau_d_data = get_exp_lut_array(ts, self._tau_d)
        # self._tau_syn_data = get_exp_lut_array(ts, self._tau_syn)

    # TODO: Add getters and setters for parameters

    @property
    def tau_f(self):
        return self._tau_f

    @tau_f.setter
    def tau_f(self, tau_f):
        self._tau_f = tau_f

    @property
    def tau_d(self):
        return self._tau_d

    @tau_d.setter
    def tau_d(self, tau_d):
        self._tau_d = tau_d
    
    @property
    def tau_syn(self):
        return self._tau_syn

    @tau_syn.setter
    def tau_syn(self, tau_syn):
        self._tau_syn = tau_syn

    @overrides(AbstractTimingDependence.is_same_as)
    def is_same_as(self, timing_dependence):
        # TODO: Update with the correct class name
        if not isinstance(timing_dependence, TsodyksMarkramTimingDependence):
            return False

        # TODO: update to check parameters are equal
        return (self._tau_f == timing_dependence.tau_f and
                self._tau_d == timing_dependence.tau_d)# and 
                # self._tau_syn == timing_dependence.tau_syn)

    @property
    def vertex_executable_suffix(self):
        """ The suffix to be appended to the vertex executable for this rule
        """
        # TODO: Add the extension to be added to the binary executable name
        # to indicate that it is compiled with this timing dependence
        # Note: The expected format of the binary name is:
        #    <neuron_model>_stdp[_mad|]_<timing_dependence>_<weight_dependence>
        return "tm_timing"

    @property
    def pre_trace_n_bytes(self):
        """ The number of bytes used by the pre-trace of the rule per neuron
        """
        # TODO: update to match the number of bytes in the pre_trace_t data
        # structure in the C code
        return BYTES_PER_SHORT

    @overrides(AbstractTimingDependence.get_parameters_sdram_usage_in_bytes)
    def get_parameters_sdram_usage_in_bytes(self):
        # TODO: update to match the number of bytes used by the parameters
        return (2 * BYTES_PER_WORD) * (len(self._tau_f_data) +
                                 len(self._tau_d_data))# +
                                #  len(self._tau_syn_data))

    @property
    def n_weight_terms(self):
        """ The number of weight terms expected by this timing rule
        """
        # TODO: update to match the number of weight terms expected in the
        # weight rule according to the C code
        return 1

    @overrides(AbstractTimingDependence.write_parameters)
    def write_parameters(self, spec, weight_scales):
        # TODO: update to write the parameters
        # Write parameters (fixed point) to spec
        fixed_point_tau_f = float_to_fixed(self._tau_f)
        fixed_point_tau_d = float_to_fixed(self._tau_d)
        # fixed_point_tau_syn = float_to_fixed(self._tau_syn)

        spec.write_value(data=fixed_point_tau_f, data_type=DataType.INT32)
        spec.write_value(data=fixed_point_tau_d, data_type=DataType.INT32)
        # spec.write_value(data=fixed_point_tau_syn, data_type=DataType.INT32)

        # Write lookup tables
        spec.write_array(self._tau_f_data)
        spec.write_array(self._tau_d_data)
        # spec.write_array(self._tau_syn_data)

    @overrides(AbstractTimingDependence.get_parameter_names)
    def get_parameter_names(self):
        return ['tau_f', 'tau_d']#, 'tau_syn']

    @property
    def synaptic_structure(self):
        """ Get the synaptic structure of the plastic part of the rows
        """
        return self._synapse_structure

    @property
    def A_plus(self):
        return self._a_plus

    @A_plus.setter
    def A_plus(self, new_value):
        self._a_plus = new_value

    @property
    def A_minus(self):
        return self._a_minus

    @A_minus.setter
    def A_minus(self, new_value):
        self._a_minus = new_value
