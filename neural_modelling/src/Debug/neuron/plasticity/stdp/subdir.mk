################################################################################
# Automatically-generated file. Do not edit!
################################################################################

# Add inputs and outputs from these tool invocations to the build variables 
C_SRCS += \
../neuron/plasticity/stdp/synapse_dynamics_stdp_mad_impl.c 

OBJS += \
./neuron/plasticity/stdp/synapse_dynamics_stdp_mad_impl.o 

C_DEPS += \
./neuron/plasticity/stdp/synapse_dynamics_stdp_mad_impl.d 


# Each subdirectory must supply rules for building sources it contributes
neuron/plasticity/stdp/%.o: ../neuron/plasticity/stdp/%.c
	@echo 'Building file: $<'
	@echo 'Invoking: GCC C Compiler'
	gcc -I"/Users/ghost/git/SpiNNMan/c_models" -I"/Users/ghost/git/spinnaker_tools/include" -I"/Users/ghost/git/SpiNNFrontEndCommon/c_common" -O0 -g3 -Wall -c -fmessage-length=0 -MMD -MP -MF"$(@:%.o=%.d)" -MT"$(@)" -o "$@" "$<"
	@echo 'Finished building: $<'
	@echo ' '


