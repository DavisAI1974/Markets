"""All resting orders and FIFO levels from the unchanged authoritative book.

No unknown-ID pruning, derived averages, top-N selection, origin-time guessing,
or masks. An order's observed priority timestamp is preserved as recorded by
the adapter; the full action history establishes whether its origin is known.
"""
from dataclasses import asdict


def observe_book(book):
    """Copy every authoritative order and level; never return live aliases."""
    return dict(instrument_id=book.instrument_id,
                orders=[asdict(book.orders[oid]) for oid in sorted(book.orders)],
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
