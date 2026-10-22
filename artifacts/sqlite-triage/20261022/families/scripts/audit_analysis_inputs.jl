# Inventory input availability only; no price associations or model fitting.
using CSV,DataFrames,JSON3,SQLite,DBInterface,Statistics
const BASE=get(ENV,"FAMILY_RESEARCH_DIR","/opt/frankie-box/work/family-research-20261022")
const OUT=joinpath(BASE,"descriptive-v1")
load(name)=CSV.read(joinpath(OUT,name*".csv"),DataFrame)
save(name,rows)=CSV.write(joinpath(OUT,name*".csv"),rows isa DataFrame ? rows : DataFrame(rows))
samples=load("samples");fd=load("features");group=load("group_measurements");complete=load("complete_context_measurements");external=load("external_asof")
phasecount=Dict(String(g.phase[1])=>nrow(g) for g in groupby(samples,:phase))
samplemap=Dict(r.sample_id=>r for r in eachrow(samples))
second=leftjoin(vcat(fd[startswith.(fd.feature,"second."),:],group;cols=:union),select(samples,:sample_id,:phase);on=:sample_id)
secondstates=combine(groupby(second,[:feature,:phase,:state,:reason]),nrow=>:rows)
save("input_second_set_dispositions",secondstates)
availability=NamedTuple[]
for g in groupby(second,[:feature,:phase])
    vals=collect(skipmissing(g.value));ages=collect(skipmissing(g.age_s))
    push!(availability,(feature=g.feature[1],phase=g.phase[1],master_n=phasecount[g.phase[1]],available_n=length(vals),missing_n=phasecount[g.phase[1]]-length(vals),source_rows=nrow(g),median_observation_age_s=isempty(ages) ? missing : median(ages),max_observation_age_s=isempty(ages) ? missing : maximum(ages)))
end
save("input_second_set_availability",availability)
extmissing=NamedTuple[]
extjoined=leftjoin(fd[startswith.(fd.feature,"external."),:],select(samples,:sample_id,:phase);on=:sample_id)
for g in groupby(extjoined,[:feature,:phase])
    ages=collect(skipmissing(g.age_s));n=count(!ismissing,g.value)
    push!(extmissing,(feature=g.feature[1],phase=g.phase[1],master_n=phasecount[g.phase[1]],available_n=n,missing_n=phasecount[g.phase[1]]-n,no_prior_publication_n=count(i->ismissing(g.source_ref[i]),1:nrow(g)),source_value_missing_n=count(i->!ismissing(g.source_ref[i]) && ismissing(g.value[i]),1:nrow(g)),median_publication_age_s=isempty(ages) ? missing : median(ages)))
end
save("input_external_missingness",extmissing)
extseries=leftjoin(external,select(samples,:sample_id,:phase);on=:sample_id)
save("input_external_series_availability",combine(groupby(extseries,[:point_name,:series,:phase]),nrow=>:master_n,:source_ordinal=>(x->count(ismissing,x))=>:no_prior_publication_n))
# Missing feature keys are not silently converted to zero. Master denominators include every context.
complete.phase=[samplemap[sid].phase for sid in complete.sample_id]
cp=NamedTuple[]
receipt=load("group_context_receipts")
receipt.phase=[samplemap[sid].phase for sid in receipt.sample_id]
expectedcounts=Dict((g.phase[1],g.lag_s[1])=>nrow(g) for g in groupby(receipt,[:phase,:lag_s]))
for g in groupby(complete,[:feature,:phase,:lag_s])
    expected=expectedcounts[(g.phase[1],g.lag_s[1])]
    n=count(!ismissing,g.value);ages=collect(skipmissing(g.age_s))
    push!(cp,(feature=g.feature[1],phase=g.phase[1],lag_s=g.lag_s[1],master_n=expected,source_key_n=nrow(g),available_n=n,explicit_null_n=count(ismissing,g.value),unmaterialized_key_n=expected-nrow(g),median_observation_age_s=isempty(ages) ? missing : median(ages)))
end
save("input_root_native_missingness",cp)
save("input_snapshot_price_availability",combine(groupby(samples,:phase),nrow=>:master_n,:price=>(x->count(ismissing,x))=>:no_prior_trade_n,:price_age_s=>(x->count(v->!ismissing(v) && v>5,x))=>:age_over_5s_n,:price_age_s=>(x->count(v->!ismissing(v) && v>120,x))=>:age_over_120s_n))
windows=load("elapsed_windows")
save("input_price_window_coverage",combine(groupby(windows,[:phase,:horizon_s]),nrow=>:master_n,:edge_censored=>sum=>:edge_censored_n,:change=>(x->count(ismissing,x))=>:unavailable_change_n))
db=SQLite.DB(joinpath(BASE,"alignment.sqlite"));DBInterface.execute(db,"PRAGMA query_only=ON")
roles=DataFrame(DBInterface.execute(db,raw"SELECT ordinal,entry_id,json_extract(body,'$.class') class,json_extract(body,'$.disposition') disposition,json_extract(body,'$.reason') reason FROM plane_registry ORDER BY ordinal"))
save("input_plane_role_inventory",roles)
summary=Dict("families_retained"=>749,"prestart_contexts_already_saved"=>1498,"timestamped_trades_already_verified"=>30739,"plane_registry_entries"=>nrow(roles),"conceptual_external_points"=>13,"aligned_external_series"=>length(unique(external.series)),"snapshot_contexts"=>nrow(samples),"indexed_root_native_contexts_added"=>nrow(receipt),"root_native_measurement_rows_added"=>nrow(complete),"completed_group_second_set_measurement_rows_added"=>nrow(group),"input_inventory_only"=>true,"rerun_status"=>"paused at user request pending disclosure of remaining gaps","unrecoverable_or_ineligible_categories"=>["source-defined measurement states, including NO_FLOW, SIDE_UNDEFINED, NOT_F_LAST and other recorded reasons","explicit null or unmaterialized measurement keys in the pinned payload","external observation absent or not yet published at cutoff; no future backfill","price endpoint before first or after last retained trade, or stale observation age","registry roles whose disposition is control/identity/not-read rather than a numerical measurement"],"retention_policy"=>"No family, trade, day, or source row is rejected because a measurement is missing. Original source database and payloads remain pinned.")
open(joinpath(OUT,"input_completeness_receipt.json"),"w") do io;JSON3.write(io,summary);end
println(JSON3.write(summary))
for phase in ["before_start","onset"]
    println("SECOND SET ",phase)
    show(stdout,MIME("text/plain"),DataFrame(availability)[[r.phase==phase for r in availability],:]);println()
end
println("EXTERNAL BEFORE START GAPS")
ee=DataFrame(extmissing);ee=ee[(ee.phase.=="before_start").&(ee.missing_n.>0),:]
show(stdout,MIME("text/plain"),ee);println();flush(stdout)
