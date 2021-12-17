#include "tm_timing_impl.h"

//---------------------------------------
// Globals
//---------------------------------------
// Exponential lookup-tables
//! Lookup table for &tau_f exponential decay
int16_lut *tau_f_lookup;
//! Lookup table for &tau_d exponential decay
int16_lut *tau_d_lookup;
//! Lookup table for &tau_syn exponential decay
int16_lut *tau_syn_lookup;

//! Global plasticity parameter data
plasticity_trace_region_data_t *plasticity_trace_region_data;

//! How the configuration data for TM is laid out in SDRAM.
typedef struct {
    uint32_t synapse_type_id;
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
void timing_initialise_data_structure(address_t address, uint32_t n_synapse_types) {

    // Copy plasticity parameter data from address; same format in both
    plasticity_trace_region_data = (plasticity_trace_region_data_t *)
            spin1_malloc(n_synapse_types * sizeof(plasticity_trace_region_data_t));
    // if (plasticity_trace_region_data == NULL) {
    //     log_error("Error allocating plasticity weight data");
    //     return NULL;
    // }
    // plasticity_weight_region_data_t *config =
    //     (plasticity_weight_region_data_t *) address;
    
    // return (address_t) &config[0];
    tau_f_lookup = (int16_lut *)
        spin1_malloc(n_synapse_types * sizeof(int16_lut));
    tau_d_lookup = (int16_lut *)
        spin1_malloc(n_synapse_types * sizeof(int16_lut));
    tau_syn_lookup = (int16_lut *)
        spin1_malloc(n_synapse_types * sizeof(int16_lut));
}

address_t timing_initialise(address_t address, uint32_t synapse_index) {

    log_info("timing_initialise %u: starting", synapse_index);
    log_info("\tMulti-TM timing rule");

    tm_config_t *config = (tm_config_t *) address;

    // Copy parameters
    plasticity_trace_region_data[synapse_index].synapse_type_id = config->synapse_type_id;
    plasticity_trace_region_data[synapse_index].U = config->U;
    plasticity_trace_region_data[synapse_index].tau_f = config->tau_f;
    plasticity_trace_region_data[synapse_index].tau_d = config->tau_d;
    plasticity_trace_region_data[synapse_index].tau_syn = config->tau_syn;
    plasticity_trace_region_data[synapse_index].delta_tau_inv = config->delta_tau_inv;

    // Copy LUTs from following memory
    address_t lut_address = config->lut_data;
    // FIXME!
    // tau_syn_lookup[synapse_index] = maths_copy_int16_lut(&lut_address);
    // tau_f_lookup[synapse_index] = maths_copy_int16_lut(&lut_address);
    // tau_d_lookup[synapse_index] = maths_copy_int16_lut(&lut_address);
    tau_syn_lookup = maths_copy_int16_lut(&lut_address);
    tau_f_lookup = maths_copy_int16_lut(&lut_address);
    tau_d_lookup = maths_copy_int16_lut(&lut_address);

    log_info("timing_initialise %u: completed successfully", synapse_index);

    // Return the address after the configuration (word aligned)
    return lut_address;
}
