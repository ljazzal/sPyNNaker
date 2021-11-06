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
    int32_t A;
    int32_t U;
} plasticity_weight_region_data_t;

// An intermediate data structure; can have more accuracy and use more storage
// than the variable structure e.g. weight might be 16-bit but stored as 32-bit
// here
typedef struct {
    int32_t initial_weight;
    int32_t weight;
    plasticity_weight_region_data_t *weight_region;
} weight_state_t;

// TODO: Ensure this includes and implements the correct interface
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
        .initial_weight = (int32_t) weight,
        .weight = 0,
        .weight_region = &plasticity_weight_region_data[synapse_type]
    };
}

//---------------------------------------
static inline weight_state_t update_resources_available(
        weight_state_t state, int32_t decayed_u) {

    // Update the fraction of available resources ready for use
    // state.weight = STDP_FIXED_MUL_16X16(state.weight_region->u, state.weight_region->x);
    state.weight_region->u = decayed_u;
    log_info("u=%u\n", state.weight_region->u);
    // int32_t initial_u = previous_state.weight_region->u;
    state.weight_region->u += STDP_FIXED_MUL_16X16(state.weight_region->U, STDP_FIXED_POINT_ONE - state.weight_region->u);
    log_info("u=%u\n", state.weight_region->u);
    // int32_t new_u = previous_state.weight_region->u;
    state.weight = STDP_FIXED_MUL_16X16(state.weight_region->u, state.weight_region->x);
    return state;
}

//---------------------------------------
static inline weight_state_t update_resources_remaining(
        weight_state_t state, int32_t decayed_x) {

    // Update fraction of resources remaining
    state.weight_region->x = STDP_FIXED_POINT_ONE - decayed_x;
    log_info("x=%u\n", state.weight_region->x);
    // int32_t initial_x = previous_state.weight_region->x;
    state.weight_region->x -= state.weight;
    // Ensure resource fractions remaining don't exceed 1
    state.weight_region->x = MIN(state.weight_region->x, STDP_FIXED_POINT_ONE);
    log_info("x=%u\n", state.weight_region->x);
    // int32_t new_x = state.weight_region->x;
    return state;
}

//---------------------------------------
static inline weight_t weight_get_final(weight_state_t new_state) {

    // TODO: Perform operations to get the final weight from the intermediate
    // state, taking into account all potentiation and depression
    // Note: it is recommended to do a single complex operation here rather
    // than one for each potentiation or depression if possible

    // int32_t new_weight = STDP_FIXED_MUL_16X16(new_state.weight_region->u, new_state.weight_region->x);
    int32_t delta_weight = new_state.weight + 2 * STDP_FIXED_POINT_ONE;
    int32_t new_weight = STDP_FIXED_MUL_16X16(new_state.weight, delta_weight);
    // int32_t new_weight = new_state.weight;  


    // Clamp new weight
    new_weight = MIN(
            new_state.weight_region->max_weight,
            MAX(new_weight, new_state.weight_region->min_weight));

    log_info("w:%u, w_:%u, w_i:%u",
            new_weight, new_state.weight, new_state.initial_weight);

    return (weight_t) new_weight;
}

#endif // _TM_WEIGHT_H_
