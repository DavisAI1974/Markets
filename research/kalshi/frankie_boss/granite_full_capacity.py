"""Full request capacity measurement without native model dependencies."""
import hashlib
from .granite_run_artifacts import canonical

def measure_request_capacity(body, tokenizer_directory):
    """Diagnostic full-token count even when the current transport cannot fit it.

    This is not a service admission receipt. The production admission callable
    still validates its complete request contract and accepted serving limit.
    """
    from .granite_run_artifacts import strict_json
    from .granite_runpod_tokenizer import LocalTokenizerAdmission, MAX_REQUEST_BYTES
    from .granite_runpod_admission import invocation
    from pathlib import Path
    request = strict_json(body)
    if canonical(request) != body:
        raise ValueError('canonical actual service request required')
    verifier = LocalTokenizerAdmission(tokenizer_directory, served_model_name=request['model'])
    ids = verifier._tokenizer.apply_chat_template(request['messages'], **invocation())
    if type(ids) is not list or not ids or any(type(i) is not int or i < 0 for i in ids):
        raise ValueError('complete tokenizer IDs required')
    positional_limit = strict_json((Path(tokenizer_directory)/'config.json').read_bytes())['max_position_embeddings']
    total = len(ids)+request['max_tokens']
    return dict(schema='BOSS_FULL_REQUEST_CAPACITY_DIAGNOSTIC_V1',
        request_sha256=hashlib.sha256(body).hexdigest(), request_bytes=len(body),
        input_tokens=len(ids), output_tokens=request['max_tokens'], total_tokens=total,
        token_ids_sha256=hashlib.sha256(canonical(ids)).hexdigest(),
        tokenizer_sha256=verifier.tokenizer_sha256, positional_limit=positional_limit,
        fits_model_positions=total <= positional_limit,
        fits_accepted_service=total <= 4096 and len(body) <= MAX_REQUEST_BYTES,
        service_admission=False, truncated=False)
