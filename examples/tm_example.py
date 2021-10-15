# import spynnaker8 and plotting stuff
import numpy as np
import spynnaker8 as p
from pyNN.utility.plotting import Figure, Panel
import matplotlib.pyplot as plt
import datetime
import os

# import models
from python_models8.neuron.plasticity.stdp.timing_dependence\
    .tm_timing_dependence import (
        TsodyksMarkramTimingDependence)
from python_models8.neuron.plasticity.stdp.weight_dependence\
    .tm_weight_dependence import (
        TsodyksMarkramWeightDependence)


# Set the run time of the execution
run_time = 300

# Set the time step of the simulation in milliseconds
time_step = 1.0

# Set the number of neurons to simulate
n_neurons = 1

# Set the i_offset current
i_offset = 0.0

# Set the weight of input spikes
weight = 1.0

# Set the times at which to input a spike
# Spike times to replicate STP figures from http://dx.doi.org/10.4249/scholarpedia.3153
spike_times = np.array([20, 90, 150, 195, 230])

p.setup(time_step)

spikeArray = {"spike_times": spike_times}
input_pop = p.Population(
    n_neurons, p.SpikeSourceArray(**spikeArray), label="input")

# A standard IF_curr_exp is used
tm_stp_pop = p.Population(n_neurons, p.IF_curr_exp(i_offset=i_offset, tau_syn_E=20.0, tau_syn_I=20.0), label="my_model_pop")

# A custom STP mechanism is used
stp = p.STDPMechanism(
    timing_dependence=TsodyksMarkramTimingDependence(
        tau_f=50.0, tau_d=750.0),       # STD
        # tau_f=750.0, tau_d=50.0),     # STF
    weight_dependence=TsodyksMarkramWeightDependence(A=1.0, U=0.45,
        w_min=0.0, w_max=10.0), weight=weight)

stp_connection = p.Projection(
    input_pop, tm_stp_pop,
    p.OneToOneConnector(),
    synapse_type=stp, receptor_type='excitatory')

input_pop.record(['spikes'])
tm_stp_pop.record(['v', 'gsyn_exc', 'spikes'])

p.run(run_time)


# Collect data
v_tm_stp_pop = tm_stp_pop.get_data('v')
exc_input_tm_stp_pop = tm_stp_pop.get_data('gsyn_exc')
input_spikes = input_pop.get_data('spikes').segments[0].spiketrains

Figure(
    Panel(input_spikes,
          ylabel="Input spikes", yticks=True, xticks=True, xlim=(0, run_time)),
    Panel(v_tm_stp_pop.segments[0].filter(name='v')[0],
          ylabel="Membrane potential (mV)",
          data_labels=[tm_stp_pop.label],
          yticks=True, xlim=(0, run_time)),
    Panel(exc_input_tm_stp_pop.segments[0].filter(name='gsyn_exc')[0],
          ylabel="Excitatory input",
          yticks=True, xlim=(0, run_time)),
    title="Simple my model examples",
    annotations="Simulated with {}".format(p.name())
)#.save('tm_std_synapse.png')

# Extracting data from logs
reports = sorted(os.listdir("./reports"), key=lambda x: datetime.datetime.strptime(x, '%Y-%m-%d-%H-%M-%S-%f'))
print(reports)

report = reports[-1]
filepath = os.path.join("./reports", report, "run_1", "provenance_data", "app_provenance_data", "iobuf_for_chip_4_4_processor_id_2.txt")

with open(filepath, 'r') as fid:
    lines = fid.readlines()

suffix_weight = "[INFO] (tm_weight_impl.h:"
suffix_timing = "[INFO] (tm_timing_impl.h:"
u = []
x = []
w = []
for l in lines:
    if l.startswith(suffix_weight):
        parsed = l.split(" ")
        if parsed[3][0] == "u":
            u.append(int(parsed[3][2:-1]))
        elif parsed[3][0] == "x":
            x.append(int(parsed[3][2:-1]))
        else:
            w.append(int(parsed[3][2:-1]))

# Plotting
fig, ax = plt.subplots(ncols=1, nrows=4)
tt = np.arange(0, run_time)
spikes = np.array(input_spikes[0])
spks = np.repeat(spikes, 2)
v = np.array(v_tm_stp_pop.segments[0].filter(name='v')[0])
I_exc = np.array(exc_input_tm_stp_pop.segments[0].filter(name='gsyn_exc')[0])

ax[0].plot(tt, v, linewidth=2)
ax[0].set_xlim([0, run_time])
ax[0].set_ylabel(r'v')
ax[1].plot(spks, u, linewidth=2, label='u', c='k')
ax[1].plot(spks, x, linewidth=2, label='x', c='cornflowerblue')
ax[1].scatter(spikes, w, c='c', marker="o", label='w', alpha=0.5)
ax[1].set_xlim([0, run_time])
ax[1].legend()
ax[2].plot(tt, I_exc, linewidth=2, c='r')
ax[2].set_xlim([0, run_time])
ax[2].set_ylabel(r'I')
ax[3].scatter(spikes, np.ones(len(spikes)), c='cornflowerblue')
ax[3].set_xlim([0, run_time])
ax[3].set_xlabel(r'Time $[ms]$')

plt.show()
p.end()
