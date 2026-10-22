using SQLite,DBInterface,DataFrames,CSV,JSON3
include("descriptive_math.jl")
const BASE=get(ENV,"FAMILY_RESEARCH_DIR","/opt/frankie-box/work/family-research-20261022")
const OUT=joinpath(BASE,"descriptive-v1")
db=SQLite.DB(joinpath(BASE,"alignment.sqlite"));DBInterface.execute(db,"PRAGMA query_only=ON")
samples=CSV.read(joinpath(OUT,"samples.csv"),DataFrame)
features=NamedTuple[];extended=NamedTuple[];receipts=NamedTuple[]
for s in eachrow(samples)
    lags=s.phase in ["onset","near_before","near_after"] ? [0,120,300,600] : [0]
    for lag in lags
        cutoff=s.cutoff_ns-lag*Int64(1_000_000_000)
        cap=lag==0 ? s.cursor_cap : typemax(Int64)
        r=DataFrame(DBInterface.execute(db,"SELECT g.source_ordinal,g.input_cursor,g.recv_ns,g.event_ns,c.source_offset,c.known_by_ns,c.raw_components_json,c.coverage_json FROM group_event g JOIN second_set_clock c ON c.input_cursor=g.input_cursor AND c.instrument_id=g.instrument_id WHERE g.recv_ns<=? AND g.input_cursor<=? AND g.instrument_id=? AND c.known_by_ns<=? ORDER BY g.recv_ns DESC,g.input_cursor DESC LIMIT 1",(cutoff,cap,s.instrument_id,cutoff)))
        nrow(r)==0 && continue
        x=r[1,:];age=(cutoff-x.known_by_ns)/1e9
        @assert x.known_by_ns<=cutoff && x.input_cursor<=cap
        push!(receipts,(sample_id=s.sample_id,lag_s=lag,cutoff_ns=cutoff,source_ordinal=x.source_ordinal,input_cursor=x.input_cursor,event_ns=x.event_ns,receive_ns=x.recv_ns,known_by_ns=x.known_by_ns,source_offset=x.source_offset,age_s=age,coverage_json=x.coverage_json))
        for (k,c) in pairs(JSON3.read(x.raw_components_json))
            name="second_group."*String(k)
            if lag==0
                push!(features,(sample_id=s.sample_id,feature=name,value=component_value(c),state=get(c,"state",missing),reason=String(get(c,"reason","")),age_s=age,source="confirmed_second_set_last_completed_group",source_ref=x.source_offset))
            else
                push!(extended,(sample_id=s.sample_id,lag_s=lag,cutoff_ns=cutoff,feature=name,value=component_value(c),state=get(c,"state",missing),reason=String(get(c,"reason","")),age_s=age,source_ref=x.source_offset))
            end
        end
    end
end
CSV.write(joinpath(OUT,"group_measurements.csv"),DataFrame(features))
CSV.write(joinpath(OUT,"extended_group_measurements.csv"),DataFrame(extended))
CSV.write(joinpath(OUT,"group_context_receipts.csv"),DataFrame(receipts))
println(JSON3.write(Dict("group_measurement_rows"=>length(features),"extended_group_measurement_rows"=>length(extended),"source_receipts"=>length(receipts),"policy"=>"Actual latest completed group, same instrument, no later than cutoff/cursor; source age and event disposition retained. These are separate historical observations, not imputed current-event values.")))
