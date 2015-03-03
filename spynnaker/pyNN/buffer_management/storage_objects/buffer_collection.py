from spinnman import exceptions as spinnman_exceptions
from spinnman import constants as spinnman_constants

from spynnaker.pyNN.buffer_management.storage_objects.buffered_sending_region \
    import BufferedSendingRegion
from spynnaker.pyNN.buffer_management.storage_objects.buffers_sent_deque import \
    BuffersSentDeque
from spynnaker.pyNN.utilities import constants
from spynnaker.pyNN import exceptions


class BufferCollection(object):

    def __init__(self):
        self._buffers_to_use = dict()
        self._buffers_sent = dict()
        self._managed_vertex = None

    def set_partitioned_vertex(self, partitioned_vertex):
        if self._managed_vertex is None:
            self._managed_vertex = partitioned_vertex
        else:
            raise exceptions.ConfigurationException(
                "tried to set the managed vertex of a buffer collection region "
                "twice, this is a error due to the immutability of this "
                "parameter, please fix this issue and retry")

    def add_buffer_element_to_transmit(self, region_id, buffer_key, data_piece):
        """ adds a buffer for a given region id

        :param region_id: the region id for which this buffer is being built
        :param buffer_key: the key for the buffer
        :param data_piece: the piece of data to add to the buffer
        :type region_id: int
        :type buffer_key: int
        :type data_piece: int
        :return: None
        :rtype: None
        """
        if region_id not in self._buffers_to_use.keys():
            self._buffers_to_use[region_id] = BufferedSendingRegion()
            self._buffers_sent[region_id] = BuffersSentDeque()
        self._buffers_to_use[region_id].\
            add_entry_to_buffer(buffer_key, data_piece)

    def add_buffer_elements_to_transmit(self, region_id, buffer_key,
                                        data_pieces):
        """ adds a buffer for a given region id

        :param region_id: the region id for which this buffer is being built
        :param buffer_key: the key for the buffer
        :param data_pieces: the pieces of data to add to the buffer
        :type region_id: int
        :type buffer_key: int
        :type data_pieces: iterable
        :return: None
        :rtype: None
        """
        if region_id not in self._buffers_to_use.keys():
            self._buffers_to_use[region_id] = BufferedSendingRegion()
        self._buffers_to_use[region_id].\
            add_entries_to_buffer(buffer_key, data_pieces)

    @property
    def regions_managed(self):
        """ returns the region ids of the regions managed by this buffer
        collection

        :return:
        """
        return self._buffers_to_use.keys()

    def buffer_shutdown(self, region_id):
        return self._buffers_to_use[region_id].buffer_shutdown

    def set_buffer_shutdown(self, region_id):
        self._buffers_to_use[region_id].set_buffer_shutdown()

    def get_size_of_region(self, region_id):
        """ get the size of a region known by the buffer region
        :param region_id: the region id to check the size of
        :return:
        """
        if region_id not in self._buffers_to_use.keys():
            raise exceptions.ConfigurationException(
                "The region id {} is not being managed. Please rectify and "
                "try again".format(region_id))
        return self._buffers_to_use[region_id].region_size

    def set_size_of_region(self, region_id, region_size):
        """ set the region size of a region being managed by the buffered region

        :param region_id: the region id to be managed
        :param region_size: the size of the region to be set
        :return:
        """
        if region_id not in self._buffers_to_use.keys():
            raise exceptions.ConfigurationException(
                "The region id {} is not being managed. Please rectify and "
                "try again".format(region_id))
        self._buffers_to_use[region_id].set_region_size(region_size)

    def get_region_base_address_for(self, region_id):
        """ get the base address of a region

        :param region_id: the region id to get the absolute address from
        :return: the base address of the region
        :rtype: int
        """
        if region_id not in self._buffers_to_use.keys():
            raise exceptions.ConfigurationException(
                "The region id {} is not being managed. Please rectify and "
                "try again".format(region_id))
        return self._buffers_to_use[region_id].region_base_address

    def set_region_base_address_for(self, region_id, new_value):
        """ set the region base address for a given region

        :param region_id: the region to which the base address is setting
        :return: None
        """
        if region_id not in self._buffers_to_use.keys():
            raise exceptions.ConfigurationException(
                "The region id {} is not being managed. Please rectify and "
                "try again".format(region_id))
        return self._buffers_to_use[region_id].\
            set_region_base_address(new_value)

    def get_next_timestamp(self, region_id):
        if region_id not in self._buffers_to_use.keys():
            raise exceptions.ConfigurationException(
                "The region id {} is not being managed. Please rectify and "
                "try again".format(region_id))
        return self._buffers_to_use[region_id].get_next_timestamp()

    def is_region_empty(self, region_id):
        """ checks if a region is empty or not (updates buffer if the last
        timer tic is after what was expected

        :param buffered_packet:
        :return:
        """
        if not self.contains_key(region_id):
            raise exceptions.ConfigurationException(
                "The region id {} is not being managed. Please rectify and "
                "try again".format(region_id))
        buffers_to_send_empty = False
        buffers_sent_empty = False
        if self.is_buffers_sent_for_region(region_id):
            buffers_sent_empty = self._buffers_sent[region_id].is_empty()

        if self.is_buffers_to_use_for_region(region_id):
            buffers_to_send_empty = self._buffers_to_use[region_id].is_region_empty()

        return buffers_sent_empty and buffers_to_send_empty

    def is_region_managed(self, region_id):
        return (self.is_buffers_sent_for_region(region_id) or
                self.is_buffers_to_use_for_region(region_id))

    def contains_key(self, region_id):
        """ checks if a region is being managed so far

        :param region_id: the region id to check if being managed so far
        """
        if region_id in self._buffers_to_use.keys():
            return True
        return False

    def is_buffers_sent_for_region(self, region_id):
        if region_id in self._buffers_sent.keys():
            return True
        else:
            return False

    def is_buffers_to_use_for_region(self, region_id):
        if region_id in self._buffers_to_use.keys():
            return True
        else:
            return False

    def is_more_elements_for_timestamp(self, region_id, timestamp):
        return self._buffers_to_use[region_id].is_timestamp_empty(timestamp)

    def get_next_element(self, region_id):
        return self._buffers_to_use[region_id].get_next_entry()

    def add_sent_packet(self, packet, region_id):
        if region_id not in self._buffers_sent.keys():
            raise  # the sent packet deque should be created when the set of buffers in firstly inserted
        self._buffers_sent[region_id].add_packet(packet)

    def add_sent_packets(self, packets, region_id):
        if isinstance(packets, list):
            for packet in packets:
                self.add_sent_packet(packet, region_id)
        else:
            raise  # error in call parameter: packets needs to be a list

    def remove_packets_in_region_in_seq_no_interval(self, region_id, min_seq_no, max_seq_no):
        if self.is_region_managed(region_id):
            self._buffers_sent[region_id].remove_packets_in_seq_no_interval(min_seq_no, max_seq_no)
        else:
            raise # the region is not managed

    def get_sent_packets(self, region_id):
        return self._buffers_sent[region_id].get_packets()

    def is_sent_packet_list_empty(self, region_id):
        return self._buffers_sent[region_id].is_empty()

    def get_next_sequence_no_for_region(self, region_id):
        return self._buffers_to_use[region_id].get_next_sequence_no()

    def get_min_seq_no(self, region_id):
        value = self._buffers_sent[region_id].get_min_seq_no()
        if value is None:
            value = self._buffers_to_use[region_id].sequence_number
        return value

    def check_sequence_number(self, region_id, sequence_no):
        return self._buffers_to_use[region_id].check_sequence_number(sequence_no)

    # def get_region_absolute_region_address(self, region_id):
    #     """gets the regions absolute region address
    #
    #     :param region_id: the region id to get the absolute address from
    #     :return:
    #     """
    #     if region_id not in self._buffers_to_use.keys():
    #         raise exceptions.ConfigurationException(
    #             "The region id {} is not being managed. Please rectify and "
    #             "try again".format(region_id))
    #     return self._buffers_to_use[region_id].current_absolute_address

    # def get_left_over_space(self, region_id, memory_used):
    #     """ checks how much memory is left over given a number of bytes being
    #      used
    #
    #     :param region_id: the region id to which this calculation is being
    #      carried out on
    #      :type region_id: int
    #     :param memory_used: the amount of memory being used in this region
    #     :type memory_used: int
    #     :return: the memory left over
    #     :rtype: int
    #     """
    #     if region_id not in self._buffers_to_use.keys():
    #         raise exceptions.ConfigurationException(
    #             "The region id {} is not being managed. Please rectify and "
    #             "try again".format(region_id))
    #     total_mem_used = \
    #         self._buffers_to_use[region_id].position_in_region + memory_used
    #     return self._buffers_to_use[region_id].region_size - total_mem_used

    # def process_buffer_packet(self, buffered_packet):
    #     """ method to support callback for sending new buffers down to the
    #      machine
    #
    #     :param buffered_packet: the buffered packet from the board for this vertex
    #     :type buffered_packet: spynnaker.pynn.buffer_management.buffer_packet.BufferPacket
    #     :return: either a request or None
    #     """
    #     # check if the region has got buffers
    #     if buffered_packet.region_id not in self._buffers_to_use.keys():
    #         raise spinnman_exceptions.SpinnmanInvalidPacketException(
    #             "buffered_packet.region_id",
    #             "The region being requested does not contain any buffered data")
    #     if (buffered_packet.count <
    #         (spinnman_constants.EIEIO_DATA_HEADER_SIZE +
    #             constants.TIMESTAMP_SPACE_REQUIREMENT)):
    #         raise spinnman_exceptions.SpinnmanInvalidPacketException(
    #             "buffered_packet.count",
    #             "The count is below what is needed for a eieio header, and so"
    #             " shouldnt have been requested")
    #     return self._managed_vertex.process_buffered_packet(buffered_packet)

    # def get_buffer_for_region(self, region_id):
    #     """ get the buffer for a given region
    #
    #     :param region_id:
    #     :return:
    #     """
    #     if region_id not in self._buffers_to_use.keys():
    #         raise exceptions.ConfigurationException(
    #             "The region id {} is not being managed. Please rectify and "
    #             "try again".format(region_id))
    #     return self._buffers_to_use[region_id].buffer