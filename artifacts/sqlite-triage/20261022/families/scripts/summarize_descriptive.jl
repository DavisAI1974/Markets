using SQLite, DBInterface, DataFrames, CSV, JSON3, Statistics
include("descriptive_math.jl")
const BASE=get(ENV,"FAMILY_RESEARCH_DIR","/opt/frankie-box/work/family-research-20261022")
const OUT=joinpath(BASE,"descriptive-v1")
load(name)=CSV.read(joinpath(OUT,name*".csv"),DataFrame)
save(name,rows)=CSV.write(joinpath(OUT,name*".csv"),rows isa DataFrame ? rows : DataFrame(rows))
db=SQLite.DB(joinpath(BASE,"alignment.sqlite"));DBInterface.execute(db,"PRAGMA query_only=ON")
q(sql,args=())=DataFrame(DBInterface.execute(db,sql,args))
samples=load("samples");features=load("features");w=load("elapsed_windows")
append!(features,load("group_measurements");promote=true)
weather=load("external_last_observed_measurements")
append!(features,DataFrame(sample_id=weather.sample_id,feature=weather.feature,value=weather.value,state=fill(missing,nrow(weather)),reason=weather.disposition,age_s=weather.publication_age_s,source=fill("published_station_measurement_history",nrow(weather)),source_ref=weather.source_ordinal);promote=true)
geometry=load("pullback_measurements");geometry=geometry[geometry.lag_s.==0,:]
append!(features,DataFrame(sample_id=geometry.sample_id,feature=geometry.feature,value=geometry.value,state=geometry.state,reason=geometry.reason,age_s=geometry.age_s,source=fill("stored_causal_pullback_geometry",nrow(geometry)),source_ref=geometry.source_ref);promote=true)
complete=load("complete_context_measurements")
basecomplete=complete[complete.lag_s.==0,:]
features=features[.!startswith.(features.feature,"root."),:]
append!(features,DataFrame(sample_id=basecomplete.sample_id,feature=basecomplete.feature,value=basecomplete.value,state=fill(missing,nrow(basecomplete)),reason=fill("",nrow(basecomplete)),age_s=basecomplete.age_s,source=fill("indexed_root_native_group_context",nrow(basecomplete)),source_ref=basecomplete.source_ordinal);promote=true)
const NS=Int64(1_000_000_000)
println("Extending pre-start and nearby second-set comparisons to 5/10 minutes");flush(stdout)
extra=NamedTuple[];native=NamedTuple[];checks=Ref(0)
for s in eachrow(samples)
    if s.phase in ["onset","near_before","near_after"]
        for lag in [120,300,600]
            cutoff=s.cutoff_ns-lag*NS
            r=q("SELECT source_offset,known_by_ns,input_cursor,raw_components_json FROM second_set_clock WHERE known_by_ns<=? AND instrument_id=? ORDER BY known_by_ns DESC,input_cursor DESC LIMIT 1",(cutoff,s.instrument_id))
            nrow(r)==0 && continue
            for (k,c) in pairs(JSON3.read(r.raw_components_json[1]))
                push!(extra,(sample_id=s.sample_id,lag_s=lag,cutoff_ns=cutoff,feature="second."*String(k),value=component_value(c),state=get(c,"state",missing),reason=String(get(c,"reason","")),age_s=(cutoff-r.known_by_ns[1])/1e9,source_ref=r.source_offset[1]))
            end
        end
    end
    if s.phase in ["onset","before_start","pre120"]
        r=s.phase=="onset" ? q("SELECT native_member_json FROM anchor_context WHERE family_id=?",(s.family_id,)) : q("SELECT native_member_json FROM prebirth_context WHERE family_id=? AND point=?",(s.family_id,s.phase=="pre120" ? "window_open" : "before_start"))
        nrow(r)==0 && continue
        j=JSON3.read(r.native_member_json[1]);book=j["book"]
        for side in ["bid_levels","ask_levels"], level in book[side]
            if get(level,"price",nothing) isa Real && get(level,"price_raw",nothing) isa Real
                @assert abs(level["price"]-level["price_raw"]/1e9)<1e-10
                checks[]+=1
            end
        end
        b,a,spread=get(book,"best_bid",nothing),get(book,"best_ask",nothing),get(book,"spread",nothing)
        if all(x->x isa Real,[b,a,spread]);@assert abs(a-b-spread)<1e-10;end
        # Counts and measured flow only. Structural IDs and teacher/state labels are provenance.
        for (anchor,obj) in pairs(j["activity_since"])
            for key in ["elapsed_recv_ns","event_count","trade_aggressor_imbalance","add_cancel_churn","trade_buy_aggressor_qty","trade_sell_aggressor_qty","priority_lost_modify_count","missing_reference_count"]
                v=get(obj,key,nothing)
                v=v isa Real && !(v isa Bool) ? Float64(v) : missing
                push!(native,(sample_id=s.sample_id,feature="native.activity_since."*String(anchor)*"."*key,value=v,anchor_basis=String(get(obj,"anchor_basis","")),side_orientation=String(get(j,"side_orientation",""))))
            end
        end
    end
