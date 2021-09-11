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
weight = 0.1

# Set the times at which to input a spike
spike_times = np.arange(0, run_time / 4, 20)
spike_times2 = np.arange(run_time - run_time / 4, run_time, 20)

p.setup(time_step)

spikeArray = {"spike_times": spike_times}
spikeArray2 = {"spike_times": spike_times2}
input_pop = p.Population(
    n_neurons, p.SpikeSourceArray(**spikeArray), label="input")
input_pop2 = p.Population(
    n_neurons, p.SpikeSourceArray(**spikeArray2), label="input")

poisson_input = p.Population(1, p.SpikeSourcePoisson(rate=200), label="poisson")
poisson_input2 = p.Population(1, p.SpikeSourcePoisson(rate=50), label="poisson2")

lif_stp_pop = p.Population(
    n_neurons, IFCurrExpStp(U=0.05, tau_f=750, tau_d=10, A=10.0, tau_syn=1, tau_syn_E=1, tau_m=5),
    label="if_curr_exp_stp_pop")

# dc_input = p.DCSource(amplitude=2.5, start=0, stop=run_time - run_time / 4)
# lif_stp_pop.inject(dc_input)


# p.Projection(
#     input_pop, lif_stp_pop,
#     p.OneToOneConnector(), receptor_type='excitatory',
#     synapse_type=p.StaticSynapse(weight=weight))

p.Projection(
    input_pop2, lif_stp_pop,
    p.OneToOneConnector(), receptor_type='excitatory',
    synapse_type=p.StaticSynapse(weight=weight))

p.Projection(
    poisson_input, lif_stp_pop, p.FixedProbabilityConnector(p_connect=0.99),
    receptor_type='excitatory', synapse_type=p.StaticSynapse(weight=2.5)
)

# p.Projection(
#     poisson_input2, lif_stp_pop, p.FixedProbabilityConnector(p_connect=0.5),
#     receptor_type='inhibitory', synapse_type=p.StaticSynapse(weight=-1.0)
# )

# input_pop.record(['spikes'])
poisson_input.record(['spikes'])
lif_stp_pop.record(['v', 'gsyn_exc', 'gsyn_inh', 'i_ext', 'spikes'])

p.run(run_time)


input = poisson_input.get_data('spikes').segments[0].spiketrains
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
