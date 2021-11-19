/*
 * Copyright (c) 2017-2021 The University of Manchester
 *
 * This program is free software: you can redistribute it and/or modify
 * it under the terms of the GNU General Public License as published by
 * the Free Software Foundation, either version 3 of the License, or
 * (at your option) any later version.
 *
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License
 * along with this program.  If not, see <http://www.gnu.org/licenses/>.
 */

#include "weight_mfvn_impl.h"

//---------------------------------------
// Globals
//---------------------------------------
// Global plasticity parameter data
plasticity_weight_region_data_t *plasticity_weight_region_data;
uint32_t *weight_shift;

typedef struct {
    accum min_weight;
    accum max_weight;
    accum a2_plus;
    accum a2_minus;
} mfvn_config_t;

//---------------------------------------
// Functions
//---------------------------------------
address_t weight_initialise(
        address_t address, uint32_t n_synapse_types,
        uint32_t *ring_buffer_to_input_buffer_left_shifts) {

    io_printf(IO_BUF, "mfvn weight_initialise: starting\n");
    io_printf(IO_BUF, "\tSTDP mfvn  weight dependence\n");

    // Copy plasticity region data from address
    // **NOTE** this seems somewhat safer than relying on sizeof
    plasticity_weight_region_data_t *dtcm_copy = plasticity_weight_region_data =
        spin1_malloc(sizeof(plasticity_weight_region_data_t) * n_synapse_types);

    if (plasticity_weight_region_data == NULL) {
        log_error("Could not initialise weight region data");
        return NULL;
    }

    weight_shift = spin1_malloc(sizeof(uint32_t) * n_synapse_types);

    if (weight_shift == NULL) {
        log_error("Could not initialise weight region data");
        return NULL;
    }

    mfvn_config_t *config = (mfvn_config_t *) address;
    for (uint32_t s = 0; s < n_synapse_types; s++) {
        // Copy parameters
        dtcm_copy[s].min_weight = config->min_weight;
        dtcm_copy[s].max_weight = config->max_weight;
        dtcm_copy[s].a2_plus = config->a2_plus;
        dtcm_copy[s].a2_minus = config->a2_minus;

        // Get the weight shift for switching from int16 to accum
        weight_shift[s] = ring_buffer_to_input_buffer_left_shifts[s];

        io_printf(IO_BUF,
            "\tSynapse type %u: Min weight:%d, Max weight:%d, A2+:%d, A2-:%d,"
            " Weight multiply right shift:%u\n",
            s, dtcm_copy[s].min_weight, dtcm_copy[s].max_weight,
            dtcm_copy[s].a2_plus, dtcm_copy[s].a2_minus, weight_shift[s]);
    }

    io_printf(IO_BUF, "mfvn weight initialisation: completed successfully\n");

    // Return end address of region
    return (address_t) config;
}