end
save("extended_second_set",extra);save("native_measurements",native)
ex=DataFrame(extra);append!(ex,load("extended_group_measurements");promote=true);nat=DataFrame(native)
println("Computing exploratory associations with explicit constant/missing results");flush(stdout)
# Reuse eligibility and publication links. Numerical association is descriptive only.
assoc_features=select(features,:sample_id,:feature,:value,:age_s)
# Complete indexed measurements already contain the native flow measurements above.
joined=leftjoin(assoc_features,samples;on=:sample_id,makeunique=true)
phasecounts=Dict(String(p)=>count(==(p),samples.phase) for p in unique(samples.phase))
quartercounts=Dict((String(g.phase[1]),Int(g.chronological_quarter[1]))=>nrow(g) for g in groupby(samples,[:phase,:chronological_quarter]))
windowmap=Dict((r.sample_id,r.horizon_s)=>r for r in eachrow(w))
associations=NamedTuple[]
for g in groupby(joined,[:feature,:phase])
    phase=g.phase[1]
    for horizon in [1,5,20,60,120,300,600,1800,3600], quarter in [0,1,2,3,4]
        xx=Float64[];yy=Float64[];ages=Float64[];total=quarter==0 ? phasecounts[phase] : get(quartercounts,(phase,quarter),0);staleprice=0
        for r in eachrow(g)
            quarter!=0 && r.chronological_quarter!=quarter && continue
            phase_for_outcome=phase in ["pre120","before_start"] ? "onset" : phase
            sid=first(split(r.sample_id,":"))*":"*phase_for_outcome
            v=get(windowmap,(sid,horizon),nothing)
            v===nothing && continue
            ismissing(r.value) || ismissing(v.change) || begin
                if v.from_age_s>5 || v.to_age_s>5
                    staleprice+=1
                else
                    push!(xx,r.value);push!(yy,v.change)
                    !ismissing(r.age_s) && push!(ages,r.age_s)
                end
            end
        end
        reason=length(xx)<3 ? "fewer_than_3_pairs" : length(unique(xx))<2 ? "constant_feature" : length(unique(yy))<2 ? "constant_price_change" : "descriptive_only"
        rho=reason=="descriptive_only" ? cor(xx,yy) : missing
        push!(associations,(feature=g.feature[1],feature_phase=phase,horizon_s=horizon,chronological_quarter=quarter,master_n=total,available_pair_n=length(xx),stale_price_pair_n=staleprice,distinct_feature_n=length(unique(xx)),correlation=rho,disposition=reason,median_feature_age_s=isempty(ages) ? missing : median(ages)))
    end
end
save("exploratory_associations",associations)
# Same feature change over pre120, pre300, pre600 at the event and nearby controls.
deltas=NamedTuple[]
current=Dict((r.sample_id,r.feature)=>r for r in eachrow(features) if startswith(r.feature,"second.") || startswith(r.feature,"second_group."))
samplemap=Dict(r.sample_id=>r for r in eachrow(samples))
for r in eachrow(ex)
    s=samplemap[r.sample_id]
    endpoint=s.phase=="onset" ? first(split(r.sample_id,":"))*":before_start" : r.sample_id
    now=get(current,(endpoint,r.feature),nothing)
    value=now===nothing || ismissing(now.value) || ismissing(r.value) ? missing : now.value-r.value
    push!(deltas,(family_id=s.family_id,sample_id=r.sample_id,phase=s.phase,feature=r.feature,lag_s=r.lag_s,change=value,from_age_s=r.age_s,to_age_s=now===nothing ? missing : now.age_s,chronological_quarter=s.chronological_quarter))
