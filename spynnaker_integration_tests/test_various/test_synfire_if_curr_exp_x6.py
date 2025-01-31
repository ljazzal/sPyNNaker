#!/usr/bin/python

# Copyright (c) 2017-2019 The University of Manchester
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

"""
Synfirechain-like example with 6 chains
"""
import spynnaker8 as p
from spinnaker_testbase import BaseTestCase


def do_run(nNeurons):
    p.setup(timestep=1.0, min_delay=1.0, max_delay=32.0)
    p.set_number_of_neurons_per_core(p.IF_curr_exp, 100)

    cell_params_lif = {'cm': 0.25, 'i_offset': 0.0, 'tau_m': 10.0,
                       'tau_refrac': 2.0, 'tau_syn_E': 0.5, 'tau_syn_I': 0.5,
                       'v_reset': -65.0, 'v_rest': -65.0, 'v_thresh': -64.4}

    populations = list()
    projections = list()

    weight_to_spike = 2
    delay = 1

    connections = list()
    for i in range(0, nNeurons):
        singleConnection = (i, ((i + 1) % nNeurons), weight_to_spike, delay)
        connections.append(singleConnection)

    injectionConnection = [(0, 0, weight_to_spike, delay)]
    spikeArray = {'spike_times': [[0]]}
    for x in range(6):
        populations.append(p.Population(nNeurons, p.IF_curr_exp,
                                        cell_params_lif))
        populations.append(p.Population(1, p.SpikeSourceArray, spikeArray))

    for x in range(0, 12, 2):
        projections.append(p.Projection(populations[x], populations[x],
                                        p.FromListConnector(connections)))
        connector = p.FromListConnector(injectionConnection)
        projections.append(p.Projection(populations[x+1], populations[x],
                                        connector))
        populations[x].record("spikes")

    p.run(1000)

    spikes = []
    for x in range(0, 12, 2):
        spikes.append(populations[x].spinnaker_get_data("spikes"))

    p.end()

    return spikes


class SynfireIfCurrx6(BaseTestCase):

    def check_run(self):
        nNeurons = 200  # number of neurons in each population
        spikes = do_run(nNeurons)
        for x in range(0, 12, 2):
            self.assertEqual(999, len(spikes[x // 2]))

    def test_run(self):
        self.runsafe(self.check_run)


if __name__ == '__main__':
    nNeurons = 200  # number of neurons in each population
    spikes = do_run(nNeurons)
    for x in range(0, 12, 2):
        print(x, len(spikes[x // 2]))
