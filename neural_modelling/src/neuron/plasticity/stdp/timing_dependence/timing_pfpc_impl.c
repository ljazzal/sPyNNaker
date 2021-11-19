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

#include "timing_pfpc_impl.h"

//---------------------------------------
// Globals
//---------------------------------------
// Exponential lookup-tables
//int16_t exp_sin_lookup[EXP_SIN_LUT_SIZE];
int16_lut *exp_sin_lookup;

//---------------------------------------
// Functions
//---------------------------------------
address_t timing_initialise(address_t address) {

	io_printf(IO_BUF, "timing_pfpc_initialise: starting\n");
    io_printf(IO_BUF, "\tCerebellum PFPC rule\n");

    // Copy LUTs from following memory
//    address_t lut_address = maths_copy_int16_lut_with_size(
//            &address[0], EXP_SIN_LUT_SIZE, &exp_sin_lookup[0]);
    address_t lut_address = address;
    exp_sin_lookup = maths_copy_int16_lut(&lut_address);

    io_printf(IO_BUF, "timing_pfpc_initialise: completed successfully\n");

    return lut_address;
}
