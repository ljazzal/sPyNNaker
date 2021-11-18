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
        "_U_fac",
        "_U_dep",
        "_tau_fac_d",
        "_tau_fac_d_data",
        "_tau_fac_f",
        "_tau_fac_f_data",
        "_tau_dep_d",
        "_tau_dep_d_data",
        "_tau_dep_f",
        "_tau_dep_f_data",
        "_tau_syn",
        "_tau_syn_data",
        "_delta_tau_fac_inv",
        "_delta_tau_dep_inv",
        "_synapse_type",
        "_receptor_type",
        "_synapse_structure"]

    NUM_PARAMETERS = 5

    # noinspection PyPep8Naming
    def __init__(
            self,
            U_fac=0.09,
            U_dep=0.5,
            tau_fac_f=670,
            tau_fac_d=138,
            tau_dep_f=17,
            tau_dep_d=671,
            tau_syn=3,
            synapse_type="facilitating",
            receptor_type="excitatory",
            A_plus=1.0, A_minus=1.0):

        # TODO: Store any parameters
        self._U_fac = U_fac
        self._U_dep = U_dep
        self._tau_fac_f = tau_fac_f
        self._tau_fac_d = tau_fac_d
        self._tau_dep_f = tau_dep_f
        self._tau_dep_d = tau_dep_d
        self._tau_syn = tau_syn
        self._delta_tau_fac_inv = 1 / (tau_syn * tau_fac_d)
        self._delta_tau_dep_inv = 1 / (tau_syn * tau_dep_d)
        self._synapse_type = synapse_type
        self._receptor_type = receptor_type

        # TODO: Update to match the synapse structure in the C code
        self._synapse_structure = SynapseStructureWeightOnly()

        # Are these in the c code?
        self._a_plus = A_plus
        self._a_minus = A_minus

            # provenance data
        ts = machine_time_step_ms()
        self._tau_fac_f_data = get_exp_lut_array(ts, self._tau_fac_f)
        self._tau_fac_d_data = get_exp_lut_array(ts, self._tau_fac_d)
        self._tau_dep_f_data = get_exp_lut_array(ts, self._tau_dep_f)
        self._tau_dep_d_data = get_exp_lut_array(ts, self._tau_dep_d)
        self._tau_syn_data = get_exp_lut_array(ts, self._tau_syn)

    @property
    def U_fac(self):
        return self._U_fac

    @U_fac.setter
    def U_fac(self, U_fac):
        self._U_fac = U_fac

    @property
    def U_dep(self):
        return self._U_dep

    @U_dep.setter
    def U_dep(self, U_dep):
        self._U_dep = U_dep

    @property
    def tau_fac_f(self):
        return self._tau_fac_f

    @tau_fac_f.setter
    def tau_fac_f(self, tau_fac_f):
        self._tau_fac_f = tau_fac_f

    @property
    def tau_fac_d(self):
        return self._tau_fac_d

    @tau_fac_d.setter
    def tau_fac_d(self, tau_fac_d):
        self._tau_fac_d = tau_fac_d

    @property
    def tau_dep_f(self):
        return self._tau_dep_f

    @tau_dep_f.setter
    def tau_dep_f(self, tau_dep_f):
        self._tau_dep_f = tau_dep_f

    @property
    def tau_dep_d(self):
        return self._tau_dep_d

    @tau_dep_d.setter
    def tau_dep_d(self, tau_dep_d):
        self._tau_dep_d = tau_dep_d

    @property
    def tau_syn(self):
        return self._tau_syn

    @tau_syn.setter
    def tau_syn(self, tau_syn):
        self._tau_syn = tau_syn

    @property
    def delta_tau_fac_inv(self):
        return self._delta_tau_fac_inv
    
    @property
    def delta_tau_dep_inv(self):
        return self._delta_tau_dep_inv

    @overrides(AbstractTimingDependence.is_same_as)
    def is_same_as(self, timing_dependence):
        # TODO: Update with the correct class name
        if not isinstance(timing_dependence, TsodyksMarkramTimingDependence):
            return False

        # TODO: update to check parameters are equal
        return (self._U_fac == timing_dependence.U_fac and
                self._U_dep == timing_dependence.U_dep and
                self._tau_fac_f == timing_dependence.tau_fac_f and
                self._tau_fac_d == timing_dependence.tau_fac_d and
                self._tau_dep_f == timing_dependence.tau_dep_f and
                self._tau_dep_d == timing_dependence.tau_dep_d and
                self._tau_syn == timing_dependence.tau_syn and
                self._delta_tau_fac_inv == timing_dependence.delta_tau_fac_inv and
                self._delta_tau_dep_inv == timing_dependence.delta_tau_dep_inv)

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
        return 0

    @overrides(AbstractTimingDependence.get_parameters_sdram_usage_in_bytes)
    def get_parameters_sdram_usage_in_bytes(self):
        # TODO: update to match the number of bytes used by the parameters
        # NOTE: usage for one set of parameters (5) and LUTs (3)
        return self.NUM_PARAMETERS * BYTES_PER_WORD + (BYTES_PER_WORD) * (len(self._tau_fac_f_data) + len(self._tau_fac_d_data) + len(self._tau_syn_data))

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
        fixed_point_tau_syn = float_to_fixed(self._tau_syn)
        if self._receptor_type == "excitatory":
            if self._synapse_type == "facilitating":
                fixed_point_U = float_to_fixed(self._U_fac)
                fixed_point_tau_f = float_to_fixed(self._tau_fac_f)
                fixed_point_tau_d = float_to_fixed(self._tau_fac_d)
                fixed_point_delta_tau_inv = float_to_fixed(self._delta_tau_fac_inv)

                lut_tau_f = self._tau_fac_f_data
                lut_tau_d = self._tau_fac_d_data

            elif self._synapse_type == "depressing":
                fixed_point_U = float_to_fixed(self._U_dep)
                fixed_point_tau_f = float_to_fixed(self._tau_dep_f)
                fixed_point_tau_d = float_to_fixed(self._tau_dep_d)
                fixed_point_delta_tau_inv = float_to_fixed(self._delta_tau_dep_inv)

                lut_tau_f = self._tau_dep_f_data
                lut_tau_d = self._tau_dep_d_data
        else:
            if self._synapse_type == "facilitating":
                fixed_point_U = float_to_fixed(self._U_fac)
                fixed_point_tau_f = float_to_fixed(self._tau_fac_f)
                fixed_point_tau_d = float_to_fixed(self._tau_fac_d)
                fixed_point_delta_tau_inv = float_to_fixed(self._delta_tau_fac_inv)

                lut_tau_f = self._tau_fac_f_data
                lut_tau_d = self._tau_fac_d_data

            elif self._synapse_type == "depressing":
                fixed_point_U = float_to_fixed(self._U_dep)
                fixed_point_tau_f = float_to_fixed(self._tau_dep_f)
                fixed_point_tau_d = float_to_fixed(self._tau_dep_d)
                fixed_point_delta_tau_inv = float_to_fixed(self._delta_tau_dep_inv)

                lut_tau_f = self._tau_dep_f_data
                lut_tau_d = self._tau_dep_d_data

        # Don't want to multiply Pxy by 0 later
        if fixed_point_delta_tau_inv == 0:
            fixed_point_delta_tau_inv = 1

        # Write parameters
        spec.write_value(data=fixed_point_U, data_type=DataType.INT32)
        spec.write_value(data=fixed_point_tau_f, data_type=DataType.INT32)
        spec.write_value(data=fixed_point_tau_d, data_type=DataType.INT32)
        spec.write_value(data=fixed_point_tau_syn, data_type=DataType.INT32)
        spec.write_value(data=fixed_point_delta_tau_inv, data_type=DataType.INT32)

        # Write lookup tables
        spec.write_array(self._tau_syn_data)
        spec.write_array(lut_tau_f)
        spec.write_array(lut_tau_d)

    @overrides(AbstractTimingDependence.get_parameter_names)
    def get_parameter_names(self):
        return ['U', 'tau_f', 'tau_d', 'tau_syn']

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
