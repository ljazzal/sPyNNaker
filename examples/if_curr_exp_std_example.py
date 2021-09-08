# import spynnaker8 and plotting stuff
import spynnaker8 as p
from pyNN.utility.plotting import Figure, Panel
import matplotlib.pyplot as plt
import numpy as np

from python_models8.neuron.builds.if_curr_exp_stp import IFCurrExpStp


# Set the run time of the execution
run_time = 1000

# Set the time step of the simulation in milliseconds
time_step = 1.0

# Set the number of neurons to simulate
n_neurons = 1

# Set the i_offset current
i_offset = 0.0

# Set the weight of input spikes
weight = 3.0

# Set the times at which to input a spike
spike_times = np.arange(0, run_time, 10)

p.setup(time_step)

spikeArray = {"spike_times": spike_times}
input_pop = p.Population(
    n_neurons, p.SpikeSourceArray(**spikeArray), label="input")

lif_stp_pop = p.Population(
    n_neurons, IFCurrExpStp(U=0.05, tau_f=250, tau_d=50),
    label="if_curr_exp_stp_pop")

p.Projection(
    input_pop, lif_stp_pop,
    p.OneToOneConnector(), receptor_type='excitatory',
    synapse_type=p.StaticSynapse(weight=weight))

input_pop.record(['spikes'])
lif_stp_pop.record(['v', 'gsyn_exc', 'gsyn_inh', 'i_ext', 'spikes'])

p.run(run_time)


input = input_pop.get_data('spikes').segments[0].spiketrains
data = lif_stp_pop.get_data()
spikes = lif_stp_pop.get_data('spikes').segments[0].spiketrains
v_lif_stp_pop = lif_stp_pop.get_data('v')
exc_input = lif_stp_pop.get_data('gsyn_exc')
inh_input = lif_stp_pop.get_data('gsyn_inh')
add_input = lif_stp_pop.get_data('i_ext')

Figure(
    Panel(input,
          ylabel="Input spikes", yticks=True, xticks=True, xlim=(0, run_time)),
    Panel(exc_input.segments[0].filter(name='gsyn_exc')[0],
          ylabel="Excitatory input",
          data_labels=[lif_stp_pop.label],
          yticks=True, xlim=(0, run_time)),
    Panel(inh_input.segments[0].filter(name='gsyn_inh')[0],
          ylabel="Inhibitory input",
          data_labels=[lif_stp_pop.label],
          yticks=True, xlim=(0, run_time)),
    Panel(v_lif_stp_pop.segments[0].filter(name='v')[0],
          ylabel="Membrane potential (mV)",
          data_labels=[lif_stp_pop.label],
          yticks=True, xlim=(0, run_time)),
    Panel(spikes,
          ylabel="Output spikes", yticks=True, xticks=True, xlim=(0, run_time)),
    Panel(add_input.segments[0].filter(name='i_ext')[0],
          ylabel="Postsynaptic input",
          data_labels=[lif_stp_pop.label],
          yticks=True, xticks=True, xlim=(0, run_time)),
    title="Simple my model examples",
    annotations="Simulated with {}".format(p.name())
)
plt.show()

p.end()
