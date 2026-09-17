"""Local, complete per-request chat token admission for the frozen Granite critic."""
import hashlib
import importlib.metadata
from pathlib import Path
import re
import threading

from . import granite_run_artifacts as artifacts
from .granite_runpod_admission import CONTEXT, TOKENIZER_FILES, TOKENIZER_VERSIONS, invocation

MAX_REQUEST_BYTES = 1024 * 1024
REQUEST_FIELDS = {'model', 'messages', 'temperature', 'max_tokens', 'stream', 'chat_template_kwargs'}


class LocalTokenizerAdmission:
    """Verify and load once; measure every exact proxy request without truncation.

    Use ``tokenizer_sha256`` as GraniteIdentity.tokenizer_sha. Its manifest follows
    granite_live_controller.measure_fixture, including the single user role. This
    identity describes tokenizer bytes/configuration, independently of any prompt.
    Injected dependencies are explicitly synthetic and intended only for tests.
    This class neither downloads files nor runs model inference.
    """

    def __init__(self, tokenizer_directory, *, served_model_name, context=CONTEXT,
                 loader=None, version_reader=None, manifest=None):
        if (type(served_model_name) is not str
                or not re.fullmatch('[A-Za-z0-9_.-]{1,100}', served_model_name)
                or type(context) is not int or context != CONTEXT):
            raise ValueError('explicit served model and the supported 131072 service context required')
        self._model = served_model_name
        self._context = context
        self.evidence_class = ('SYNTHETIC_TOKENIZER' if any(
            value is not None for value in (loader, version_reader, manifest)) else 'LOCAL_TOKENIZER_ADMISSION')
        version_reader = version_reader or importlib.metadata.version
        versions = {name: version_reader(name) for name in TOKENIZER_VERSIONS}
        if versions != TOKENIZER_VERSIONS:
            raise ValueError('pinned tokenizer versions required')
        manifest = artifacts.strict_json(artifacts.canonical(manifest)) if manifest is not None else (
            artifacts.strict_json(artifacts.DEFAULT_MANIFEST.read_bytes()))
        artifacts.validate_manifest(manifest)
        directory = Path(tokenizer_directory).absolute()
        if (any(path.is_symlink() for path in (directory, *directory.parents))
                or not directory.is_dir() or {p.name for p in directory.iterdir()} != TOKENIZER_FILES):
            raise ValueError('exact local tokenizer directory required')
        rows = [row for row in manifest['files'] if row['path'] in TOKENIZER_FILES]
        for row in rows:
            artifacts.verify_file(directory / row['path'], row)
        config = artifacts.strict_json((directory / 'config.json').read_bytes())
        limit = config.get('max_position_embeddings') if type(config) is dict else None
        if type(limit) is not int or limit < context:
            raise ValueError('model positional limit must admit selected context')
        # Match the established production identity, not the frozen smoke receipt.
        self._manifest_bytes = artifacts.canonical(dict(schema='GRANITE_TOKENIZER_MANIFEST_V1',
            files=rows, versions=versions, invocation=dict(message_roles=['user'], **invocation())))
        self._tokenizer_sha256 = hashlib.sha256(self._manifest_bytes).hexdigest()
        if loader is None:
            from transformers import AutoTokenizer
            loader = AutoTokenizer.from_pretrained
        self._tokenizer = loader(str(directory), local_files_only=True, trust_remote_code=False)
        # Recheck bytes after loading so a concurrent change cannot silently bind a
        # tokenizer loaded from different files to the verified manifest identity.
        for row in rows:
            artifacts.verify_file(directory / row['path'], row)
        self._lock = threading.Lock()

    @property
    def context(self):
        return self._context

    @property
    def tokenizer_sha256(self):
        return self._tokenizer_sha256

    @property
    def tokenizer_manifest(self):
        return artifacts.strict_json(self._manifest_bytes)

    def __call__(self, body):
        return self._measure(body)[1]

    def with_remaining_output(self, body):
        """Select all remaining context for output with one full prompt measurement.

        Changes only max_tokens; callers must persist the returned exact body and
        admission together. EOS may stop generation before this physical limit.
        """
        if self._context != 131072:
            raise ValueError('remaining output requires the explicit long context')
        return self._measure(body, remaining_output=True)

    def _measure(self, body, *, remaining_output=False):
        if type(body) is not bytes or not body or len(body) > MAX_REQUEST_BYTES:
            raise ValueError('bounded canonical request bytes required')
        try:
            request = artifacts.strict_json(body)
            if type(request) is not dict or set(request) != REQUEST_FIELDS or artifacts.canonical(request) != body:
                raise ValueError()
            messages = request['messages']
            if (request['model'] != self._model
                    or type(request['temperature']) not in (int, float) or request['temperature'] != 0
                    or request['stream'] is not False
                    or type(request['max_tokens']) is not int
                    or not 1 <= request['max_tokens'] <= self._context
                    or type(request['chat_template_kwargs']) is not dict
                    or set(request['chat_template_kwargs']) != {'enable_thinking'}
                    or request['chat_template_kwargs']['enable_thinking'] is not False
                    or type(messages) is not list or len(messages) != 1
                    or type(messages[0]) is not dict or set(messages[0]) != {'role', 'content'}
                    or messages[0]['role'] != 'user' or type(messages[0]['content']) is not str):
                raise ValueError()
        except (ValueError, TypeError, KeyError, OverflowError, RecursionError):
            raise ValueError('request differs from admitted proxy contract') from None
        try:
            with self._lock:
                ids = self._tokenizer.apply_chat_template(messages, **invocation())
        except Exception:
            raise ValueError('local complete chat tokenization failed') from None
        if type(ids) is not list or not ids or any(type(token) is not int or token < 0 for token in ids):
            raise ValueError('complete input and output exceed admitted context or token IDs are invalid')
        if remaining_output:
            request['max_tokens'] = self._context - len(ids)
            body = artifacts.canonical(request)
        if request['max_tokens'] < 1 or len(ids) + request['max_tokens'] > self._context:
            raise ValueError('complete input and output exceed admitted context or token IDs are invalid')
        return body, dict(request_sha256=hashlib.sha256(body).hexdigest(), input_tokens=len(ids),
            output_tokens=request['max_tokens'], context=self._context, tokenizer_sha256=self.tokenizer_sha256)
