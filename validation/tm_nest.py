# Short-term plasticity based on Tsodyks-Markram model
# Backend: NEST
import numpy as np
import yaml
import pyNN.nest as sim
import matplotlib.pyplot as plt

def tm_simulation(params):


    # Simulation setup
    sim.setup(params["sim"]["dt"])
    # Spike times to replicate STP figures from http://dx.doi.org/10.4249/scholarpedia.3153
    spike_times = np.array([20, 90, 150, 195, 230, 720, 790, 850, 895, 930])
    spike_array = {"spike_times": spike_times}
    input_pop = sim.Population(1,
        sim.SpikeSourceArray(**spike_array),
        label="input")

    # LIF configuration
    lif_params = params["lif"]
    lif_pop = sim.Population(lif_params["N"],
        sim.IF_curr_exp(i_offset=lif_params["i_offset"], tau_syn_E=lif_params["tau_syn_E"], tau_syn_I=lif_params["tau_syn_E"]),
        label="lif_pop")

    # Synapse configuration and projection
    stp = sim.TsodyksMarkramSynapse(tau_facil=750, tau_rec=50, U=0.15, weight=2.0)
    stp_connection = sim.Projection(
        input_pop, lif_pop,
        sim.OneToOneConnector(),
        synapse_type=stp,
        receptor_type='excitatory')

    # Recording data
    input_pop.record(['spikes'])
    lif_pop.record(['v', 'spikes'])

    sim.run(params["sim"]["T"])

    # Collecting data
    v_lif_pop = lif_pop.get_data('v').segments[0].filter(name='v')[0][:-1]
    spikes_lif_pop = lif_pop.get_data('spikes').segments[0].spiketrains[0]
    spikes_input = input_pop.get_data('spikes').segments[0].spiketrains[0]

    # End simulation
    sim.end()

    return np.array(v_lif_pop), np.array(spikes_lif_pop), np.array(spikes_input)


if __name__== "__main__":
    
    # Load simulation parameters
    with open("parameters.yml", "r") as fid:
        try:
            cfg = yaml.safe_load(fid)
        except yaml.YAMLError as exc:
            print(exc)

    # Run TM simulation using NEST backend
    v, spikes_post, spikes_pre = tm_simulation(cfg)
    tt = np.arange(0, cfg["sim"]["T"] + cfg["sim"]["dt"], cfg["sim"]["dt"])

    # Plotting
    fig, ax = plt.subplots(ncols=1, nrows=3)

    ax[0].scatter(spikes_pre, np.ones(len(spikes_pre)), c="k", label='Presynaptic spikes')
    ax[0].set_xlim([0, cfg["sim"]["T"]])
    ax[0].legend()

    ax[1].plot(tt, v, linewidth=2, label="Membrane voltage")
    ax[1].set_xlim([0, cfg["sim"]["T"]])
    ax[1].set_ylabel(r'V')
    ax[1].legend()

    ax[2].scatter(spikes_post, np.ones(len(spikes_post)), c="k", label='Postsynaptic spikes')
    ax[2].set_xlim([0, cfg["sim"]["T"]])
    ax[2].set_xlabel(r'Time $[ms]$')
    ax[2].legend()

    plt.show()
