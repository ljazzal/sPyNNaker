# Simulation of the effects of DBS on basal ganglia (BG) nuclei
# based on the Tsodyks-Markram (TM) model of short-term plasticity (STP)


from os import name
import numpy as np
import yaml
import argparse
import spynnaker8 as sim
from pyNN.utility.plotting import Figure, Panel
import matplotlib.pyplot as plt
from models.lif_neuron import LIFPopulation
from utils.dbs_utils import DBSPopulation

# Fix random seed to get reproducible results
np.random.seed(30)


# TODO: plotting functions
def plot_data():
    pass

def parse_arguments():
    # Parse command line arguments
    parser = argparse.ArgumentParser()
    parser.add_argument("--nucleus", type=str, choices=["stn", "vim", "snr"], required=True, help="Nucleus to stimulate during simulation")
    args, usr_args = parser.parse_known_args()
    return args, usr_args


if __name__ == "__main__":
    # Parse user arguments
    args, usr_args = parse_arguments()

    # Load simulation parameters
    with open("models/lif_parameters.yml", "r") as fid:
        try:
            cfg = yaml.safe_load(fid)
        except yaml.YAMLError as exc:
            print(exc)

    # Simulation setup
    sim.setup(cfg["sim"]["dt"])

    # Building populations
    # TODO: replace with OUP
    noisy_input = sim.NoisyCurrentSource(mean=0, stdev=cfg["nucleus"][args.nucleus]["noise_std"])
    # presynaptic_pop = DBSPopulation()
    lif = LIFPopulation(cfg["nucleus"][args.nucleus], cfg["synapses"], args.nucleus)
    lif_pop = sim.Population(2, sim.IF_curr_exp(i_offset=0, tau_syn_E=20.0, tau_syn_I=20.0), label="my_model_pop")
    spike_times = np.array([20, 90, 150, 195, 230])
    spike_times2 = np.array([50, 100, 150, 200, 250])
    spikeArray = {"spike_times": spike_times}
    spikeArray2 = {"spike_times": spike_times2}
    input_pop = sim.Population(1, sim.SpikeSourceArray(**spikeArray), label="input")
    input_pop2 = sim.Population(1, sim.SpikeSourceArray(**spikeArray2), label="input")

    # Configuring synapses (i.e. connections)
    # NOTE: "Synapse dynamics must match exactly when using multiple edges to the same population" --> ISSUE
    stp_fac_connection = sim.Projection(
        input_pop, lif_pop,
        sim.OneToOneConnector(),
        synapse_type=lif.exc_synapses["fac"], receptor_type="excitatory"
    )

    stp_fac_connection2 = sim.Projection(
        input_pop2, lif_pop,
        sim.OneToOneConnector(),
        synapse_type=lif.exc_synapses["dep"], receptor_type="excitatory"
    )

    # Placing probes
    input_pop.record(["spikes"])
    input_pop2.record(["spikes"])
    lif_pop.record(["v", "gsyn_exc", "spikes"])

    sim.run(cfg["sim"]["T"])

    # Extracting measurements
    v_lif = lif_pop.get_data("v")
    i_exc_lif = lif_pop.get_data("gsyn_exc")
    pre_spikes = input_pop.get_data("spikes").segments[0].spiketrains
    pre_spikes2 = input_pop2.get_data("spikes").segments[0].spiketrains

    # Plotting results
    Figure(
        Panel(pre_spikes,
            ylabel="Input spikes", yticks=True, xticks=True, xlim=(0, cfg["sim"]["T"])),
        Panel(pre_spikes2,
            ylabel="Input spikes", yticks=True, xticks=True, xlim=(0, cfg["sim"]["T"])),
        Panel(v_lif.segments[0].filter(name='v')[0],
            ylabel="Membrane potential (mV)",
            data_labels=[lif.population_label],
            yticks=True, xlim=(0, cfg["sim"]["T"])),
        Panel(i_exc_lif.segments[0].filter(name='gsyn_exc')[0],
            ylabel="Excitatory input",
            yticks=True, xlim=(0, cfg["sim"]["T"])),
    title="Simple my model examples",
    annotations="Simulated with {}".format(sim.name())
)#.save('tm_std_synapse.png')

plt.show()
sim.end()