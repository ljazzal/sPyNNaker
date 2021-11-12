# Short-term plasticity based on Tsodyks-Markram model
# Comparison of NEST and SpiNNaker results
import numpy as np
import yaml
import pyNN.nest as sim
import matplotlib.pyplot as plt
from tm_nest import tm_simulation as nest_sim
from tm_spinnaker import tm_simulation as spinn_sim

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

    # 1. Run TM simulation using NEST backend
    v1, spikes_post1, spikes_pre1 = nest_sim(spike_times, cfg)

    # 2. Run TM simulation using SpiNNaker backend
    v2, spikes_post2, spikes_pre2 = spinn_sim(spike_times, cfg)
    tt = np.arange(0, cfg["sim"]["T"], cfg["sim"]["dt"])

    # Plotting
    fig, ax = plt.subplots(ncols=1, nrows=3)

    ax[0].scatter(spikes_pre1, np.ones(len(spikes_pre1)), c="b", label="NEST")
    ax[0].scatter(spikes_pre2, np.ones(len(spikes_pre2)), c="r", label="SpiNN")
    ax[0].set_xlim([0, cfg["sim"]["T"]])
    ax[0].set_title(r'Poisson spike source: $15\,\rm{Hz}$')
    ax[0].legend()

    ax[1].plot(tt, v1, c="b", linewidth=2, label="NEST")
    ax[1].plot(tt, v2, c="r", linewidth=2, label="SpiNN")
    ax[1].set_xlim([0, cfg["sim"]["T"]])
    ax[1].set_ylabel(r'V')
    ax[1].legend()

    ax[2].scatter(spikes_post1, np.ones(len(spikes_post1)), c="b", label="NEST")
    ax[2].scatter(spikes_post2, np.ones(len(spikes_post2)), c="r", label="SpiNN")
    ax[2].set_xlim([0, cfg["sim"]["T"]])
    ax[2].set_xlabel(r'Time $[ms]$')
    ax[2].set_title(r'Output spikes')
    ax[2].legend()

    plt.show()
