"""Original classroom alignment: exact receive time, stable last same-stamp row."""
function align_external_known(known, times)
    stamps=Int64[k.published_ns for k in known]
    @assert issorted(stamps)
    indices=searchsortedlast.(Ref(stamps),times)
    states=fill(UInt8(1),length(times));values=fill(NaN,length(times))
    for (i,k) in enumerate(indices)
        k==0 && continue
        @assert stamps[k]<=times[i]
        states[i]=UInt8(known[k].state)
        if states[i]==0
            @assert known[k].value!==nothing
            values[i]=Float64(known[k].value)
            @assert isfinite(values[i])
        else
            @assert known[k].value===nothing
        end
    end
    values,states,indices
end
