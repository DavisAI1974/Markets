using CSV,DataFrames,Statistics,JSON3
const BASE=get(ENV,"FAMILY_RESEARCH_DIR","/opt/frankie-box/work/family-research-20261022")
const OUT=joinpath(BASE,"descriptive-v1")
context=CSV.read(joinpath(OUT,"complete_context_measurements.csv"),DataFrame)
samples=CSV.read(joinpath(OUT,"samples.csv"),DataFrame)
lookup=Dict((r.sample_id,r.lag_s,r.feature)=>r.value for r in eachrow(context))
features=sort(unique(context.feature));changes=NamedTuple[]
for s in eachrow(samples)
    s.phase in ["onset","near_before","near_after"] || continue
    endpoint=s.phase=="onset" ? first(split(s.sample_id,":"))*":before_start" : s.sample_id
    for lag in [120,300,600], feature in features
        a=get(lookup,(s.sample_id,lag,feature),missing)
        b=get(lookup,(endpoint,0,feature),missing)
        delta=ismissing(a) || ismissing(b) ? missing : b-a
        push!(changes,(family_id=s.family_id,sample_id=s.sample_id,phase=s.phase,lag_s=lag,feature=feature,change=delta,chronological_quarter=s.chronological_quarter))
    end
end
ch=DataFrame(changes)
CSV.write(joinpath(OUT,"root_native_prestart_changes.csv"),ch)
summary=NamedTuple[]
for g in groupby(ch,[:feature,:lag_s,:phase,:chronological_quarter])
    v=collect(skipmissing(g.change))
    push!(summary,(feature=g.feature[1],lag_s=g.lag_s[1],phase=g.phase[1],chronological_quarter=g.chronological_quarter[1],master_n=nrow(g),available_n=length(v),mean_change=isempty(v) ? missing : mean(v),median_change=isempty(v) ? missing : median(v),positive_n=count(>(0),v),negative_n=count(<(0),v),flat_n=count(==(0),v)))
end
CSV.write(joinpath(OUT,"root_native_prestart_change_summary.csv"),DataFrame(summary))
change_lookup=Dict((r.family_id,r.phase,r.lag_s,r.feature)=>r.change for r in eachrow(ch))
pairs=NamedTuple[]
for g in groupby(ch[ch.phase.=="onset",:],[:feature,:lag_s,:chronological_quarter])
    for control in ["near_before","near_after"]
        vals=Float64[]
        for r in eachrow(g)
            b=get(change_lookup,(r.family_id,control,r.lag_s,r.feature),missing)
            !ismissing(r.change) && !ismissing(b) && push!(vals,r.change-b)
        end
        push!(pairs,(feature=g.feature[1],lag_s=g.lag_s[1],chronological_quarter=g.chronological_quarter[1],control=control,master_n=nrow(g),available_pair_n=length(vals),mean_difference=isempty(vals) ? missing : mean(vals),median_difference=isempty(vals) ? missing : median(vals),positive_n=count(>(0),vals),negative_n=count(<(0),vals),flat_n=count(==(0),vals)))
    end
end
CSV.write(joinpath(OUT,"root_native_nearby_change_summary.csv"),DataFrame(pairs))
# All 13 external concepts also retain their true pre120/before-start changes.
fd=CSV.read(joinpath(OUT,"features.csv"),DataFrame)
external=fd[startswith.(fd.feature,"external."),:]
elookup=Dict((r.sample_id,r.feature)=>r.value for r in eachrow(external))
external_changes=NamedTuple[]
for s in eachrow(samples[samples.phase.=="onset",:]), feature in unique(external.feature)
    prefix=first(split(s.sample_id,":"))
    a=get(elookup,(prefix*":pre120",feature),missing);b=get(elookup,(prefix*":before_start",feature),missing)
    push!(external_changes,(family_id=s.family_id,feature=feature,lag_s=120,change=ismissing(a) || ismissing(b) ? missing : b-a,chronological_quarter=s.chronological_quarter))
end
CSV.write(joinpath(OUT,"external_pre120_changes.csv"),DataFrame(external_changes))
println(JSON3.write(Dict("root_native_feature_count"=>length(features),"root_native_prestart_rows"=>nrow(ch),"nearby_comparisons"=>length(pairs),"external_pre120_rows"=>length(external_changes),"policy"=>"Every family is retained for every feature/lag; unavailable endpoints remain missing; actual onset cohort ends strictly before its first-observed start.")))
