# Leaky integrate-and-fire (LIF) neurons for DBS simulation
# lja, October 2021
import numpy as np
import spynnaker8 as sim

# Import STP models
from python_models8.neuron.plasticity.stdp.timing_dependence.tm_timing_dependence import TsodyksMarkramTimingDependence
from python_models8.neuron.plasticity.stdp.weight_dependence.tm_weight_dependence import TsodyksMarkramWeightDependence


class LIFPopulation:
    """
    Generic LIF population class to be parameterized according to target nucleus:
        - STN: subthalamic nucleus
        - SNr: substantia nigra pars reticulata
        - Vim: ventral intermediate nucleus
    """

    def __init__(self, neuron_params, synapse_params, nucleus):
        
        self.neuron_params = neuron_params
        self.synapse_params = synapse_params
        self.population_label = nucleus
        self.exc_synapses = dict.fromkeys(synapse_params)
        self.inh_synapses = dict.fromkeys(synapse_params)
        
        self.initialize(self.neuron_params, self.synapse_params)
    
    def initialize(self, neuron_params, synapse_params):
        
        n_params = {p: neuron_params[p] for p in neuron_params.keys() & sim.IF_curr_exp().default_parameters}
        self.neuron = sim.IF_curr_exp(**n_params)
        self.pop = sim.Population(neuron_params["N"], self.neuron, label=self.population_label)

        # TODO: add support for static synapses
        default_weight_params = TsodyksMarkramWeightDependence().get_parameter_names()
        default_timing_params = TsodyksMarkramTimingDependence().get_parameter_names()
        for syn in self.exc_synapses.keys():
            exc_stp_w_params = {p: synapse_params[syn]["exc"][p] for p in synapse_params[syn]["exc"].keys() & default_weight_params}
            exc_stp_t_params = {p: synapse_params[syn]["exc"][p] for p in synapse_params[syn]["exc"].keys() & default_timing_params}
            inh_stp_w_params = {p: synapse_params[syn]["inh"][p] for p in synapse_params[syn]["inh"].keys() & default_weight_params}
            inh_stp_t_params = {p: synapse_params[syn]["inh"][p] for p in synapse_params[syn]["inh"].keys() & default_timing_params}
            self.exc_synapses[syn] = sim.STDPMechanism(
                timing_dependence=TsodyksMarkramTimingDependence(
                    **exc_stp_t_params
                ),
                weight_dependence=TsodyksMarkramWeightDependence(
                    **exc_stp_w_params
                ),
                # weight=weight
            )
            self.inh_synapses[syn] = sim.STDPMechanism(
                timing_dependence=TsodyksMarkramTimingDependence(
                    **inh_stp_t_params
                ),
                weight_dependence=TsodyksMarkramWeightDependence(
                    **inh_stp_w_params
                ),
                # weight=weight
            )