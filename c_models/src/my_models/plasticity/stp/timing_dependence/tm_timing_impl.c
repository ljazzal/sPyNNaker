#include "tm_timing_impl.h"

// TODO: Describe the layout of the configuration *in SDRAM*
typedef struct my_timing_config {
    accum tau_F;
    accum tau_D;
} my_timing_config_t;

// TODO: Set up any variables here
accum tau_F;
accum tau_D;

//---------------------------------------
// Functions
//---------------------------------------
address_t timing_initialise(address_t address) {

    log_info("timing_initialise: starting");
    log_info("\tSTDP my timing rule");

    // TODO: copy parameters from memory
    my_timing_config_t *config = (my_timing_config_t *) address;
    tau_F = config->tau_F;
    tau_D = config->tau_D;

    log_info("tau_F = %k", tau_F);
    log_info("tau_D = %k", tau_D);
    log_info("timing_initialise: completed successfully");

    // Return the address after the configuration (word aligned)
    return (address_t) (config + 1);
}
