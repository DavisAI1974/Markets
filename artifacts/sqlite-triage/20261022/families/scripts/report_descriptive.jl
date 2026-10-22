using SQLite, DBInterface, CSV, DataFrames, JSON3, Statistics
include("descriptive_math.jl")
const BASE=get(ENV,"FAMILY_RESEARCH_DIR","/opt/frankie-box/work/family-research-20261022")
const OUT=joinpath(BASE,"descriptive-v1")
load(name)=CSV.read(joinpath(OUT,name*".csv"),DataFrame)
save(name,rows)=CSV.write(joinpath(OUT,name*".csv"),rows isa DataFrame ? rows : DataFrame(rows))
db=SQLite.DB(joinpath(BASE,"alignment.sqlite"));DBInterface.execute(db,"PRAGMA query_only=ON")
q(sql)=DataFrame(DBInterface.execute(db,sql))
samples=load("samples");w=load("elapsed_windows");fd=load("features")
append!(fd,load("group_measurements");promote=true)
weather=load("external_last_observed_measurements")
append!(fd,DataFrame(sample_id=weather.sample_id,feature=weather.feature,value=weather.value,state=fill(missing,nrow(weather)),reason=weather.disposition,age_s=weather.publication_age_s,source=fill("published_station_measurement_history",nrow(weather)),source_ref=weather.source_ordinal);promote=true)
geometry=load("pullback_measurements");geometry=geometry[geometry.lag_s.==0,:]
append!(fd,DataFrame(sample_id=geometry.sample_id,feature=geometry.feature,value=geometry.value,state=geometry.state,reason=geometry.reason,age_s=geometry.age_s,source=fill("stored_causal_pullback_geometry",nrow(geometry)),source_ref=geometry.source_ref);promote=true)
complete=load("complete_context_measurements");basecomplete=complete[complete.lag_s.==0,:]
fd=fd[.!startswith.(fd.feature,"root."),:]
append!(fd,DataFrame(sample_id=basecomplete.sample_id,feature=basecomplete.feature,value=basecomplete.value,state=fill(missing,nrow(basecomplete)),reason=fill("",nrow(basecomplete)),age_s=basecomplete.age_s,source=fill("indexed_root_native_group_context",nrow(basecomplete)),source_ref=basecomplete.source_ordinal);promote=true)
pc=q("SELECT * FROM price_clock ORDER BY instrument_id,available_ns,group_close_input_cursor,source_ordinal")
pg=Dict(g.instrument_id[1]=>g for g in groupby(pc,:instrument_id))
diagnostics=NamedTuple[]
for s in eachrow(samples)
    g=pg[s.instrument_id];keys=collect(zip(g.available_ns,g.group_close_input_cursor))
    pre_end=s.phase=="onset" ? s.cutoff_ns-1 : s.cutoff_ns
    pre_cap=s.phase=="onset" ? s.cursor_cap-1 : s.cursor_cap
    i=asof_index(keys,s.cutoff_ns-120_000_000_000);j=asof_index(keys,pre_end,pre_cap)
    push!(diagnostics,(sample_id=s.sample_id,pre_from_age_s=i==0 ? missing : (s.cutoff_ns-120_000_000_000-g.available_ns[i])/1e9,pre_to_age_s=j==0 ? missing : (pre_end-g.available_ns[j])/1e9,pre_from_ordinal=i==0 ? missing : g.source_ordinal[i],pre_to_ordinal=j==0 ? missing : g.source_ordinal[j],trades_in_pre120=j-i,pre_left_censored=i==0))
end
save("prior_price_diagnostics",diagnostics)
diag=Dict(r.sample_id=>r for r in diagnostics)
direction=NamedTuple[]
for g in groupby(w,[:phase,:horizon_s,:pre_direction])
    for sensitivity in ["future_endpoints_fresh","pre_and_future_endpoints_fresh"]
        valid=[i for i in 1:nrow(g) if !ismissing(g.change[i]) && g.from_age_s[i]<=5 && g.to_age_s[i]<=5 && (sensitivity=="future_endpoints_fresh" || (!ismissing(diag[g.sample_id[i]].pre_from_age_s) && diag[g.sample_id[i]].pre_from_age_s<=5 && diag[g.sample_id[i]].pre_to_age_s<=5))]
        vals=Float64[g.change[i] for i in valid]
        signed=Float64[sign(g.pre120_change[i])*g.change[i] for i in valid if !ismissing(g.pre120_change[i]) && abs(g.pre120_change[i])>1e-12]
        push!(direction,(phase=g.phase[1],horizon_s=g.horizon_s[1],pre_direction=g.pre_direction[1],sensitivity=sensitivity,master_n=nrow(g),available_n=length(vals),mean_change=isempty(vals) ? missing : mean(vals),median_change=isempty(vals) ? missing : median(vals),up_n=count(>(1e-12),vals),down_n=count(<(-1e-12),vals),flat_n=count(x->abs(x)<=1e-12,vals),signed_pair_n=length(signed),mean_signed_change=isempty(signed) ? missing : mean(signed)))
    end
