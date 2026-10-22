using SQLite, DBInterface, DataFrames, CSV, JSON3, Statistics, Dates
include("descriptive_math.jl")
const BASE = get(ENV,"FAMILY_RESEARCH_DIR","/opt/frankie-box/work/family-research-20261022")
const OUT = joinpath(BASE,"descriptive-v1")
mkpath(OUT)
const db=SQLite.DB(joinpath(BASE,"alignment.sqlite"))
DBInterface.execute(db,"PRAGMA query_only=ON")
query(sql,args=())=DataFrame(DBInterface.execute(db,sql,args))
save(name,rows)=CSV.write(joinpath(OUT,name*".csv"),rows isa DataFrame ? rows : DataFrame(rows))
function unpack(x)
    tag=x[1]
    tag=="dict" && return Dict(String(p[1])=>unpack(p[2]) for p in x[2])
    tag=="float64" && return reinterpret(Float64,parse(UInt64,String(x[2]);base=16))
    tag in ("none","null") && return nothing
    tag in ("list","tuple") && return [unpack(y) for y in x[2]]
    length(x)>1 ? x[2] : nothing
end
num(v)=v isa Real && !(v isa Bool) && isfinite(v) ? Float64(v) : missing
println("Loading exact price clocks and family starts");flush(stdout)
prices=query("SELECT * FROM price_clock ORDER BY instrument_id,available_ns,group_close_input_cursor,source_ordinal")
families=query("SELECT f.*,g.instrument_id FROM family_start f LEFT JOIN group_event g ON g.source_ordinal=f.source_ordinal ORDER BY f.start_recv_ns,f.input_cursor")
save("family_master",families)
save("plane_registry",query("SELECT * FROM plane_registry ORDER BY ordinal"))
save("external_point_provenance",query("SELECT * FROM external_point ORDER BY name"))
save("source_registry",query("SELECT * FROM source_registry"))
save("view_definitions",query("SELECT name,sql FROM sqlite_master WHERE type='view'"))
pricegroups=Dict(g.instrument_id[1]=>g for g in groupby(prices,:instrument_id))
pricekeys=Dict(k=>collect(zip(g.available_ns,g.group_close_input_cursor)) for (k,g) in pricegroups)
function price_at(inst,t,cursor=typemax(Int64))
    haskey(pricegroups,inst) || return (price=missing,age_s=missing,ordinal=missing,ns=missing,cursor=missing)
    g=pricegroups[inst];i=asof_index(pricekeys[inst],t,cursor)
    i==0 && return (price=missing,age_s=missing,ordinal=missing,ns=missing,cursor=missing)
    (price=g.price_raw[i]/1e9,age_s=(t-g.available_ns[i])/1e9,ordinal=g.source_ordinal[i],ns=g.available_ns[i],cursor=g.group_close_input_cursor[i])
end
function change_at(inst,a,b,acursor=typemax(Int64),bcursor=typemax(Int64))
    p,q=price_at(inst,a,acursor),price_at(inst,b,bcursor)
    g=get(pricegroups,inst,nothing)
    edge=g===nothing || a<g.available_ns[1] || b>g.available_ns[end]
    d=edge || ismissing(p.price) || ismissing(q.price) ? missing : q.price-p.price
    (change=d,from_age_s=p.age_s,to_age_s=q.age_s,from_ordinal=p.ordinal,to_ordinal=q.ordinal,edge_censored=edge)
end
unit_errors=count(abs.(prices.price .- prices.price_raw./1e9).>1e-12)
@assert unit_errors==0
samples=NamedTuple[];windows=NamedTuple[];features=NamedTuple[];contexts=NamedTuple[]
const NS=Int64(1_000_000_000)
function addfeature(sample,name,value;state=missing,reason="",age=missing,source="",ref=missing)
    push!(features,(sample_id=sample,feature=name,value=num(value),state=state,reason=reason,age_s=age,source=source,source_ref=ref))
end
function extract_frame(sample,packed,age)
    ismissing(packed) && return
    # Decode selected branches only; never consume identifiers, state labels, or teacher knowledge.
    f=Dict(String(p[1])=>p[2] for p in JSON3.read(packed)[2])
    for k in ["best_bid","best_ask","mid","spread","depth_imbalance_n","depth_imbalance_full","bid_depth_full","ask_depth_full","bid_order_count_full","ask_order_count_full","bid_price_level_count_full","ask_price_level_count_full"]
        haskey(f,k) && addfeature(sample,"root."*k,unpack(f[k]);age=age,source="root")
    end
    if haskey(f,"best_bid") && haskey(f,"best_ask") && haskey(f,"spread")
        bid,ask,spread=unpack(f["best_bid"]),unpack(f["best_ask"]),unpack(f["spread"])
        if all(x->x isa Real,[bid,ask,spread])
            @assert abs((ask-bid)-spread)<1e-10
        end
    end
    if haskey(f,"activity")
        for (w,a) in unpack(f["activity"]), k in ["event_count","trade_aggressor_imbalance","add_cancel_churn","trade_buy_aggressor_qty","trade_sell_aggressor_qty","top_level_add_qty_derived","top_level_cancel_qty_derived","priority_lost_modify_count","missing_reference_count"]
            haskey(a,k) && addfeature(sample,"root.activity."*w*"."*k,a[k];age=age,source="root")
        end
    end