end
delta=DataFrame(deltas);save("prestart_feature_changes",delta)
paired=NamedTuple[]
dm=Dict((r.family_id,r.feature,r.lag_s,r.phase)=>r for r in eachrow(delta))
for r in eachrow(delta)
    r.phase=="onset" || continue
    for control in ["near_before","near_after"]
        c=get(dm,(r.family_id,r.feature,r.lag_s,control),nothing)
        value=c===nothing || ismissing(r.change) || ismissing(c.change) ? missing : r.change-c.change
        push!(paired,(family_id=r.family_id,feature=r.feature,lag_s=r.lag_s,control=control,onset_change=r.change,control_change=c===nothing ? missing : c.change,difference=value,chronological_quarter=r.chronological_quarter))
    end
end
save("prestart_nearby_feature_pairs",paired)
ps=NamedTuple[]
for g in groupby(DataFrame(paired),[:feature,:lag_s,:control,:chronological_quarter])
    v=collect(skipmissing(g.difference));a=collect(skipmissing(g.onset_change));b=collect(skipmissing(g.control_change))
    push!(ps,(feature=g.feature[1],lag_s=g.lag_s[1],control=g.control[1],chronological_quarter=g.chronological_quarter[1],master_n=nrow(g),available_pair_n=length(v),mean_difference=isempty(v) ? missing : mean(v),median_difference=isempty(v) ? missing : median(v),positive_n=count(>(0),v),negative_n=count(<(0),v),flat_n=count(==(0),v),mean_onset_change=isempty(a) ? missing : mean(a),mean_control_change=isempty(b) ? missing : mean(b)))
end
save("prestart_nearby_feature_summary",ps)
# Contiguous interval overlap and nearby contamination, without excluding any row.
overlaps=NamedTuple[];starts=samples[samples.phase.=="onset",:]
for s in eachrow(starts), h in [120,300,600,1800,3600]
    others=count((starts.instrument_id.==s.instrument_id).&(starts.cutoff_ns.>=s.cutoff_ns-h*NS).&(starts.cutoff_ns.<=s.cutoff_ns+h*NS))-1
    push!(overlaps,(family_id=s.family_id,horizon_s=h,other_starts_within_horizon=others))
end
save("overlap_counts",overlaps)
println("Native price_raw/1e9 checks: ",checks[])
println("ONSET DIRECTION: fresh endpoint ages <=5 seconds; all quarters combined")
for h in [1,5,20,60,120,300,600,1800,3600], direction in ["up","down","flat","missing"]
    g=w[(w.phase.=="onset").&(w.horizon_s.==h).&(w.pre_direction.==direction),:]
    valid=[i for i in 1:nrow(g) if !ismissing(g.change[i]) && g.from_age_s[i]<=5 && g.to_age_s[i]<=5]
    v=Float64[g.change[i] for i in valid]
    signed=Float64[sign(g.pre120_change[i])*g.change[i] for i in valid if !ismissing(g.pre120_change[i]) && abs(g.pre120_change[i])>1e-12]
    println(JSON3.write(Dict("h"=>h,"direction"=>direction,"master_n"=>nrow(g),"fresh_n"=>length(v),"mean"=>isempty(v) ? nothing : mean(v),"median"=>isempty(v) ? nothing : median(v),"up"=>count(>(1e-12),v),"down"=>count(<(-1e-12),v),"flat"=>count(x->abs(x)<=1e-12,v),"mean_signed"=>isempty(signed) ? nothing : mean(signed))))
end
aa=DataFrame(associations)
println("Association dispositions: ",combine(groupby(aa,:disposition),nrow=>:rows))
println("Finished descriptive follow-up; no model or significance claims");flush(stdout)
