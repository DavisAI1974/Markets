"""All resting orders and FIFO levels from the unchanged authoritative book.

No unknown-ID pruning, derived averages, top-N selection, origin-time guessing,
or masks. An order's observed priority timestamp is preserved as recorded by
the adapter; the full action history establishes whether its origin is known.
"""
def observe_book(book):
    """Copy every authoritative order and level; never return live aliases.

    RestingOrder is a flat dataclass (eight int/str fields), so dict(vars(order)) is exactly
    asdict(order): same keys in field order, same values, a fresh dict. asdict walks every field
    through its recursive deep-copy machinery and was measured at 5 ms per record on the real
    Sunday book; the copy here is the same observation without that walk.
    """
    return dict(instrument_id=book.instrument_id,
                orders=[dict(vars(book.orders[oid])) for oid in sorted(book.orders)],
                levels={side: [dict(price_raw=price, order_ids=list(book.levels[side][price]))
                               for price in sorted(book.levels[side], reverse=side == "B")]
                        for side in ("B", "A")},
                integrity=dict(book.integrity),
                last_sequence=book.last_sequence,
                last_recv_ns=book.last_recv_ns,
                last_event_ns=book.last_event_ns,
                priority_time_semantics="adapter-observed; consult action history for origin")


def order_rank(book, order):
    """Read exact rank from the authoritative current book, without rebuilding it."""
    if order is None:
        return None
    prices = sorted(book.levels[order.side], reverse=order.side == 'B')
    return prices.index(order.price_raw) + 1


# ---- the incremental observation (Greg, 2026-09-22: "we just want time") ---------------------------------------------
# observe_book above is the reference: it copies every order and level and pack() walks every field of every one on every
# closed group, while the adapter mutates ONE order per message. IncrementalObservation keeps each order's and each level's
# canonical fragment (the bytes canonical_tagged_bytes(pack(...)) would give for that node), updates the fragments the
# message touched, and joins them into the observation's bytes. json.dumps is compositional for lists ('[' + ','.join + ']'
# with these separators), so the joined bytes ARE canonical_tagged_bytes(pack(observe_book(book))) when every fragment is
# right; a differential check against that reference runs at the first observation and every `check_every` observations,
# and a mismatch REFUSES (never a wrong body). A reset (or the adapter's one-side clear) rebuilds from the book.
import bisect
try:
    from .c15_journal import pack
    from .verified_journal_reader import canonical_tagged_bytes
except ImportError:
    from c15_journal import pack
    from verified_journal_reader import canonical_tagged_bytes

_SEMANTICS = canonical_tagged_bytes(pack("adapter-observed; consult action history for origin"))


def _order_fragment(order):
    return canonical_tagged_bytes(pack(dict(vars(order))))


def _level_fragment(price, ids):
    return canonical_tagged_bytes(pack(dict(price_raw=price, order_ids=list(ids))))


class IncrementalObservation:
    def __init__(self, book):
        self.book = book
        self.observations = 0          # observations composed for this instrument; the differential check's own count
        self.rebuild()

    def rebuild(self):
        book = self.book
        self.sorted_oids = sorted(book.orders)
        self.order_frag = {oid: (tuple(vars(book.orders[oid]).values()), _order_fragment(book.orders[oid])) for oid in self.sorted_oids}
        self.level_frag = {(side, price): _level_fragment(price, ids)
                           for side in ("B", "A") for price, ids in book.levels[side].items()}

    def note(self, order_id, before, after, side=None, price_raw=None):
        """After the adapter applied one message: `before` = the order's fields before (a mapping or None), `after` = the
        RestingOrder now in the book (or None); the message's own side and price name a level that may have changed."""
        book = self.book
        if after is None:
            if order_id in self.order_frag:
                del self.order_frag[order_id]
                index = bisect.bisect_left(self.sorted_oids, order_id)
                if index >= len(self.sorted_oids) or self.sorted_oids[index] != order_id:
                    raise ValueError('incremental observation differs from the book (order index); refused')
                del self.sorted_oids[index]
        else:
            key = tuple(vars(after).values())
            current = self.order_frag.get(order_id)
            if current is None:
                bisect.insort(self.sorted_oids, order_id)
                self.order_frag[order_id] = (key, _order_fragment(after))
            elif current[0] != key:
                self.order_frag[order_id] = (key, _order_fragment(after))
        touched = set()
        if before is not None:
            touched.add((before['side'], before['price_raw']))
        if after is not None:
            touched.add((after.side, after.price_raw))
        if side in ("B", "A") and price_raw is not None:
            touched.add((side, price_raw))
        for side_, price in touched:
            ids = book.levels[side_].get(price) if side_ in book.levels else None
            if ids:
                self.level_frag[(side_, price)] = _level_fragment(price, ids)
            else:
                self.level_frag.pop((side_, price), None)

    def canonical(self):
        book = self.book
        frag = self.order_frag
        levels = self.level_frag
        parts = [b'["dict",[["instrument_id",', canonical_tagged_bytes(pack(book.instrument_id)),
                 b'],["orders",["list",[', b','.join(frag[oid][1] for oid in self.sorted_oids), b']]],["levels",["dict",[']
        for side in ("B", "A"):
            prices = sorted(book.levels[side], reverse=side == "B")
            parts.append(b'["' + side.encode() + b'",["list",[')
            parts.append(b','.join(levels[(side, price)] for price in prices))
            parts.append(b']]]' + (b',' if side == "B" else b''))
        parts.extend([b']]],["integrity",', canonical_tagged_bytes(pack(dict(book.integrity))),
                      b'],["last_sequence",', canonical_tagged_bytes(pack(book.last_sequence)),
                      b'],["last_recv_ns",', canonical_tagged_bytes(pack(book.last_recv_ns)),
                      b'],["last_event_ns",', canonical_tagged_bytes(pack(book.last_event_ns)),
                      b'],["priority_time_semantics",', _SEMANTICS, b']]]'])
        return b''.join(parts)

    def reference(self):
        return canonical_tagged_bytes(pack(observe_book(self.book)))

    def checked(self):
        composed = self.canonical()
        if composed != self.reference():
            raise ValueError('incremental observation differs from observe_book; refused')
        return composed
