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

import numpy as np
from spyNNaker.pyNN.models.spike_source.spike_source_array import SpikeSourceArray
# from spynnaker.pyNN.utilities import utility_calls
import utility_calls


class SpikeSourceArrayDbs(SpikeSourceArray):
    """
    SpikeSourceArray that simulates DBS effect:
    https://www.sciencedirect.com/science/article/pii/S1935861X21000929
    """

    def __init__(
            self, start, stop, frequency):
        
        spike_times = np.arange(start, stop, np.floor(1e3/frequency))
        super().__init__(spike_times)

    @property
    def _spike_times(self):
        return self.__spike_times
