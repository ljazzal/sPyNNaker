# Short-term plasticity based on Tsodyks-Markram model
# Backend: SpiNNaker
import numpy as np
import yaml
import spynnaker8 as sim
import matplotlib.pyplot as plt

# Tsodyks-Markram synapse model for SpiNNaker
from python_models8.neuron.plasticity.stdp.timing_dependence\
    .tm_timing_dependence import (
        TsodyksMarkramTimingDependence)
from python_models8.neuron.plasticity.stdp.weight_dependence\
    .tm_weight_dependence import (
        TsodyksMarkramWeightDependence)


def tm_simulation(input_spikes, params, syn="fac", type="exc"):


    # Simulation setup
    sim.setup(params["sim"]["dt"])
    # Spike times to replicate STP figures from http://dx.doi.org/10.4249/scholarpedia.3153
    # spike_times = np.array([20, 90, 150, 195, 230, 720, 790, 850, 895, 930])
    # spike_times = np.array([16.,  79., 213., 225., 265., 276., 340., 366., 422., 636., 760., 886., 894., 936., 941.])
    spike_array = {"spike_times": input_spikes}
    poisson_source = sim.SpikeSourcePoisson(rate=50)
    input_pop = sim.Population(1,
        sim.SpikeSourceArray(**spike_array),
        # poisson_source,
        label="input")
    input_pop2 = sim.Population(1,
        poisson_source,
        label="input2")

    # LIF configuration
    lif_params = params["lif"]
    lif_pop = sim.Population(lif_params["N"],
        sim.IF_curr_exp(i_offset=lif_params["i_offset"], tau_syn_E=lif_params["tau_syn_E"], tau_syn_I=lif_params["tau_syn_E"]),
        label="lif_pop")

    # Synapse configuration and projection
    # A custom STP mechanism is used on SpiNNaker
    # for syn_type in "facilitating", "depressing", "pseudo":
    # syn_params = params["synapses"]["fac"]["exc"]
    # exc_synapse_types = {}

    timing_dep_fac = TsodyksMarkramTimingDependence(synapse_type="facilitating", receptor_type="excitatory")
    weight_dep_fac = TsodyksMarkramWeightDependence(w_min=0.0, w_max=10.0)
    timing_dep_dep = TsodyksMarkramTimingDependence(synapse_type="depressing", receptor_type="excitatory")
    weight_dep_dep = TsodyksMarkramWeightDependence(w_min=0.0, w_max=10.0)

    # inh_synapse_types = {}
    
    stp_f = sim.STDPMechanism(
        timing_dependence=timing_dep_fac,
        weight_dependence=weight_dep_fac,
        weight=-2.0)
    # stp = sim.StaticSynapse(weight=0.5)
    print(stp_f)
    stp_d = sim.STDPMechanism(
        timing_dependence=timing_dep_dep,
        weight_dependence=weight_dep_dep,
        weight=1.0)
    # stp2 = sim.StaticSynapse(weight=0.1)
    print(stp_d)

    stp_exc_fac_connection = sim.Projection(
        input_pop, lif_pop,
        sim.OneToOneConnector(),
        synapse_type=stp_f,
        receptor_type='inhibitory')
    stp_exc_dep_connection = sim.Projection(
        input_pop2, lif_pop,
        sim.OneToOneConnector(),
        synapse_type=stp_d,
        receptor_type='excitatory')
    # stp_exc_fac_connection = sim.Projection(
    #     input_pop, lif_pop,
    #     sim.OneToOneConnector(),
    #     synapse_type=stp_f,
    #     receptor_type='inhibitory')
    # stp_exc_dep_connection = sim.Projection(
    #     input_pop2, lif_pop,
    #     sim.OneToOneConnector(),
    #     synapse_type=stp_d,
    #     receptor_type='inhibitory')

    # Recording data
    input_pop.record(['spikes'])
    input_pop2.record(['spikes'])
    lif_pop.record(['v', 'spikes'])

    sim.run(params["sim"]["T"])

    # Collecting data
    v_lif_pop = lif_pop.get_data('v').segments[0].filter(name='v')[0]
    spikes_lif_pop = lif_pop.get_data('spikes').segments[0].spiketrains[0]
    spikes_input = input_pop.get_data('spikes').segments[0].spiketrains[0]
    spikes_input2 = input_pop2.get_data('spikes').segments[0].spiketrains[0]

    # End simulation
    sim.end()

    return np.array(v_lif_pop), np.array(spikes_lif_pop), np.array(spikes_input), np.array(spikes_input2)


if __name__== "__main__":
    
    # Load simulation parameters
    with open("parameters.yml", "r") as fid:
        try:
            cfg = yaml.safe_load(fid)
        except yaml.YAMLError as exc:
            print(exc)

    # Input spikes: Poisson spike source @ 50 Hz
    spike_times = np.array([ 25., 129., 133., 138., 157., 167., 177., 180., 187., 194., 203.,
       235., 237., 264., 282., 315., 378., 385., 387., 387., 421., 477.,
       481., 501., 506., 518., 545., 579., 593., 622., 624., 630., 643.,
       664., 671., 694., 702., 704., 707., 723., 730., 740., 815., 816.,
       820., 874., 881., 886., 891., 896., 918., 933., 943., 969., 978.,
       983.])

    # Run TM simulation using NEST backend
    v, spikes_post, spikes_pre1, spikes_pre2 = tm_simulation(spike_times, cfg)
    tt = np.arange(0, cfg["sim"]["T"], cfg["sim"]["dt"])

    # Plotting
    fig, ax = plt.subplots(ncols=1, nrows=4)

    ax[0].scatter(spikes_pre1, np.ones(len(spikes_pre1)), c="k", label='Presynaptic spikes 1')
    ax[0].set_xlim([0, cfg["sim"]["T"]])
    ax[0].legend()

    ax[1].scatter(spikes_pre2, np.ones(len(spikes_pre2)), c="k", label='Presynaptic spikes 2')
    ax[1].set_xlim([0, cfg["sim"]["T"]])
    ax[1].legend()

    ax[2].plot(tt, v, linewidth=2, label="Membrane voltage")
    ax[2].set_xlim([0, cfg["sim"]["T"]])
    ax[2].set_ylabel(r'V')
    ax[2].legend()

    ax[3].scatter(spikes_post, np.ones(len(spikes_post)), c="k", label='Postsynaptic spikes')
    ax[3].set_xlim([0, cfg["sim"]["T"]])
    ax[3].set_xlabel(r'Time $[ms]$')
    ax[3].legend()

    plt.show()