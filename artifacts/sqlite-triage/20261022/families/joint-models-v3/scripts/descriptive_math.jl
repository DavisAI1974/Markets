"""Index of latest observable record, ordered by exact (nanoseconds, cursor)."""
function asof_index(keys, ns::Int64, cursor::Int64=typemax(Int64))
    i=searchsortedlast(keys,(ns,cursor))
    while i>0 && keys[i][2]>cursor
        i-=1
    end
    i
end

"""Descriptive as-of price change within the retained instrument session only."""
function observed_change(times, prices, a::Int64, b::Int64)
    (isempty(times) || a < first(times) || b > last(times) || b < a) && return missing
    i, j = searchsortedlast(times,a), searchsortedlast(times,b)
    (i == 0 || j == 0) && return missing
    prices[j] - prices[i]
end

function component_value(c)
    get(c,"state",nothing) == 0 || return missing
    v=get(c,"value",nothing)
    v isa Real && isfinite(v) ? Float64(v) : missing
end
