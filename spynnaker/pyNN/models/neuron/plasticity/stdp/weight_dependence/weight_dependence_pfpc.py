# Copyright (c) 2017-2021 The University of Manchester
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

from data_specification.enums import DataType
from spinn_utilities.overrides import overrides
from .abstract_has_a_plus_a_minus import AbstractHasAPlusAMinus
from .abstract_weight_dependence import AbstractWeightDependence


class WeightDependencePFPC(
        AbstractHasAPlusAMinus, AbstractWeightDependence):
    __slots__ = [
        "__w_max",
        "__w_min",
        "__pot_alpha"
        ]

    # noinspection PyPep8Naming
    def __init__(self, w_min=0.0, w_max=1.0, pot_alpha=0.01):
        super(WeightDependencePFPC, self).__init__()
        self.__w_min = w_min
        self.__w_max = w_max
        self.__pot_alpha = pot_alpha

    @property
    def w_min(self):
        return self.__w_min

    @property
    def w_max(self):
        return self.__w_max

    @property
    def pot_alpha(self):
        return self.__pot_alpha

    @pot_alpha.setter
    def pot_alpha(self, new_value):
        self.__pot_alpha = new_value

    @overrides(AbstractWeightDependence.is_same_as)
    def is_same_as(self, weight_dependence):
        if not isinstance(weight_dependence, WeightDependencePFPC):
            return False
        return (
            (self.__w_min == weight_dependence.w_min) and
            (self.__w_max == weight_dependence.w_max) and
            (self.A_plus == weight_dependence.A_plus) and
            (self.A_minus == weight_dependence.A_minus))

    @property
    def vertex_executable_suffix(self):
        return "pfpc"

    @overrides(AbstractWeightDependence.get_parameters_sdram_usage_in_bytes)
    def get_parameters_sdram_usage_in_bytes(
            self, n_synapse_types, n_weight_terms):
        if n_weight_terms != 1:
            raise NotImplementedError(
                "PFPC weight dependence only supports one term")
        return (4 * 4) * n_synapse_types

    @overrides(AbstractWeightDependence.write_parameters)
    def write_parameters(
            self, spec, global_weight_scale, synapse_weight_scales,
            n_weight_terms):
        # Loop through each synapse type's weight scale
        for _ in synapse_weight_scales:

            print("PFPC, writing values min, max, pot_alpha, A_minus ",
                  self.__w_min, self.__w_max, self.__pot_alpha, self.A_minus)

            # Scale the weights
            spec.write_value(
                data=self.__w_min * global_weight_scale,
                data_type=DataType.S1615)
            spec.write_value(
                data=self.__w_max * global_weight_scale,
                data_type=DataType.S1615)

            # Pre-multiply weight parameters by Wmax?
            # I don't know what's going on here, this is weird
            # If this works the parameter needs renaming on the C side
            # otherwise it's just confusing
            spec.write_value(
                data=self.__pot_alpha * global_weight_scale,
                data_type=DataType.S1615)

            # This parameter is actually currently unused
            # (I'm not convinced that's true...)
            spec.write_value(
                data=self.A_minus * global_weight_scale,
                data_type=DataType.S1615)

    @property
    def weight_maximum(self):
        return self.__w_max

    @overrides(AbstractWeightDependence.get_parameter_names)
    def get_parameter_names(self):
        return ['w_min', 'w_max', 'A_plus', 'A_minus', "pot_alpha"]
