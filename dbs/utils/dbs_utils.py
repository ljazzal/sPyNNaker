# DBS presynaptic spike source
# lja, October 2021
import numpy as np
from spyNNaker.pyNN.models.spike_source.spike_source_array import SpikeSourceArray

class SpikeSourceArrayDbs(SpikeSourceArray):
    """
    SpikeSourceArray that simulates DBS effect:
    https://www.sciencedirect.com/science/article/pii/S1935861X21000929
    """

    def __init__(self, start, stop, frequency):
        
        spike_times = np.arange(start, stop, np.floor(1e3/frequency))
        super().__init__(spike_times)

    @property
    def _spike_times(self):
        return self.__spike_times


class DBSPopulation:

    def __init__(self):
        pass