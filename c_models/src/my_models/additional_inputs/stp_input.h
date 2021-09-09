#ifndef _STP_INPUT_H_
#define _STP_INPUT_H_

#include <neuron/additional_inputs/additional_input.h>

typedef struct additional_input_t {
    REAL u; // fraction of resources ready for use
    REAL x; // fraction of resources available after neurotransmitter depletion
    REAL I_stp; // synaptic current generated following STP

    REAL A; // weight
    REAL U; // increase in utilization u produced by a spike
    REAL exp_tau_F; // exp(-(machine time step in ms) / (tau_F))
    REAL exp_tau_D; // exp(-(machine time step in ms) / (tau_D)))
    REAL exp_tau_syn; // exp(-(machine time step in ms) / (tau_syn))
} additional_input_t;

//! \brief Gets the value of current provided by the additional input this
//!     timestep
//! \param[in] additional_input The additional input type pointer to the
//!     parameters
//! \param[in] membrane_voltage The membrane voltage of the neuron
//! \return The value of the input after scaling
static input_t additional_input_get_input_value_as_current(
        additional_input_t *additional_input,
        state_t membrane_voltage) {
    use(membrane_voltage);

    additional_input->u *= additional_input->exp_tau_F;
    // additional_input->u += additional_input->U;

    // Update input current resulting from STP process
    additional_input->I_stp *= additional_input->exp_tau_syn;
    // additional_input->I_stp += additional_input->A * additional_input->u * additional_input->x;

    // Resources remaining after neurotransmitter depletion (x)
    additional_input->x *= additional_input->exp_tau_D;
    additional_input->x += 1 - additional_input->exp_tau_D;
    // additional_input->x += 1 - additional_input->exp_tau_D;
    return additional_input->I_stp;
}

//! \brief Notifies the additional input type that the neuron has spiked
//! \param[in] additional_input The additional input type pointer to the
//!     parameters
static void additional_input_has_spiked(
        additional_input_t *additional_input) {
    // Resources ready update (u)
    // additional_input->u += additional_input->U;
    additional_input->u *= -additional_input->U * additional_input->exp_tau_F;
    additional_input->u += additional_input->U;

    // // Update input current resulting from STP process
    // additional_input->I_stp += additional_input->A * additional_input->u * additional_input->x;
    additional_input->I_stp += additional_input->A * additional_input->u * additional_input->x;

    // // Resources remaining after neurotransmitter depletion (x)
    // additional_input->x += 1 - additional_input->exp_tau_D;
    additional_input->x *= -additional_input->u * additional_input->exp_tau_D;
}

#endif // _STP_INPUT_H_
