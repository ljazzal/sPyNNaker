# import spynnaker8 and plotting stuff
from python_models8.neuron import input_types
from python_models8.neuron.plasticity.stdp import timing_dependence
import numpy as np
import spynnaker8 as p
from pyNN.utility.plotting import Figure, Panel
import matplotlib.pyplot as plt
import datetime
import os

# import models
from python_models8.neuron.plasticity.stdp.timing_dependence\
    .my_timing_dependence import (
        MyTimingDependence)
from python_models8.neuron.plasticity.stdp.timing_dependence\
    .tm_timing_dependence import (
        TsodyksMarkramTimingDependence)
from python_models8.neuron.plasticity.stdp.weight_dependence\
    .tm_weight_dependence import (
        TsodyksMarkramWeightDependence)
from python_models8.neuron.plasticity.stdp.weight_dependence\
    .my_weight_dependence import (
        MyWeightDependence)


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
# spike_times = np.array([10., 80., 140, 190, 230., 260., 280., 290., 300., 310, 320., 480, 490])#], 340, 360, 370, 710, 720, 730, 740, 780])
spike_times = np.array([20, 90, 150, 195, 230])

p.setup(time_step)

spikeArray = {"spike_times": spike_times}
input_pop = p.Population(
    n_neurons, p.SpikeSourceArray(**spikeArray), label="input")

my_model_stdp_pop = p.Population(
    n_neurons, p.IF_curr_exp(i_offset=i_offset, tau_syn_E=20.0, tau_syn_I=20.0), label="my_model_pop")
stdp = p.STDPMechanism(
    timing_dependence=TsodyksMarkramTimingDependence(
        tau_f=50.0, tau_d=750.0),
        # tau_f=800.0, tau_d=50.0),
    weight_dependence=TsodyksMarkramWeightDependence(A=1.0, U=0.5,
        w_min=0.0, w_max=10.0), weight=weight)

stdp_connection = p.Projection(
    input_pop, my_model_stdp_pop,
    p.OneToOneConnector(),
    synapse_type=stdp, receptor_type='excitatory')

input_pop.record(['spikes'])
my_model_stdp_pop.record(['v', 'gsyn_exc', 'spikes'])

p.run(run_time)

# print(stdp_connection.get('weight', 'list'))

# get v for each example
# v_my_model_pop = my_model_pop.get_data('v')
v_my_model_my_input_type_pop = my_model_stdp_pop.get_data('v')
exc_input = my_model_stdp_pop.get_data('gsyn_exc')
input_spikes = input_pop.get_data('spikes').segments[0].spiketrains
# v_my_model_my_synapse_type_pop = my_model_my_synapse_type_pop.get_data('v')
# v_my_model_my_additional_input_pop = my_model_my_additional_input_pop.get_data(
#     'v')
# v_my_model_my_threshold_pop = my_model_my_threshold_pop.get_data('v')
# v_my_if_curr_exp_semd_pop = my_if_curr_exp_semd_pop.get_data('v')
# v_my_full_neuron_pop = my_full_neuron_pop.get_data('v')

Figure(
    # membrane potentials for each example
    Panel(input_spikes,
          ylabel="Input spikes", yticks=True, xticks=True, xlim=(0, run_time)),
    Panel(v_my_model_my_input_type_pop.segments[0].filter(name='v')[0],
          ylabel="Membrane potential (mV)",
          data_labels=[my_model_stdp_pop.label],
          yticks=True, xlim=(0, run_time)),
    Panel(exc_input.segments[0].filter(name='gsyn_exc')[0],
          ylabel="Excitatory input",
          yticks=True, xlim=(0, run_time)),
    title="Simple my model examples",
    annotations="Simulated with {}".format(p.name())
).save('tm_synapse.png')

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
    if l.startswith(suffix_timing):
        parsed = l.split(" ")
        u.append(int(parsed[4][3:-1]))
        u.append(int(parsed[5][2:-1]))
        x.append(int(parsed[6][3:-1]))
        x.append(int(parsed[7][2:-1]))
    elif l.startswith(suffix_weight):
        parsed = l.split(" ")
        w.append(int(parsed[3][2:-1]))

# Plotting
spikes = np.array(input_spikes[0])
spks = np.repeat(spikes, 2)
fig = plt.figure()
plt.plot(spks, u, linewidth=2, label='u')
plt.plot(spks, x, linewidth=2, label='x')
plt.scatter(spikes, w, c='c', marker="o", label='w', alpha=0.5)
plt.legend()

plt.show()
p.end()
