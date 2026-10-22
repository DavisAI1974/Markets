# Extract observed geometry; preserve the source completed-step definition.
using CSV,DataFrames,JSON3,SQLite,DBInterface,Statistics
const BASE=get(ENV,"FAMILY_RESEARCH_DIR","/opt/frankie-box/work/family-research-20261022")
const OUT=joinpath(BASE,"descriptive-v1")
contexts=CSV.read(joinpath(OUT,"geometry_contexts.csv"),DataFrame)
samples=CSV.read(joinpath(OUT,"samples.csv"),DataFrame)
samplemap=Dict(r.sample_id=>r for r in eachrow(samples))
function rational_value(v)
    v===nothing && return nothing
    denominator=BigInt(v["denominator"]);@assert denominator>0
    BigInt(v["numerator"])//denominator
end
rows=NamedTuple[];agreements=Ref(0)
for r in eachrow(contexts)
    d=JSON3.read(r.dstate_json);raw=JSON3.read(r.raw_components_json)
    s=d["state"];sample=samplemap[r.sample_id]
    @assert d["cursor"]==r.input_cursor && d["instrument_id"]==sample.instrument_id
    @assert d["ts_recv_ns"]<=r.cutoff_ns && r.known_by_ns<=r.cutoff_ns
    valid=get(raw["unresolved_age_groups_log"],"state",1)==0
    depth=rational_value(get(s,"pull_depth",nothing))
    anchor=get(s,"anchor_dir",nothing)
    active=valid && anchor!==nothing && depth!==nothing
    reason=String(get(raw["unresolved_age_groups_log"],"reason",""))
    push!(rows,(sample_id=r.sample_id,lag_s=r.lag_s,feature="geometry.ongoing_pullback_depth_ticks",value=active ? Float64(depth) : missing,state=active ? 0 : 1,reason=active ? "observed current geometry; distinct from completed-step pullback" : "source geometry frozen or undefined: "*reason,age_s=r.age_s,source_ref=r.source_offset,exact_numerator=depth===nothing ? "" : string(numerator(depth)),exact_denominator=depth===nothing ? "" : string(denominator(depth)),stored_anchor_dir=anchor===nothing ? missing : anchor,chain_broken=Bool(get(s,"broken",false)),armed=Bool(get(s,"armed",false))))
    for (field,sourcefield) in [("last","pullback_ticks_last_log"),("previous","pullback_ticks_prev_log")]
        p=rational_value(get(s,field=="last" ? "p_last" : "p_prev",nothing));c=raw[sourcefield]
        present=get(c,"state",1)==0
        if present
            @assert p!==nothing && abs(log1p(Float64(p))-Float64(c["value"]))<1e-12
            agreements[]+=1
        end
        push!(rows,(sample_id=r.sample_id,lag_s=r.lag_s,feature="geometry.completed_pullback_"*field*"_ticks",value=present ? Float64(p) : missing,state=Int(c["state"]),reason=String(get(c,"reason","")),age_s=r.age_s,source_ref=r.source_offset,exact_numerator=p===nothing ? "" : string(numerator(p)),exact_denominator=p===nothing ? "" : string(denominator(p)),stored_anchor_dir=anchor===nothing ? missing : anchor,chain_broken=Bool(get(s,"broken",false)),armed=Bool(get(s,"armed",false))))
    end
end
df=DataFrame(rows);CSV.write(joinpath(OUT,"pullback_measurements.csv"),df)
joined=leftjoin(df,select(samples,:sample_id,:phase);on=:sample_id)
availability=combine(groupby(joined,[:feature,:phase,:lag_s]),nrow=>:master_n,:value=>(x->count(!ismissing,x))=>:available_n,:value=>(x->count(ismissing,x))=>:missing_n)
CSV.write(joinpath(OUT,"input_pullback_availability.csv"),availability)
dispositions=combine(groupby(joined,[:feature,:phase,:lag_s,:state,:reason]),nrow=>:rows)
CSV.write(joinpath(OUT,"input_pullback_dispositions.csv"),dispositions)
db=SQLite.DB(joinpath(BASE,"alignment.sqlite"));DBInterface.execute(db,"PRAGMA query_only=ON")
groups=DataFrame(DBInterface.execute(db,"SELECT source_ordinal,family_id AS observed_family_id,instrument_id FROM group_event"))
links=leftjoin(CSV.read(joinpath(OUT,"group_context_receipts.csv"),DataFrame),groups;on=:source_ordinal)
links.target_family_id=[samplemap[sid].family_id for sid in links.sample_id]
links.phase=[samplemap[sid].phase for sid in links.sample_id]
links.registry_identities_retained=fill(99,nrow(links));links.conceptual_external_points_retained=fill(13,nrow(links))
CSV.write(joinpath(OUT,"family_context_linkage.csv"),links)
summary=Dict("context_rows"=>nrow(contexts),"pullback_measurement_rows"=>nrow(df),"source_completed_pullback_agreements"=>agreements[],"family_link_rows"=>nrow(links),"distinct_target_families"=>length(unique(links.target_family_id)),"status"=>"input completion only; statistical rerun remains paused","definition"=>"Source completed-step fields unchanged. Added separately named ongoing pullback depth from stored causal D-state. Frozen/undefined anchor states remain missing, never imputed.")
open(joinpath(OUT,"input_pullback_completion_receipt.json"),"w") do io;JSON3.write(io,summary);end
println(JSON3.write(summary))
println("BEFORE START");show(stdout,MIME("text/plain"),availability[(availability.phase.=="before_start").&(availability.lag_s.==0),:]);println();flush(stdout)
