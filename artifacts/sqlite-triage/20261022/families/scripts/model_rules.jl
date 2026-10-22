using Statistics
function safe_feature(name)
    occursin(r"(^|\.)(order_id|family_id|instrument_id|channel_id|publisher_id|input_cursor|source_ordinal|sequence|group_index|ts_recv_ns|ts_event_ns|timestamp|target|label|outcome|recognition)(\.|$)",name) && return false
    occursin(r"(start|end|birth|terminal|opened|closed|available|published|known|recv|event)_ns$",name) && !occursin("latency",name) && return false
    !occursin(r"lifecycle\.(candidate|episode|response)\.",name)
end
struct Prep
    columns::Vector{Int}
    masks::Vector{Int}
    medians::Vector{Float64}
    scales::Vector{Float64}
    names::Vector{String}
end
function fitprep(x,names)
    cols=Int[];masks=Int[];meds=Float64[];scales=Float64[];out=String[]
    for j in axes(x,2)
        v=filter(isfinite,x[:,j]);isempty(v) && continue
        m=median(v);s=length(v)>1 ? std(v) : 0.0
        if s>1e-12
            push!(cols,j);push!(meds,m);push!(scales,s);push!(out,names[j])
        end
        if 0<length(v)<size(x,1)
            push!(masks,j)
        end
    end
    append!(out,[names[j]*".__missing" for j in masks])
    Prep(cols,masks,meds,scales,out)
end
function applyprep(p,x)
    z=zeros(size(x,1),length(p.columns)+length(p.masks))
    for (k,j) in enumerate(p.columns),i in axes(x,1)
        z[i,k]=isfinite(x[i,j]) ? clamp((x[i,j]-p.medians[k])/p.scales[k],-20,20) : 0.0
    end
    for (k,j) in enumerate(p.masks),i in axes(x,1)
        z[i,length(p.columns)+k]=!isfinite(x[i,j])
    end
    z
end
crossing_returns(bid,ask,future_bid,future_ask)=(future_bid-ask,bid-future_ask)
function layergroup(n)
    if occursin("external",n)
        for k in ["mos.gw_by_cycle","mos.disagreement_by_cycle","weather","calendar","curve","storage.estimate","storage.weekly","cot.023391"]
            occursin(k,n) && return "external."*k
        end
        for k in ["managed_money_net_pctile_1y","managed_money_net_chg_wow","managed_money_net_pctile_3y","wind_mwh","est_gas_burn"]
            occursin(k,n) && return "external."*k
        end
        return "external.other"
    elseif startswith(n,"lifecycle.")
        return join(split(n,'.')[1:2],'.')
    elseif startswith(n,"second.") || startswith(n,"second_group.")
        return "second_set_scientific_components"
    elseif occursin("pullback",n)
        return "causal_pullback_geometry"
    elseif occursin("activity",n) || occursin("structure",n)
        return "root_native_flow_structure"
    elseif startswith(n,"native.book") || startswith(n,"root.")
        return "root_native_book_depth_queue"
    end
    "native_timing_measurements"
end
