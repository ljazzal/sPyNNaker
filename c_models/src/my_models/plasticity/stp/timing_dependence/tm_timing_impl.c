#include "tm_timing_impl.h"

//---------------------------------------
// Globals
//---------------------------------------
// Exponential lookup-tables
// TODO: see if we can move to int32_lut for better accuracy
//! Lookup table for &tau_f exponential decay
int16_lut *tau_f_lookup;
//! Lookup table for &tau_d exponential decay
int16_lut *tau_d_lookup;
//! Lookup table for &tau_syn exponential decay
int16_lut *tau_syn_lookup;

//! Global plasticity parameter data
plasticity_trace_region_data_t plasticity_trace_region_data;

//! How the configuration data for TM is laid out in SDRAM.
typedef struct {
    int32_t U;
    int32_t tau_f;
    int32_t tau_d;
    int32_t tau_syn;
    int32_t delta_tau_inv;
    uint32_t lut_data[];
} tm_config_t;


//---------------------------------------
// Functions
//---------------------------------------
address_t timing_initialise(address_t address) {

    log_info("timing_initialise: starting");
    log_info("\tSTDP my timing rule");

    tm_config_t *config = (tm_config_t *) address;

    // Copy parameters
    plasticity_trace_region_data.U = config->U;
    plasticity_trace_region_data.tau_f = config->tau_f;
    plasticity_trace_region_data.tau_d = config->tau_d;
    plasticity_trace_region_data.tau_syn = config->tau_syn;
    plasticity_trace_region_data.delta_tau_inv = config->delta_tau_inv;

    // Copy LUTs from following memory
    address_t lut_address = config->lut_data;
    // address_t lut_address = address;
    tau_f_lookup = maths_copy_int16_lut(&lut_address);
    tau_d_lookup = maths_copy_int16_lut(&lut_address);
    tau_syn_lookup = maths_copy_int16_lut(&lut_address);

    log_info("timing_initialise: completed successfully");

    // Return the address after the configuration (word aligned)
    return lut_address;
}
