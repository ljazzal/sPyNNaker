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

from spynnaker.pyNN.models.neuron import AbstractPyNNNeuronModelStandard
from spynnaker.pyNN.models.defaults import default_initial_values
from spynnaker.pyNN.models.neuron.neuron_models import (
    NeuronModelLeakyIntegrateAndFire)
from spynnaker.pyNN.models.neuron.synapse_types import SynapseTypeExponential
from spynnaker.pyNN.models.neuron.input_types import InputTypeCurrent
from spynnaker.pyNN.models.neuron.threshold_types import ThresholdTypeStatic
from python_models8.neuron.input_types.stp_input_current import StpInputCurrent


class IFCurrExpStp(AbstractPyNNNeuronModelStandard):
    """ Model from Liu, Y. H., & Wang, X. J. (2001). Spike-frequency\
        adaptation of a generalized leaky integrate-and-fire model neuron. \
        *Journal of Computational Neuroscience*, 10(1), 25-45. \
        `doi:10.1023/A:1008916026143 \
        <https://doi.org/10.1023/A:1008916026143>`
    """

    @default_initial_values({"v", "isyn_exc", "isyn_inh", "i_stp", "u", "x"})
    def __init__(
            self, tau_m=10.0, cm=1.0, v_rest=-70.0, v_reset=-70.0,
            v_thresh=-40.0, tau_syn_E=10.0, tau_syn_I=10.0, tau_refrac=0.1,
            i_offset=0.0, v=-70.0, isyn_exc=0.0, isyn_inh=0.0,
            u=0.0, x=1.0, i_stp=0.0, A=0.1, U=0.5, tau_f=50, tau_d=750, tau_syn=10.0):
        # pylint: disable=too-many-arguments, too-many-locals
        neuron_model = NeuronModelLeakyIntegrateAndFire(
            v, v_rest, tau_m, cm, i_offset, v_reset, tau_refrac)
        synapse_type = SynapseTypeExponential(
            tau_syn_E, tau_syn_I, isyn_exc, isyn_inh)
        input_type = StpInputCurrent(u, x, i_stp, A, U, tau_f, tau_d, tau_syn)
        threshold_type = ThresholdTypeStatic(v_thresh)

        super().__init__(
            model_name="IF_curr_exp_stp",
            binary="IF_curr_exp_stp.aplx",
            neuron_model=neuron_model, input_type=input_type,
            synapse_type=synapse_type, threshold_type=threshold_type)