end
println("Analyzing elapsed-time paths, nearby periods, and second-set dispositions");flush(stdout)
for (rank,f) in enumerate(eachrow(families))
    inst,t,fc=f.instrument_id,f.start_recv_ns,f.input_cursor
    quarter=clamp(fld(4*(t-families.start_recv_ns[1]),families.start_recv_ns[end]-families.start_recv_ns[1]+1)+1,1,4)
    for (phase,delta) in [("pre120",-120),("before_start",0),("onset",0),("near_before",-600),("near_after",600)]
        cutoff=t+delta*NS-(phase=="before_start" ? 1 : 0)
        cap=phase=="before_start" ? fc-1 : phase=="onset" ? fc : typemax(Int64)
        sid=string(rank,":",phase);p=price_at(inst,cutoff,cap)
        pre_end=phase=="onset" ? cutoff-1 : cutoff
        pre_cap=phase=="onset" ? cap-1 : cap
        pre=change_at(inst,cutoff-120NS,pre_end,typemax(Int64),pre_cap)
        direction=ismissing(pre.change) ? "missing" : pre.change>1e-12 ? "up" : pre.change< -1e-12 ? "down" : "flat"
        push!(samples,(sample_id=sid,family_id=f.family_id,phase=phase,instrument_id=inst,cutoff_ns=cutoff,cursor_cap=cap,chronological_quarter=quarter,price=p.price,price_age_s=p.age_s,price_source_ordinal=p.ordinal,pre120_change=pre.change,pre_direction=direction))
        # Same-instrument, two-clock eligibility; exact native cursor limits apply at onset.
        s=query("SELECT source_offset,input_cursor,known_by_ns,event_ns,receive_ns,raw_components_json,coverage_json FROM second_set_clock WHERE known_by_ns<=? AND input_cursor<=? AND instrument_id=? ORDER BY known_by_ns DESC,input_cursor DESC LIMIT 1",(cutoff,cap,inst))
        if nrow(s)>0
            r=s[1,:];age=(cutoff-r.known_by_ns)/1e9
            @assert r.known_by_ns<=cutoff && r.input_cursor<=cap
            for (key,c) in pairs(JSON3.read(r.raw_components_json))
                addfeature(sid,"second."*String(key),component_value(c);state=get(c,"state",missing),reason=String(get(c,"reason","")),age=age,source="confirmed_second_set",ref=r.source_offset)
            end
            push!(contexts,(sample_id=sid,source="second_set",ref=r.source_offset,known_by_ns=r.known_by_ns,event_ns=r.event_ns,receive_ns=r.receive_ns,input_cursor=r.input_cursor,age_s=age,coverage=r.coverage_json))
        end
        if phase in ["onset","before_start","pre120"]
            if phase=="onset"
                r=query("SELECT root_frame_packed_json FROM anchor_context WHERE family_id=?",(f.family_id,))
                extract_frame(sid,r.root_frame_packed_json[1],0.0)
            else
                point=phase=="pre120" ? "window_open" : "before_start"
                r=query("SELECT * FROM prebirth_context WHERE family_id=? AND point=?",(f.family_id,point))
                if nrow(r)>0 && !ismissing(r.record_recv_ns[1]) && r.record_recv_ns[1]<=cutoff && r.input_cursor[1]<=cap
                    extract_frame(sid,r.root_frame_packed_json[1],(cutoff-r.record_recv_ns[1])/1e9)
                end
            end
        end
        if phase in ["onset","near_before","near_after"]
            for h in [1,5,20,60,120,300,600,1800,3600]
                d=change_at(inst,cutoff,cutoff+h*NS,cap)
                prior=change_at(inst,cutoff-h*NS,pre_end,typemax(Int64),pre_cap)
                earlier=change_at(inst,cutoff-2h*NS,cutoff-h*NS)
                push!(windows,merge((sample_id=sid,family_id=f.family_id,phase=phase,instrument_id=inst,horizon_s=h,chronological_quarter=quarter,pre_direction=direction,pre120_change=pre.change,prior_equal_h_change=prior.change,earlier_equal_h_change=earlier.change),d))
            end
        end
    end
    rank%100==0 && (println("families ",rank);flush(stdout))
