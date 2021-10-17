# Simulation of the effects of DBS on basal ganglia (BG) nuclei
# based on the Tsodyks-Markram (TM) model of short-term plasticity (STP)


from os import name
import numpy as np
import yaml
import spynnaker8 as sim
from models.lif_neuron import LIFPopulation
from utils.dbs_utils import DBSPopulation

# Fix random seed to get reproducible results
np.random.seed(30)


# TODO: plotting functions


if __name__ == "__main__":
    # TODO: parse configs from command line args
    nucleus = "STN"
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
    noisy_input = sim.NoisyCurrentSource(mean=0, stdev=cfg["nucleus"][nucleus]["noise_std"])
    # presynaptic_pop = DBSPopulation()
    lif = LIFPopulation(cfg["nucleus"][nucleus], cfg["synapses"])
    # stp_connection = sim.Projection(
    #     presynaptic.pop, lif.pop, sim.OneToOneConnector(),
    #     synapse_type=lif.synapese[""]
    # )


    # Connecting populations

    # Placing probes

    sim.run(cfg["sim"]["T"])

    # Extracting measurements


    # Plotting results