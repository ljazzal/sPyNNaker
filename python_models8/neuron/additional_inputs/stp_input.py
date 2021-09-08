import numpy
from spinn_utilities.overrides import overrides
from data_specification.enums import DataType
from spynnaker.pyNN.models.neuron.additional_inputs import (
    AbstractAdditionalInput)

# TODO: create constants to match the parameter names
U = "u"
X = "x"
I_STP = "i_stp"

A = "A"
USE = "U"
TAU_F = "tau_f"
TAU_D = "tau_d"
TAU_SYN = "tau_syn"

# TODO: create units for each parameter
UNITS = {
    U: "",
    X: "",
    I_STP: "nA",
    A: "",
    USE: "",
    TAU_F: "ms",
    TAU_D: "ms",
    TAU_SYN: "ms"
}


class StpInput(AbstractAdditionalInput):
    __slots__ = [
        "__u",
        "__x",
        "__i_stp",
        "__A",
        "__U",
        "__tau_f",
        "__tau_d",
        "__tau_syn"
    ]

    def __init__(
            self,

            # TODO: update the parameters
            u, x, i_stp, A, U, tau_f, tau_d, tau_syn
            ):

        # TODO: Update the data types - this must match the struct exactly
        super().__init__([
            DataType.S1615,  # resources ready, u
            DataType.S1615,  # resources remaining, x
            DataType.S1615,  # i_stp
            DataType.S1615,  # weight, A
            DataType.S1615,  # usage, U
            DataType.S1615,  # exp(-ts / tau_f)
            DataType.S1615,  # exp(-ts / tau_d)
            DataType.S1615   # exp(-ts / tau_syn)
        ])

        # TODO: store the parameters
        self.__u  = u
        self.__x = x
        self.__i_stp = i_stp
        self.__A = A
        self.__U = U
        self.__tau_f = tau_f
        self.__tau_d = tau_d
        self.__tau_syn = tau_syn

    @overrides(AbstractAdditionalInput.get_n_cpu_cycles)
    def get_n_cpu_cycles(self, n_neurons):
        # TODO: Calculate (or guess) the CPU cycles
        return 10 * n_neurons

    @overrides(AbstractAdditionalInput.add_parameters)
    def add_parameters(self, parameters):
        # TODO: Add initial values of the parameters that the user can change
        parameters[A] = self.__A
        parameters[USE] = self.__U
        parameters[TAU_F] = self.__tau_f
        parameters[TAU_D] = self.__tau_d
        parameters[TAU_SYN] = self.__tau_syn

    @overrides(AbstractAdditionalInput.add_state_variables)
    def add_state_variables(self, state_variables):
        # TODO: Add initial values of the state variables that the user can
        # change
        state_variables[U] = self.__u
        state_variables[X] = self.__x
        state_variables[I_STP] = self.__i_stp

    @overrides(AbstractAdditionalInput.get_values)
    def get_values(self, parameters, state_variables, vertex_slice, ts):
        # TODO: Return, in order of the struct, the values from the parameters,
        # state variables, or other
        return [state_variables[U], state_variables[X], state_variables[I_STP],
                parameters[A], parameters[USE],
                parameters[TAU_F].apply_operation(
                    operation=lambda x: 0.0 if x == 0.0 else numpy.exp(float(-ts) / (1000.0 * x))),
                parameters[TAU_D].apply_operation(
                    operation=lambda x: 0.0 if x == 0.0 else numpy.exp(float(-ts) / (1000.0 * x))),
                parameters[TAU_SYN].apply_operation(
                    operation=lambda x: 0.0 if x == 0.0 else numpy.exp(float(-ts) / (1000.0 * x)))]

    @overrides(AbstractAdditionalInput.update_values)
    def update_values(self, values, parameters, state_variables):
        # TODO: From the list of values given in order of the struct, update
        # the parameters and state variables
        (u, x, i_stp, _A, _U, _exp_tau_f, _exp_tau_d, _exp_tau_syn) = values

        # NOTE: If you know that the value doesn't change, you don't have to
        # assign it (hint: often only state variables are likely to change)!
        state_variables[U] = u
        state_variables[X] = x
        state_variables[I_STP] = i_stp

    @overrides(AbstractAdditionalInput.has_variable)
    def has_variable(self, variable):
        # This works from the UNITS dict, so no changes are required
        return variable in UNITS

    @overrides(AbstractAdditionalInput.get_units)
    def get_units(self, variable):
        # This works from the UNITS dict, so no changes are required
        return UNITS[variable]

    @property
    def u(self):
        return self.__u
    
    @property
    def x(self):
        return self.__x

    @property
    def i_stp(self):
        return self.__i_stp

    @property
    def A(self):
        return self.__A

    @property
    def U(self):
        return self.__U

    @property
    def tau_f(self):
        return self.__tau_f

    @property
    def tau_d(self):
        return self.__tau_d
    
    @property
    def tau_syn(self):
        return self.__tau_syn
