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
import spynnaker8 as p
from spinnaker_testbase import BaseTestCase


def a_run():
    n_neurons = 100  # number of neurons in each population

    p.setup(timestep=1.0, min_delay=1.0, max_delay=1.0)

    x = p.Population(
        n_neurons, p.IF_curr_exp(), label='pop_1',
        additional_parameters={"spikes_per_second": "bacon"})
    assert x._vertex.spikes_per_second == "bacon"


class PopAdditionParamsTest(BaseTestCase):

    def test_a_run(self):
        self.runsafe(a_run)


if __name__ == '__main__':
    a_run()
