#ifndef _TM_TIMING_IMPL_H_
#define _TM_TIMING_IMPL_H_

//---------------------------------------
// Typedefines
//---------------------------------------
//! The type of post-spike traces
typedef struct post_trace_t {
} post_trace_t;
//! The type of pre-spike traces
typedef struct pre_trace_t {
} pre_trace_t;

typedef struct {
    int32_t tau_f;
    int32_t tau_d;
} plasticity_trace_region_data_t;

#include <neuron/plasticity/stdp/synapse_structure/synapse_structure_weight_impl.h>
#include <neuron/plasticity/stdp/timing_dependence/timing.h>
#include <neuron/plasticity/stdp/weight_dependence/weight_one_term.h>

// Include debug header for log_info etc
#include <debug.h>

// Include generic plasticity maths functions
#include <neuron/plasticity/stdp/maths.h>
#include <neuron/plasticity/stdp/stdp_typedefs.h>

//---------------------------------------
// Externals
//---------------------------------------
extern int16_lut *tau_f_lookup;
extern int16_lut *tau_d_lookup;
// extern int16_lut *tau_syn_lookup;

//---------------------------------------
// Timing dependence inline functions
//---------------------------------------
static inline post_trace_t timing_get_initial_post_trace(void) {
    return (post_trace_t) {};
}

static inline post_trace_t timing_add_post_spike(
        UNUSED uint32_t time, UNUSED uint32_t last_time, UNUSED post_trace_t last_trace) {
    return (post_trace_t) {};
}

static inline pre_trace_t timing_add_pre_spike(
        UNUSED uint32_t time, UNUSED uint32_t last_time, UNUSED pre_trace_t last_trace) {
    return (pre_trace_t) {};
}

static inline update_state_t timing_apply_pre_spike(
        uint32_t time, UNUSED pre_trace_t trace, uint32_t last_pre_time,
        UNUSED pre_trace_t last_pre_trace, UNUSED uint32_t last_post_time,
        UNUSED post_trace_t last_post_trace, update_state_t previous_state) {

    uint32_t time_since_last_pre = time - last_pre_time;

    // Resources available
    int32_t decayed_u = (last_pre_time == 0) ? 0 :
        STDP_FIXED_MUL_16X16(previous_state.weight_region->u,
        maths_lut_exponential_decay(time_since_last_pre, tau_f_lookup));

    update_state_t new_state = update_resources_available(previous_state, decayed_u);

    // Resources remaining
    int32_t exp_tau_d = (last_pre_time == 0) ? STDP_FIXED_POINT_ONE : STDP_FIXED_MUL_16X16(STDP_FIXED_POINT_ONE, maths_lut_exponential_decay(time_since_last_pre, tau_d_lookup));
    int32_t decayed_x = STDP_FIXED_MUL_16X16(STDP_FIXED_POINT_ONE - previous_state.weight_region->x, exp_tau_d);

    return update_resources_remaining(new_state, decayed_x);    
}

static inline update_state_t timing_apply_post_spike(
        UNUSED uint32_t time, UNUSED post_trace_t trace, UNUSED uint32_t last_pre_time,
        UNUSED pre_trace_t last_pre_trace, UNUSED uint32_t last_post_time,
        UNUSED post_trace_t last_post_trace, update_state_t previous_state) {
    return previous_state;
}

#endif // _TM_TIMING_IMPL_H_