end
save("samples",samples);save("elapsed_windows",windows);save("second_set_context_receipts",contexts)
println("Joining all 13 external points with separate series and publication provenance");flush(stdout)
# Preserve dimensions explicitly. Absolute dates/clocks remain provenance, never predictors.
dimensions=Dict("mos.gw_by_cycle"=>["model","horizon_days","target_day"],"weather.obs_hourly"=>["station"],"curve.settled_shape"=>["front_symbol","next_symbol","back_rank"],"curve.traded_shape"=>["front_symbol","next_symbol","back_rank"])
fields=Dict("cot.023651"=>["managed_money_net_pctile_1y","managed_money_net_chg_wow","managed_money_net_pctile_3y"],"cot.023391"=>["managed_money_net_pctile_1y"],"mos.gw_by_cycle"=>["gw_hdd","gw_cdd","coverage"],"eia930.us48"=>["wind_mwh","est_gas_burn_bcfd_rate"],"calendar.sessions_since_prompt_expiry"=>["sessions_since_prompt_expiry"],"mos.disagreement_by_cycle"=>["max_abs_spread_gw_hdd"],"weather.gw_daily"=>["gw_hdd","gw_cdd","coverage"],"weather.obs_hourly"=>["tmpf","dwpf","sknt"],"storage.weekly"=>["level_bcf","weekly_chg_bcf","vs_5yr_bcf"],"storage.estimate"=>["estimate_bcf","actual_bcf","surprise_bcf"],"curve.settled_shape"=>["slope_1","slope_back","curvature","front_next_spread"],"curve.traded_shape"=>["slope_1","slope_back","curvature","front_next_spread"])
ext=query("SELECT * FROM external_row ORDER BY published_ns,source_ordinal")
series=Dict{String,Vector{Int}}();objects=Dict{Int,Any}()
for (i,r) in enumerate(eachrow(ext))
    haskey(fields,r.point_name) || continue
    j=JSON3.read(r.row_json);objects[i]=j
    dims=get(dimensions,r.point_name,String[])
    key=r.point_name*"|"*join([d*"="*string(get(j,d,nothing)) for d in dims],"|")
    push!(get!(series,key,Int[]),i)
end
external_links=NamedTuple[]
for (key,idx) in sort(collect(series);by=first)
    times=ext.published_ns[idx]
    for sample in samples
        # No source cursor is available for external publications: strictly earlier ns only.
        k=searchsortedlast(times,sample.cutoff_ns-1)
        row=k==0 ? nothing : ext[idx[k],:]
        push!(external_links,(sample_id=sample.sample_id,series=key,point_name=k==0 ? ext.point_name[idx[1]] : row.point_name,source_ordinal=k==0 ? missing : row.source_ordinal,published_ns=k==0 ? missing : row.published_ns,event_time_ns=k==0 ? missing : row.event_time_ns,publication_age_s=k==0 ? missing : (sample.cutoff_ns-row.published_ns)/1e9,source_row_json=k==0 ? "" : row.row_json))
        point=ext.point_name[idx[1]]
        for field in fields[point]
            value=k==0 ? nothing : get(objects[idx[k]],field,nothing)
            # Weather source uses 'M' strings. Parse only documented numeric measurements.
            value isa AbstractString && (value=tryparse(Float64,value))
            addfeature(sample.sample_id,"external."*key*"."*field,value;age=k==0 ? missing : (sample.cutoff_ns-row.published_ns)/1e9,source=point,ref=k==0 ? missing : row.source_ordinal,reason=k==0 ? "no prior publication" : value===nothing ? "source missing" : "")
        end
    end
