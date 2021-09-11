//! \file
//! \brief Input type is standard current-based model
#ifndef _STP_INPUT_CURRENT_H_
#define _STP_INPUT_CURRENT_H_

#include <neuron/input_types/input_type.h>

typedef struct input_type_t {
    REAL u; // fraction of resources ready for use
    REAL x; // fraction of resources available after neurotransmitter depletion
    REAL I_stp; // synaptic current generated following STP

    REAL A; // weight
    REAL U; // increase in utilization u produced by a spike
    REAL exp_tau_F; // exp(-(machine time step in ms) / (tau_F))
    REAL exp_tau_D; // exp(-(machine time step in ms) / (tau_D)))
    REAL exp_tau_syn; // exp(-(machine time step in ms) / (tau_syn))
} input_type_t;

static inline void _stp_update_usage(input_type_t *input_type) {
    // Resources ready update (u)
    input_type->u *= (1 - input_type->U) * input_type->exp_tau_F;
    input_type->u += input_type->U;
}

static inline void _stp_update_remaining(input_type_t *input_type) {
    // Resources remaining after neurotransmitter depletion (x)
    input_type->x *= (1 - input_type->u) * input_type->exp_tau_D;
    input_type->x += 1 - input_type->exp_tau_D;
}

//! Scaling factor (trivial!) for input currents
static const REAL INPUT_SCALE_FACTOR = ONE;

//! \brief Gets the actual input value. This allows any scaling to take place
//! \param[in,out] value: The array of the receptor-based values of the input
//!     before scaling
//! \param[in] input_type: The input type pointer to the parameters
//! \param[in] num_receptors: The number of receptors.
//!     The size of the \p value array.
//! \return Pointer to array of values of the receptor-based input after
//!     scaling
static inline input_t *input_type_get_input_value(
        input_t *restrict value, input_type_t *input_type,
        uint16_t num_receptors) {
    for (int i = 0; i < num_receptors; i++) {
        // Use synaptic resources
        _stp_update_usage(input_type);

        // Update input current according to usage
        value[i] *= input_type->exp_tau_syn;
        value[i] += input_type->A * input_type->u * input_type->x;
        
        // Update remaining resources
        _stp_update_remaining(input_type);

        // value[i] = value[i] * INPUT_SCALE_FACTOR;
    }
    return &value[0];
}

//! \brief Converts an excitatory input into an excitatory current
//! \param[in,out] exc_input: Pointer to array of excitatory inputs from
//!     different receptors this timestep. Note that this will already have
//!     been scaled by input_type_get_input_value()
//! \param[in] input_type: The input type pointer to the parameters
//! \param[in] membrane_voltage: The membrane voltage to use for the input
static inline void input_type_convert_excitatory_input_to_current(
        UNUSED input_t *restrict exc_input,
        UNUSED const input_type_t *input_type,
        UNUSED state_t membrane_voltage) {
}

//! \brief Converts an inhibitory input into an inhibitory current
//! \param[in,out] inh_input: Pointer to array of inhibitory inputs from
//!     different receptors this timestep. Note that this will already have
//!     been scaled by input_type_get_input_value()
//! \param[in] input_type: The input type pointer to the parameters
//! \param[in] membrane_voltage: The membrane voltage to use for the input
static inline void input_type_convert_inhibitory_input_to_current(
        UNUSED input_t *restrict inh_input,
        UNUSED const input_type_t *input_type,
        UNUSED state_t membrane_voltage) {
}

#endif // _STP_INPUT_CURRENT_H_
