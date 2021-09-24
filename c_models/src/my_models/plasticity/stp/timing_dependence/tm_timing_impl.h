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
    int16_t ru;
    int16_t ry;
    int16_t rz;
} pre_trace_t;

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
    // extern int16_lut *tau_d_lookup;
    // // Get time since last spike
    // uint32_t delta_time = time - last_time;

    // // Decay previous o1 and o2 traces
    // int32_t decayed_o1_trace = STDP_FIXED_MUL_16X16(last_trace,
    //         maths_lut_exponential_decay(delta_time, tau_d_lookup));

    // // Add energy caused by new spike to trace
    // // **NOTE** o2 trace is pre-multiplied by a3_plus
    // int32_t new_o1_trace = decayed_o1_trace + STDP_FIXED_POINT_ONE;

    // log_debug("\tdelta_time=%d, o1=%d\n", delta_time, new_o1_trace);

    // Return new pre- synaptic event with decayed trace values with energy
    // for new spike added
    // return (post_trace_t) new_o1_trace;
    return (post_trace_t) {};
}

//---------------------------------------
//! \brief Add a pre spike to the pre trace
//! \param[in] time: the time of the spike
//! \param[in] last_time: the time of the previous spike update
//! \param[in] last_trace: the pre trace to update
//! \return the updated pre trace
static inline pre_trace_t timing_add_pre_spike(
        uint32_t time, uint32_t last_time, pre_trace_t last_trace) {
    extern int16_lut *tau_f_lookup;
    // Get time since last spike
    uint32_t delta_time = time - last_time;

    // Decay previous ru, ry and rz traces
    int32_t decayed_ru_trace = (last_time == 0) ? 0 :
        STDP_FIXED_MUL_16X16(last_trace.ru,
        maths_lut_exponential_decay(delta_time, tau_f_lookup));
    
    // int32_t decayed_ry_trace = (last_time == 0) ? 0 :
    //     STDP_FIXED_MUL_16X16(last_trace.ry,
    //     maths_lut_exponential_decay(delta_time, tau_d_lookup));
    
    // int32_t decayed_rz_trace = (last_time == 0) ? 0 :
    //     STDP_FIXED_MUL_16X16(last_trace.rz,
    //     maths_lut_exponential_decay(delta_time, tau_syn_lookup));

    // Add energy caused by new spike to trace
    int32_t new_ru = decayed_ru_trace + STDP_FIXED_POINT_ONE;
    // int32_t new_ry = decayed_ry_trace + STDP_FIXED_POINT_ONE;
    // int32_t new_rz = decayed_rz_trace + STDP_FIXED_POINT_ONE;


    log_info("\tdelta_time=%u, r1=%d\n", delta_time, new_ru);

    // Return new pre-synaptic event with decayed trace values with energy
    // for new spike added
    return (pre_trace_t) new_ru_trace;
    // return (pre_trace_t) {.ru = new_ru, .ry = new_ry, .rz = new_rz};
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
        uint32_t time, pre_trace_t trace, uint32_t last_pre_time,
        UNUSED pre_trace_t last_pre_trace, UNUSED uint32_t last_post_time,
        UNUSED post_trace_t last_post_trace, update_state_t previous_state) {
    extern int16_lut *tau_d_lookup;

    // Get time of event relative to last post-synaptic event
    // uint32_t time_since_last_post = time - last_post_time;
    // int32_t decayed_o1 = STDP_FIXED_MUL_16X16(last_post_trace,
    //     maths_lut_exponential_decay(time_since_last_post, tau_d_lookup));
    uint32_t time_since_last_pre = time - last_pre_time;
    int32_t decayed_o1 = STDP_FIXED_MUL_16X16(trace,
        maths_lut_exponential_decay(time_since_last_pre, tau_d_lookup));

    log_info("\t\t\ttime_since_last_pre_event=%u, decayed_o1=%d\n",
            time_since_last_pre, decayed_o1);

    // Apply depression to state (which is a weight_state)
    return weight_one_term_apply_potentiation(previous_state, decayed_o1);
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
    // extern int16_lut *tau_f_lookup;

    // Get time of event relative to last pre-synaptic event
    // uint32_t time_since_last_pre = time - last_pre_time;
    // if (time_since_last_pre > 0) {
    //     int32_t decayed_r1 = STDP_FIXED_MUL_16X16(last_pre_trace,
    //         maths_lut_exponential_decay(time_since_last_pre, tau_f_lookup));

    //     log_debug("\t\t\ttime_since_last_pre_event=%u, decayed_r1=%d\n",
    //             time_since_last_pre, decayed_r1);

    //     // Apply potentiation to state (which is a weight_state)
    //     return weight_one_term_apply_potentiation(previous_state, decayed_r1);
    // } else {
    //     return previous_state;
    // }
    return previous_state;
}

#endif // _TM_TIMING_IMPL_H_
