#ifndef _TM_WEIGHT_H_
#define _TM_WEIGHT_H_

// Because spin1_memcpy() is used in various places
#include <spin1_api.h>

// Include generic plasticity maths functions
#include <neuron/plasticity/stdp/maths.h>
#include <neuron/plasticity/stdp/stdp_typedefs.h>
#include <neuron/synapse_row.h>

#include <debug.h>

// A structure for the variables
typedef struct {
    int32_t min_weight;
    int32_t max_weight;
    int32_t u;
    int32_t x;
    int32_t y;
    int32_t initial_weight;
} plasticity_weight_region_data_t;

// An intermediate data structure; can have more accuracy and use more storage
// than the variable structure e.g. weight might be 16-bit but stored as 32-bit
// here
// TODO: determine if intermediate data structure can help with accuracy
typedef struct {
    int32_t weight;
    plasticity_weight_region_data_t *weight_region;
} weight_state_t;

// TODO: Ensure this includes and implements the correct interface
// NOTE: Can probably do with base class
#include <neuron/plasticity/stdp/weight_dependence/weight_one_term.h>

// The external variables of the weight rule
extern plasticity_weight_region_data_t *plasticity_weight_region_data;

//---------------------------------------
// STDP weight dependence functions
//---------------------------------------
static inline weight_state_t weight_get_initial(
        weight_t weight, index_t synapse_type) {

    // TODO: Store the data in the intermediate data structure
    return (weight_state_t ) {
        .weight = (int32_t) weight,
        .weight_region = &plasticity_weight_region_data[synapse_type]
    };
}

//---------------------------------------
static inline weight_t weight_get_final(weight_state_t new_state) {

    // Clamp new weight
    int32_t new_weight = MIN(
            new_state.weight_region->max_weight,
            MAX(new_state.weight, new_state.weight_region->min_weight));

    log_info("w:%u", new_weight);

    return (weight_t) new_weight;
}

#endif // _TM_WEIGHT_H_
