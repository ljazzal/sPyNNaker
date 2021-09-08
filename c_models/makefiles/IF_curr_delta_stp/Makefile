APP = $(notdir $(CURDIR))
BUILD_DIR = build/

NEURON_MODEL = $(NEURON_DIR)/neuron/models/neuron_model_lif_impl.c
NEURON_MODEL_H = $(NEURON_DIR)/neuron/models/neuron_model_lif_impl.h
ADDITIONAL_INPUT_H = $(EXTRA_SRC_DIR)/my_models/additional_inputs/stp_input.h
INPUT_TYPE_H = $(NEURON_DIR)/neuron/input_types/input_type_current.h
NEURON_IMPL_H = $(NEURON_DIR)/neuron/implementations/neuron_impl_standard.h
THRESHOLD_TYPE_H = $(NEURON_DIR)/neuron/threshold_types/threshold_type_static.h
SYNAPSE_TYPE_H = $(NEURON_DIR)/neuron/synapse_types/synapse_types_delta_impl.h
SYNAPSE_DYNAMICS = $(NEURON_DIR)/neuron/plasticity/synapse_dynamics_static_impl.c

include ../extra.mk