end
save("external_asof",external_links);save("features",features)
println("Summarizing both directions, flat evidence, stability, and stale-price sensitivity");flush(stdout)
w=DataFrame(windows);summaries=NamedTuple[]
for g in groupby(w,[:phase,:instrument_id,:horizon_s,:pre_direction,:chronological_quarter])
    for maxage in [Inf,5.0,30.0,120.0]
        valid=[i for i in 1:nrow(g) if !ismissing(g.change[i]) && g.from_age_s[i]<=maxage && g.to_age_s[i]<=maxage]
        vals=Float64[g.change[i] for i in valid]
        signed=Float64[sign(g.pre120_change[i])*g.change[i] for i in valid if !ismissing(g.pre120_change[i]) && abs(g.pre120_change[i])>1e-12]
        decel=[i for i in valid if !ismissing(g.prior_equal_h_change[i]) && !ismissing(g.earlier_equal_h_change[i]) && abs(g.earlier_equal_h_change[i])>1e-12]
        push!(summaries,(phase=g.phase[1],instrument_id=g.instrument_id[1],horizon_s=g.horizon_s[1],pre_direction=g.pre_direction[1],chronological_quarter=g.chronological_quarter[1],max_price_age_s=maxage,master_n=nrow(g),available_n=length(vals),edge_censored_n=count(g.edge_censored),up_n=count(>(1e-12),vals),down_n=count(<(-1e-12),vals),flat_n=count(x->abs(x)<=1e-12,vals),mean_change=isempty(vals) ? missing : mean(vals),median_change=isempty(vals) ? missing : median(vals),signed_pair_n=length(signed),mean_signed_change=isempty(signed) ? missing : mean(signed),continuation_n=count(>(1e-12),signed),reversal_n=count(<(-1e-12),signed),deceleration_pair_n=length(decel),deceleration_n=count(i->sign(g.prior_equal_h_change[i])==sign(g.earlier_equal_h_change[i]) && abs(g.prior_equal_h_change[i])<abs(g.earlier_equal_h_change[i]),decel)))
    end
end
save("direction_summary",summaries)
# Paired nearby changes are descriptive controls, possibly contaminated by other starts.
paired=NamedTuple[]
for g in groupby(w,[:family_id,:horizon_s])
    a=g[g.phase.=="onset",:]
    for phase in ["near_before","near_after"]
        b=g[g.phase.==phase,:]
        nrow(a)==1 && nrow(b)==1 || continue
        d=ismissing(a.change[1]) || ismissing(b.change[1]) ? missing : a.change[1]-b.change[1]
        push!(paired,(family_id=g.family_id[1],horizon_s=g.horizon_s[1],control_phase=phase,change_difference=d,onset_change=a.change[1],control_change=b.change[1],onset_age_s=a.to_age_s[1],control_age_s=b.to_age_s[1]))
    end
end
save("nearby_price_pairs",paired)
fd=DataFrame(features);sd=DataFrame(samples)
profile=NamedTuple[]
for g in groupby(fd,:feature)
    v=collect(skipmissing(g.value));ages=collect(skipmissing(g.age_s))
    push!(profile,(feature=g.feature[1],master_n=nrow(g),available_n=length(v),missing_n=count(ismissing,g.value),distinct_n=length(unique(v)),min=isempty(v) ? missing : minimum(v),max=isempty(v) ? missing : maximum(v),median_age_s=isempty(ages) ? missing : median(ages),max_age_s=isempty(ages) ? missing : maximum(ages)))
end
save("feature_availability",profile)
# Retained sequence is never truncated to an outcome horizon. All groups stay linked.
println("Saving complete retained group sequence with exact second-set links");flush(stdout)
save("retained_group_sequence",query("SELECT g.*,c.source_offset,c.known_by_ns,c.coverage_json FROM group_event g LEFT JOIN second_set_clock c ON c.input_cursor=g.input_cursor AND c.instrument_id=g.instrument_id ORDER BY g.recv_ns,g.input_cursor"))
cp(joinpath(BASE,"julia-env","Project.toml"),joinpath(OUT,"Project.toml");force=true)
cp(joinpath(BASE,"julia-env","Manifest.toml"),joinpath(OUT,"Manifest.toml");force=true)
receipt=Dict("checkpoint"=>"ac1040dbf174c9a1184ef2ec81633d54687d02e2","family_count"=>nrow(families),"sample_count"=>length(samples),"elapsed_windows"=>length(windows),"feature_rows"=>length(features),"external_series"=>length(series),"external_links"=>length(external_links),"price_unit_errors"=>unit_errors,"analysis"=>"descriptive; no model, predictor selection, backtest, or causal claim","source_database"=>joinpath(BASE,"alignment.sqlite"),"source_sha256_from_completed_handoff"=>"e16f8d6bb6a95b6eceff86be81b6942ef755a91b9e4b6ae36f88e49a080f0429","external_publication_policy"=>"strictly earlier ns; nominal/rule-based provenance preserved in external_point_provenance","price_policy"=>"same instrument, exact ns/cursor as-of endpoints, age retained, outside retained price bounds missing","limitation"=>"one retained market day; overlapping windows and nearby controls are dependent; no significance claims; 99 registry roles retained, not 99 numerical predictors; only documented numeric source fields summarized")
open(joinpath(OUT,"run_receipt.json"),"w") do io;JSON3.write(io,receipt);end
println(JSON3.write(receipt));flush(stdout)
