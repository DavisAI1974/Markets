"""Explicit Kalshi cancellation control composition; acknowledgements never release risk."""
from dataclasses import asdict, dataclass
import hashlib
from pathlib import Path
from .execution_contracts import Contract
from .execution_cancel_contracts import CancelAuthorization, CancelIntent, CancelWire, cancel_path
from .execution_controller import ExecutionController, PreparedExecution, _pin, _validate
from .execution_adapters import (KalshiPin, TransportReceipt, parse_order_response,
    _json_object, _require, _parse_decimal, _units)


CANCEL_SCHEMA_SHA256='f98d25bff30f0aafc93dafc2b7f373d21378225955e57755a17cd84950899b55'

@dataclass(frozen=True)
class PreparedCancellation(Contract):
    control: CancelIntent
    original: PreparedExecution
    target_receipt: TransportReceipt
    authorization_hash: str
    wire: CancelWire


class CancellationController:
    def __init__(self,controller,authorization,*,expected_authorization_hash):
        if type(controller) is not ExecutionController or type(authorization) is not CancelAuthorization:
            raise ValueError('existing controller and typed cancellation authority required')
        self.controller=controller
        self.authorization,self.expected_authorization_hash=authorization,expected_authorization_hash
        try:
            self._authority()
        except BaseException as original:
            controller._stop('cancellation authority invalid',original)
            raise

    def _authority(self):
        c=self.controller
        _pin(c.authority,c.expected_authority_hash)
        _pin(self.authorization,self.expected_authorization_hash)
        reference=Path(__file__).parent/'provenance/kalshi-cancel-order-v2-20260915.md'
        if (self.authorization.schema_hash!=CANCEL_SCHEMA_SHA256
                or hashlib.sha256(reference.read_bytes()).hexdigest()!=CANCEL_SCHEMA_SHA256):
            raise ValueError('cancellation schema differs from pinned official reference bytes')
        if (type(c.pin) is not KalshiPin or self.authorization.account!=c.authority.account
                or self.authorization.authority_hash!=c.authority.digest
                or self.authorization.adapter_hash!=c.pin.digest):
            raise ValueError('cancellation authority differs from original execution authority/account/adapter')

    def prepare(self,control,*,expected_control_hash,original,expected_original_hash,
                target_receipt,expected_target_receipt_hash):
        try:
            return self._prepare(control,expected_control_hash=expected_control_hash,original=original,
                expected_original_hash=expected_original_hash,target_receipt=target_receipt,
                expected_target_receipt_hash=expected_target_receipt_hash)
        except BaseException as error:
            self.controller._stop('cancellation preparation failed',error)
            raise

    def _prepare(self,control,*,expected_control_hash,original,expected_original_hash,
                target_receipt,expected_target_receipt_hash):
        """Retain exact original order receipt; use its provider ID only after parsing."""
        c=self.controller
        self._authority()
        if type(control) is not CancelIntent or type(target_receipt) is not TransportReceipt:
            raise ValueError('typed cancellation control and original target receipt required')
        _pin(control,expected_control_hash)
        c._prepared(original,expected_original_hash)
        c.store.put(dict(kind='cancel_target',value=asdict(target_receipt)))
        _pin(target_receipt,expected_target_receipt_hash)
        target=parse_order_response(target_receipt,intent=original.inputs.intent,wire=original.wire,
            pin=c.pin,expected_source=target_receipt.source)
        if (target.status not in ('ACKNOWLEDGED','PARTIAL') or target.remaining_quantity<=0
                or control.original_intent_id!=original.inputs.intent.intent_id
                or control.original_intent_hash!=original.inputs.intent.digest
                or control.submitted_wire_hash!=original.wire.digest or control.account!=original.inputs.intent.account
                or control.provider_order_id!=target.provider_id or control.client_id!=target.client_id
                or control.target_receipt_hash!=target_receipt.digest
                or control.authorization_hash!=self.authorization.digest):
            raise ValueError('cancel target differs from exact original submitted order evidence')
        if not self.authorization.created_ns <= control.created_ns < control.expires_ns <= self.authorization.expires_ns:
            raise ValueError('control lifetime differs from cancellation authorization')
        state=c.ledger.state(control.original_intent_id)
        if state['wire']!=asdict(original.wire) or state['intent']!=asdict(original.inputs.intent) or state['released']:
            raise ValueError('target is not this ledger unresolved submitted wire')
        wire=CancelWire(control.digest,c.pin.digest,control.account,control.provider_order_id,control.client_id,
            c.pin.ticker,c.pin.subaccount,'DELETE',cancel_path(control.provider_order_id,c.pin.subaccount,c.pin.ticker),b'',
            min(control.expires_ns,target_receipt.received_ns+self.authorization.max_target_age_ns+1))
        prepared=PreparedCancellation(control,original,target_receipt,self.authorization.digest,wire)
        c.store.put(dict(kind='prepared_cancel',value=asdict(prepared)))
        return prepared

    def _ack(self,receipt,prepared,sent_ns):
        wire=prepared.wire
        if (receipt.wire_hash!=wire.digest or receipt.account!=wire.account or receipt.source!='kalshi.cancel_order'
                or receipt.http_status!=200 or receipt.received_ns<sent_ns):
            raise ValueError('cancel response is not an exact acknowledgement envelope')
        body=_json_object(receipt.body,'Kalshi cancel acknowledgement')
        if _require(body,'order_id',str,'cancel')!=wire.provider_order_id:
            raise ValueError('cancel response provider order differs')
        # Provider client_order_id is optional; if supplied, it must echo exactly.
        if 'client_order_id' in body and body['client_order_id']!=wire.client_id:
            raise ValueError('cancel response client order differs')
        reduced=_units(_parse_decimal(_require(body,'reduced_by',str,'cancel'),'reduced_by'),
                       self.controller.pin.quantity_units_per_contract,'reduced_by')
        target=parse_order_response(prepared.target_receipt,intent=prepared.original.inputs.intent,
            wire=prepared.original.wire,pin=self.controller.pin,expected_source=prepared.target_receipt.source)
        event_ns=_require(body,'ts_ms',int,'cancel')*1_000_000
        if not target.event_ns <= event_ns <= receipt.received_ns or reduced>target.remaining_quantity:
            raise ValueError('cancel acknowledgement clocks or quantity differ from target')
        return dict(provider_order_id=wire.provider_order_id,client_id=body.get('client_order_id'),
            reduced_quantity=reduced,event_ns=event_ns,received_ns=receipt.received_ns)

    def dispatch_once(self,prepared,*,expected_prepared_hash,transport,transport_hash,now):
        c=self.controller
        try:
            if type(prepared) is not PreparedCancellation:
                raise ValueError('typed prepared cancellation required')
            _pin(prepared,expected_prepared_hash)
            repeated=self._prepare(prepared.control,expected_control_hash=prepared.control.digest,
                original=prepared.original,expected_original_hash=prepared.original.digest,
                target_receipt=prepared.target_receipt,expected_target_receipt_hash=prepared.control.target_receipt_hash)
            if repeated!=prepared or transport_hash!=self.authorization.transport_hash or not callable(transport) or not callable(now):
                raise ValueError('prepared cancellation or independent transport capability differs')
            clock=now()
            retained=[]
            def sender(wire):
                response=transport(wire)
                if type(response) is not TransportReceipt:
                    raise ValueError('typed cancellation transport envelope required')
                locator=c.store.put(dict(kind='cancel_response',value=asdict(response)))
                _validate(response)
                ack=self._ack(response,prepared,clock)
                retained.append((response,locator,ack))
                return response.body
            c.ledger.cancel_once(control=prepared.control,authorization=self.authorization,wire=prepared.wire,
                target_received_ns=prepared.target_receipt.received_ns,now=clock,sender=sender)
            response,locator,ack=retained[0]
            result=dict(kind='cancel_result',prepared_hash=prepared.digest,response_hash=response.digest,
                receipt_locator=locator,acknowledgement=ack,checkpoint=c.ledger.checkpoint(),
                reservation_release=False)
            result_locator=c.store.put(result)
            return dict(result,result_locator=result_locator)
        except BaseException as original:
            c._stop('cancellation outcome unresolved',original)
            raise
