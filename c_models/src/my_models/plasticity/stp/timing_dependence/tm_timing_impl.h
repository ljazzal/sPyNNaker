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
    int32_t U;
    int32_t tau_f;
    int32_t tau_d;
    int32_t tau_syn;
    int32_t delta_tau_inv;
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
extern int16_lut *tau_syn_lookup;

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
    extern plasticity_trace_region_data_t plasticity_trace_region_data;

    // Record initial synapse weight (specified by user)
    if (last_pre_time == 0) {
        previous_state.weight_region->initial_weight = previous_state.weight;
    }

    uint32_t time_since_last_pre = time - last_pre_time;
    log_info("w_i:%u", previous_state.weight_region->initial_weight);

    int32_t Puu = maths_lut_exponential_decay(time_since_last_pre, tau_f_lookup);
    int32_t Pyy = maths_lut_exponential_decay(time_since_last_pre, tau_syn_lookup);
    int32_t Pzz = maths_lut_exponential_decay(time_since_last_pre, tau_d_lookup);
    log_info("Puu:%u, Pyy:%u, Pzz:%u", Puu, Pyy, Pzz);


    int32_t Pxy = STDP_FIXED_MUL_16X16((Pzz - STDP_FIXED_POINT_ONE), plasticity_trace_region_data.tau_d) - STDP_FIXED_MUL_16X16((Pyy - STDP_FIXED_POINT_ONE), plasticity_trace_region_data.tau_syn);
    Pxy = STDP_FIXED_MUL_16X16(Pxy, plasticity_trace_region_data.delta_tau_inv);
    int32_t Pxz = STDP_FIXED_POINT_ONE - Pzz;
    log_info("Pxy:%u, Pxz:%u, delta_tau_inv:%u", Pxy, Pxz, plasticity_trace_region_data.tau_d);

    int32_t z = STDP_FIXED_POINT_ONE - previous_state.weight_region->x - previous_state.weight_region->y;
    log_info("z:%u, y:%u, x:%u, u:%u", z, previous_state.weight_region->y, previous_state.weight_region->x, previous_state.weight_region->u);

    // Resources available
    previous_state.weight_region->u = STDP_FIXED_MUL_16X16(previous_state.weight_region->u, Puu);
    previous_state.weight_region->x += STDP_FIXED_MUL_16X16(previous_state.weight_region->y, Pxy) +
        STDP_FIXED_MUL_16X16(z, Pxz);
    previous_state.weight_region->y = STDP_FIXED_MUL_16X16(previous_state.weight_region->y, Pyy);
    log_info("z:%u, y:%u, x:%u, u:%u", z, previous_state.weight_region->y, previous_state.weight_region->x, previous_state.weight_region->u);

    // Update u
    previous_state.weight_region->u += STDP_FIXED_MUL_16X16(plasticity_trace_region_data.U, STDP_FIXED_POINT_ONE - previous_state.weight_region->u);
    log_info("z:%u, y:%u, x:%u, u:%u", z, previous_state.weight_region->y, previous_state.weight_region->x, previous_state.weight_region->u);

    // Weight update
    int32_t delta_psc = STDP_FIXED_MUL_16X16(previous_state.weight_region->u, previous_state.weight_region->x);
    log_info("delta_psc:%u", delta_psc);
    previous_state.weight = STDP_FIXED_MUL_16X16(delta_psc, previous_state.weight_region->initial_weight);
    // previous_state.weight_region->initial_weight += Pyy;

    // Resources remaining
    previous_state.weight_region->x -= delta_psc;
    previous_state.weight_region->y += delta_psc;

    return previous_state;    
}

static inline update_state_t timing_apply_post_spike(
        UNUSED uint32_t time, UNUSED post_trace_t trace, UNUSED uint32_t last_pre_time,
        UNUSED pre_trace_t last_pre_trace, UNUSED uint32_t last_post_time,
        UNUSED post_trace_t last_post_trace, update_state_t previous_state) {
    return previous_state;
}

#endif // _TM_TIMING_IMPL_H_
