import numpy
from spinn_utilities.overrides import overrides
from data_specification.enums import DataType
from pacman.executor.injection_decorator import inject_items
from .abstract_neuron_model import AbstractNeuronModel

V = "v"
V_REST = "v_rest"
TAU_M = "tau_m"
CM = "cm"
I_OFFSET = "i_offset"
I_VEL_DRIVE = "i_vel_drive"
V_RESET = "v_reset"
TAU_REFRAC = "tau_refrac"
DIR_PREF = "dir_pref"
COUNT_REFRAC = "count_refrac"

UNITS = {
    V: 'mV',
    V_REST: 'mV',
    TAU_M: 'ms',
    CM: 'nF',
    I_OFFSET: 'nA',
    I_VEL_DRIVE: 'nA',
    V_RESET: 'mV',
    TAU_REFRAC: 'ms',
    DIR_PREF: 'radians',
}


class NeuronModelLeakyIntegrateAndFireGridCell(AbstractNeuronModel):
    __slots__ = [
        "_v_init",
        "_v_rest",
        "_tau_m",
        "_cm",
        "_i_offset",
        "_i_vel_drive",
        "_v_reset",
        "_tau_refrac",
        "_dir_pref"]

    def __init__(
            self, v_init, v_rest, tau_m, cm, i_offset, i_vel_drive, v_reset, tau_refrac, dir_pref):
        super(NeuronModelLeakyIntegrateAndFireGridCell, self).__init__(
            [DataType.S1615,   # v
             DataType.S1615,   # v_rest
             DataType.S1615,   # r_membrane (= tau_m / cm)
             DataType.S1615,   # exp_tc (= e^(-ts / tau_m))
             DataType.S1615,   # i_offset
             DataType.S1615,   # i_vel_drive
             DataType.INT32,   # count_refrac
             DataType.S1615,   # v_reset
             DataType.INT32,   # tau_refrac
             DataType.S1615])   # dir_pref

        if v_init is None:
            v_init = v_rest
        self._v_init = v_init
        self._v_rest = v_rest
        self._tau_m = tau_m
        self._cm = cm
        self._i_offset = i_offset
        self._i_vel_drive = i_vel_drive
        self._v_reset = v_reset
        self._tau_refrac = tau_refrac
        self._dir_pref = dir_pref

    @overrides(AbstractNeuronModel.get_n_cpu_cycles)
    def get_n_cpu_cycles(self, n_neurons):
        # A bit of a guess
        return 100 * n_neurons

    @overrides(AbstractNeuronModel.add_parameters)
    def add_parameters(self, parameters):
        parameters[V_REST] = self._v_rest
        parameters[TAU_M] = self._tau_m
        parameters[CM] = self._cm
        parameters[I_OFFSET] = self._i_offset
        parameters[V_RESET] = self._v_reset
        parameters[TAU_REFRAC] = self._tau_refrac
        parameters[I_VEL_DRIVE] = self._i_vel_drive
        parameters[DIR_PREF] = self._dir_pref

    @overrides(AbstractNeuronModel.add_state_variables)
    def add_state_variables(self, state_variables):
        state_variables[V] = self._v_init
        state_variables[COUNT_REFRAC] = 0

    @overrides(AbstractNeuronModel.get_units)
    def get_units(self, variable):
        return UNITS[variable]

    @overrides(AbstractNeuronModel.has_variable)
    def has_variable(self, variable):
        return variable in UNITS

    @inject_items({"ts": "MachineTimeStep"})
    @overrides(AbstractNeuronModel.get_values, additional_arguments={'ts'})
    def get_values(self, parameters, state_variables, vertex_slice, ts):

        # Add the rest of the data
        return [state_variables[V], parameters[V_REST],
                parameters[TAU_M] / parameters[CM],
                parameters[TAU_M].apply_operation(
                    operation=lambda x: numpy.exp(float(-ts) / (1000.0 * x))),
                parameters[I_OFFSET],
                parameters[I_VEL_DRIVE],
                state_variables[COUNT_REFRAC],
                parameters[V_RESET],
                parameters[TAU_REFRAC].apply_operation(
                    operation=lambda x: int(numpy.ceil(x / (ts / 1000.0)))),
                parameters[DIR_PREF]]

    @overrides(AbstractNeuronModel.update_values)
    def update_values(self, values, parameters, state_variables):

        # Read the data
        (v, _v_rest, _r_membrane, _exp_tc, _i_offset, _i_vel_drive, count_refrac,
         _v_reset, _tau_refrac, _dir_pref) = values

        # Copy the changed data only
        state_variables[V] = v
        state_variables[COUNT_REFRAC] = count_refrac

    @property
    def v_init(self):
        return self._v

    @v_init.setter
    def v_init(self, v_init):
        self._v = v_init

    @property
    def v_rest(self):
        return self._v_rest

    @v_rest.setter
    def v_rest(self, v_rest):
        self._v_rest = v_rest

    @property
    def tau_m(self):
        return self._tau_m

    @tau_m.setter
    def tau_m(self, tau_m):
        self._tau_m = tau_m

    @property
    def cm(self):
        return self._cm

    @cm.setter
    def cm(self, cm):
        self._cm = cm

    @property
    def i_offset(self):
        return self._i_offset

    @i_offset.setter
    def i_offset(self, i_offset):
        self._i_offset = i_offset

    @property
    def i_vel(self):
        return self._i_vel_drive

    @i_offset.setter
    def i_vel(self, i_vel_drive):
        self._i_vel_drive = i_vel_drive

    @property
    def v_reset(self):
        return self._v_reset

    @v_reset.setter
    def v_reset(self, v_reset):
        self._v_reset = v_reset

    @property
    def tau_refrac(self):
        return self._tau_refrac

    @tau_refrac.setter
    def tau_refrac(self, tau_refrac):
        self._tau_refrac = tau_refrac

    @property
    def dir_pref(self):
        return self._dir_pref

    @dir_pref.setter
    def dir_pref(self, dir_pref):
        self._dir_pref = dir_pref
