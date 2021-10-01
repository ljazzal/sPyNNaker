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
//! \brief Get an initial post-synaptic timing trace
//! \return the post trace
static inline post_trace_t timing_get_initial_post_trace(void) {
    return (post_trace_t) {};
}

//---------------------------------------
//! \brief Add a post spike to the post trace
//! \param[in] time: the time of the spike
//! \param[in] last_time: the time of the previous spike update
//! \param[in] last_trace: the post trace to update
//! \return the updated post trace
static inline post_trace_t timing_add_post_spike(
        UNUSED uint32_t time, UNUSED uint32_t last_time, UNUSED post_trace_t last_trace) {
    return (post_trace_t) {};
}

//---------------------------------------
//! \brief Add a pre spike to the pre trace
//! \param[in] time: the time of the spike
//! \param[in] last_time: the time of the previous spike update
//! \param[in] last_trace: the pre trace to update
//! \return the updated pre trace
static inline pre_trace_t timing_add_pre_spike(
        UNUSED uint32_t time, UNUSED uint32_t last_time, UNUSED pre_trace_t last_trace) {
    return (pre_trace_t) {};
}

//---------------------------------------
//! \brief Apply a pre-spike timing rule state update
//! \param[in] time: the current time
//! \param[in] trace: the current pre-spike trace
//! \param[in] last_pre_time: the time of the last pre-spike
//! \param[in] last_pre_trace: the trace of the last pre-spike
//! \param[in] last_post_time: the time of the last post-spike
//! \param[in] last_post_trace: the trace of the last post-spike
//! \param[in] previous_state: the state to update
//! \return the updated state
static inline update_state_t timing_apply_pre_spike(
        uint32_t time, UNUSED pre_trace_t trace, uint32_t last_pre_time,
        UNUSED pre_trace_t last_pre_trace, UNUSED uint32_t last_post_time,
        UNUSED post_trace_t last_post_trace, update_state_t previous_state) {

    uint32_t time_since_last_pre = time - last_pre_time;
    int32_t decayed_u = (last_pre_time == 0) ? 0 :
        STDP_FIXED_MUL_16X16(previous_state.weight_region->u,
        maths_lut_exponential_decay(time_since_last_pre, tau_f_lookup));
    previous_state.weight_region->u = decayed_u;
    int32_t initial_u = previous_state.weight_region->u;

    int32_t du = STDP_FIXED_MUL_16X16(previous_state.weight_region->U, STDP_FIXED_POINT_ONE - previous_state.weight_region->u);
    previous_state.weight_region->u += du;
    int32_t new_u = previous_state.weight_region->u;
    previous_state.new_weight = STDP_FIXED_MUL_16X16(previous_state.weight_region->u, previous_state.weight_region->x);

    int32_t exp_tau_d = (last_pre_time == 0) ? STDP_FIXED_POINT_ONE : STDP_FIXED_MUL_16X16(STDP_FIXED_POINT_ONE, maths_lut_exponential_decay(time_since_last_pre, tau_d_lookup));

    int32_t decayed_x = STDP_FIXED_MUL_16X16(STDP_FIXED_POINT_ONE - previous_state.weight_region->x, exp_tau_d); 
    previous_state.weight_region->x = STDP_FIXED_POINT_ONE - decayed_x;
    int32_t initial_x = previous_state.weight_region->x;
    
    previous_state.weight_region->x -= previous_state.new_weight;
    previous_state.weight_region->x = MIN(previous_state.weight_region->x, STDP_FIXED_POINT_ONE);
    int32_t new_x = previous_state.weight_region->x;
    
    log_info("time_since_last_pre_event=%u, u0=%u, u=%u, x0=%u, x=%u, w=%u, decayed_x=%u, exp_tau_d=%d\n",
        time_since_last_pre, initial_u, new_u, initial_x, new_x, previous_state.new_weight, decayed_x, exp_tau_d);
    // return weight_one_term_apply_potentiation(previous_state, decayed_u);
    return previous_state;
}

//---------------------------------------
//! \brief Apply a post-spike timing rule state update
//! \param[in] time: the current time
//! \param[in] trace: the current post-spike trace
//! \param[in] last_pre_time: the time of the last pre-spike
//! \param[in] last_pre_trace: the trace of the last pre-spike
//! \param[in] last_post_time: the time of the last post-spike
//! \param[in] last_post_trace: the trace of the last post-spike
//! \param[in] previous_state: the state to update
//! \return the updated state
static inline update_state_t timing_apply_post_spike(
        UNUSED uint32_t time, UNUSED post_trace_t trace, UNUSED uint32_t last_pre_time,
        UNUSED pre_trace_t last_pre_trace, UNUSED uint32_t last_post_time,
        UNUSED post_trace_t last_post_trace, update_state_t previous_state) {
    return previous_state;
}

#endif // _TM_TIMING_IMPL_H_
