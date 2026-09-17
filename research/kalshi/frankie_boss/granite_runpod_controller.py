"""Explicit assembly of an existing native controller and frozen Runpod critic."""


def build_runpod_controller(*, enabled=False, legacy=None, bridge=None, journal=None,
                            expected_native_hash=None, expected_critic_config_hash=None,
                            expected_critic_identity_hash=None, config=None, identity=None,
                            runtime_receipt=None, admit_request=None, api_key=None,
                            exchange=None, event=None, controller_event=None,
                            context_encoding='native_v1',
                            spool_directory=None):
    """Return the existing controller without refreshing or allocating resources.

    The caller supplies its real native bridge and durable controller journal,
    independently trusted pins, runtime receipt, private credential and exact
    per-request tokenizer admission. This function derives no expected pins and
    creates no model, source fixture, training loop or replacement calculation.
    ``event`` observes critic transport; ``controller_event`` observes controller
    phases. Disabled mode preserves the existing legacy route.
    """
    if type(enabled) is not bool:
        raise ValueError('enabled must be boolean')
    from .frankie_controller import FrankieForecastController
    if not enabled:
        return FrankieForecastController(enabled=False, legacy=legacy, event=controller_event)

    from .granite_runpod_service import build_runpod_service
    critic = build_runpod_service(enabled=True, config=config, identity=identity,
        runtime_receipt=runtime_receipt, admit_request=admit_request, api_key=api_key,
        exchange=exchange, event=event, spool_directory=spool_directory)
    return FrankieForecastController(enabled=True, bridge=bridge, journal=journal,
        critic=critic, expected_native_hash=expected_native_hash,
        expected_critic_config_hash=expected_critic_config_hash,
        expected_critic_identity_hash=expected_critic_identity_hash,
        context_encoding=context_encoding, event=controller_event)