end
save("direction_freshness_sensitivity",direction)
availability=NamedTuple[]
for g in groupby(leftjoin(fd,select(samples,:sample_id,:phase);on=:sample_id),[:feature,:phase])
    v=collect(skipmissing(g.value));ages=collect(skipmissing(g.age_s))
    master=count(==(g.phase[1]),samples.phase)
    push!(availability,(feature=g.feature[1],phase=g.phase[1],master_n=master,available_n=length(v),missing_n=master-length(v),distinct_n=length(unique(v)),median_age_s=isempty(ages) ? missing : median(ages),age_over_120s_n=count(>(120),ages),age_over_day_n=count(>(86400),ages)))
end
save("feature_phase_availability",availability)
# Source-wide dispositions describe which fields exist, not just the selected snapshots.
dispositions=q(raw"SELECT j.key AS component,json_extract(j.value,'$.state') AS state,json_extract(j.value,'$.reason') AS reason,count(*) AS rows FROM second_set_clock s,json_each(s.raw_components_json) j GROUP BY 1,2,3")
save("all_second_set_component_dispositions",dispositions)
roles=q(raw"SELECT json_extract(body,'$.disposition') disposition,count(*) entries FROM plane_registry GROUP BY 1")
save("plane_disposition_summary",roles)
pd=load("nearby_price_pairs");near=NamedTuple[]
for g in groupby(pd,[:horizon_s,:control_phase])
    v=collect(skipmissing(g.change_difference))
    push!(near,(horizon_s=g.horizon_s[1],control_phase=g.control_phase[1],master_n=nrow(g),available_n=length(v),mean_difference=isempty(v) ? missing : mean(v),median_difference=isempty(v) ? missing : median(v)))
end
save("nearby_price_summary",near)
overlap=load("overlap_counts");over=combine(groupby(overlap,:horizon_s),:other_starts_within_horizon=>mean=>:mean_other_starts,:other_starts_within_horizon=>maximum=>:max_other_starts,:other_starts_within_horizon=>(x->count(>(0),x))=>:starts_with_overlap)
save("overlap_summary",over)
assoc=load("exploratory_associations");stable=NamedTuple[]
for g in groupby(assoc,[:feature,:feature_phase,:horizon_s])
    allrow=g[g.chronological_quarter.==0,:];quarters=g[g.chronological_quarter.>0,:]
    rs=collect(skipmissing(quarters.correlation));nn=quarters.available_pair_n
    push!(stable,(feature=g.feature[1],phase=g.feature_phase[1],horizon_s=g.horizon_s[1],overall_pair_n=allrow.available_pair_n[1],overall_correlation=allrow.correlation[1],quarter_pair_counts=join(nn,"|"),quarter_correlations=join([ismissing(x) ? "missing" : string(x) for x in quarters.correlation],"|"),all_quarters_at_least_30_pairs=length(nn)==4 && minimum(nn)>=30,same_sign_all_quarters=length(rs)==4 && all(sign.(rs).==sign(rs[1]))))
end
save("association_stability",stable)
onset=DataFrame(direction);onset=onset[(onset.phase.=="onset").&(onset.sensitivity.=="pre_and_future_endpoints_fresh"),:]
println("DIRECTION ALL FOUR ENDPOINTS <=5s");show(stdout,MIME("text/plain"),onset);println()
println("NEARBY PRICE COMPARISONS");show(stdout,MIME("text/plain"),DataFrame(near));println()
println("OVERLAP");show(stdout,MIME("text/plain"),over);println()
av=DataFrame(availability);av=av[(av.phase.=="before_start").&startswith.(av.feature,"second."),:]
println("SECOND-SET BEFORE START AVAILABILITY");show(stdout,MIME("text/plain"),av);println()
ss=DataFrame(stable);ss=ss[(ss.phase.=="before_start").&(.!ismissing.(ss.overall_correlation)),:]
ss.abs_correlation=abs.(ss.overall_correlation);sort!(ss,:abs_correlation;rev=true)
println("LARGEST STRICT PRESTART DESCRIPTIVE CORRELATIONS: exploratory, dependent, uncorrected")
show(stdout,MIME("text/plain"),first(ss,12));println()
receipt=Dict("descriptive_association_rows"=>nrow(assoc),"source_component_disposition_rows"=>nrow(dispositions),"plane_roles"=>sum(roles.entries),"all_four_price_endpoint_freshness_s"=>5,"future_price_endpoints_freshness_s"=>5,"multiple_comparison_policy"=>"All computed comparisons saved, including missing/constant; no p-values, selected model, predictive target, significance or tradability claim.","chronology_policy"=>"four equal elapsed-time quarters; availability counts and signs reported separately","dependence_policy"=>"overlap counts retained; nearby controls can include other first-observed starts; no independent-sample inference","prestart_feature_change_policy"=>"onset cohort ends strictly before start; separate contemporaneous onset association rows","source_preservation"=>"alignment.sqlite is read only; complete raw source rows and all offsets remain pinned; numerical analyses cover documented selected measurements, not every byte of all payloads")
open(joinpath(OUT,"analysis_receipt.json"),"w") do io;JSON3.write(io,receipt);end
println(JSON3.write(receipt));flush(stdout)
