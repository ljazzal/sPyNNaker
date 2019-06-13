from spynnaker.pyNN.models.neuron import AbstractPyNNNeuronModelStandard
from spynnaker.pyNN.models.defaults import default_initial_values
from spynnaker.pyNN.models.neuron.neuron_models import (
    NeuronModelLeakyIntegrateAndFireGridCell)
from spynnaker.pyNN.models.neuron.synapse_types import SynapseTypeExponential
from spynnaker.pyNN.models.neuron.input_types import InputTypeCurrent
from spynnaker.pyNN.models.neuron.threshold_types import ThresholdTypeStatic


class GridCell(AbstractPyNNNeuronModelStandard):
    """ Leaky integrate and fire neuron with an exponentially decaying \
        current input
    """

    @default_initial_values({"v", "isyn_exc", "isyn_inh"})
    def __init__(
            self, tau_m=20.0, cm=1.0, v_rest=-65.0, v_reset=-65.0,
            v_thresh=-50.0, tau_syn_E=5.0, tau_syn_I=5.0, tau_refrac=0.1,
            i_offset=0.0, i_vel_drive=0.0, v=-65.0, isyn_exc=0.0, isyn_inh=0.0):
        # pylint: disable=too-many-arguments, too-many-locals
        neuron_model = NeuronModelLeakyIntegrateAndFireGridCell(
            v, v_rest, tau_m, cm, i_offset, i_vel_drive, v_reset, tau_refrac)
        synapse_type = SynapseTypeExponential(
            tau_syn_E, tau_syn_I, isyn_exc, isyn_inh)
        input_type = InputTypeCurrent()
        threshold_type = ThresholdTypeStatic(v_thresh)

        super(GridCell, self).__init__(
            model_name="grid_cell", binary="grid_cell.aplx",
            neuron_model=neuron_model, input_type=input_type,
            synapse_type=synapse_type, threshold_type=threshold_type)
