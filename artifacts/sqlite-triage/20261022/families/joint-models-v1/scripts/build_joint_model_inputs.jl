using CSV,DataFrames,JSON3,SQLite,DBInterface,Serialization,Statistics
include("model_rules.jl")
const BASE=get(ENV,"FAMILY_RESEARCH_DIR","/opt/frankie-box/work/family-research-20261022")
const INPUT=joinpath(BASE,"enriched-v2")
const OUT=joinpath(BASE,"joint-models-v1")
mkpath(OUT)
@assert isfile(joinpath(INPUT,"completed_analysis_receipt.json"))
function build()
    samples=CSV.read(joinpath(INPUT,"samples.csv"),DataFrame)
    smap=Dict(String(r.sample_id)=>i for (i,r) in enumerate(eachrow(samples)))
    current=Dict{Tuple{String,String},Float64}();history=Dict{Tuple{String,Int,String},Float64}()
    ages=Dict{Tuple{String,String},Float64}();allnames=Set{String}()
    function consume(file;lagged=false,skiproot=false)
        table=CSV.File(joinpath(INPUT,file*".csv"))
        for r in table
            sid=String(r.sample_id);name=String(r.feature)
            skiproot && startswith(name,"root.") && continue
            push!(allnames,name)
            lag=lagged ? Int(r.lag_s) : 0
            v=ismissing(r.value) ? NaN : Float64(r.value)
            if lag==0
                current[(sid,name)]=v
                age=hasproperty(r,:age_s) ? r.age_s : r.publication_age_s
                !ismissing(age) && (ages[(sid,name)]=Float64(age))
            else
                history[(sid,lag,name)]=v
            end
        end
        println("Loaded model input ",file);flush(stdout)
    end
    consume("features";skiproot=true)
    consume("group_measurements")
    consume("external_last_observed_measurements")
    consume("complete_context_measurements";lagged=true)
    consume("pullback_measurements";lagged=true)
    consume("enriched_context_measurements";lagged=true)
    consume("extended_second_set";lagged=true)
    consume("extended_group_measurements";lagged=true)
    original=sort(collect(allnames));safe=filter(safe_feature,original)
    names=vcat(safe,["delta"*string(lag)*"."*n for lag in [120,300,600] for n in safe])
    x=fill(NaN,nrow(samples),length(names));p=length(safe)
    for (j,n) in enumerate(safe),s in eachrow(samples)
        i=smap[s.sample_id];x[i,j]=get(current,(s.sample_id,n),NaN)
        for (k,lag) in enumerate([120,300,600])
            s.phase in ["before_start","near_before","near_after"] || continue
            history_sid=s.phase=="before_start" ? first(split(s.sample_id,":"))*":onset" : s.sample_id
            a=get(history,(history_sid,lag,n),NaN);b=x[i,j]
            x[i,k*p+j]=isfinite(a) && isfinite(b) ? b-a : NaN
        end
    end
    CSV.write(joinpath(OUT,"model_sample_master.csv"),samples)
    CSV.write(joinpath(OUT,"model_feature_registry.csv"),DataFrame(column=1:length(names),feature=names,group=layergroup.(replace.(names,r"^delta[0-9]+\."=>"")),causal_history=startswith.(names,"delta")))
    CSV.write(joinpath(OUT,"excluded_predictor_metadata.csv"),DataFrame(feature=setdiff(original,safe),reason=fill("identity_or_absolute_clock_or_outcome;original_source_preserved",length(setdiff(original,safe)))))
    # NaN denotes unavailable measurement in this separate numerical matrix; raw
    # source missingness/reasons and all rows remain in the frozen input artifacts.
    serialize(joinpath(OUT,"model_matrix.jls"),(x=x,names=names,samples=samples))
    q=CSV.read(joinpath(INPUT,"quote_windows.csv"),DataFrame)
    qmap=Dict((String(r.sample_id),Int(r.horizon_s))=>r for r in eachrow(q))
    db=SQLite.DB(joinpath(BASE,"alignment.sqlite"));DBInterface.execute(db,"PRAGMA query_only=ON")
    families=DataFrame(DBInterface.execute(db,"SELECT f.start_recv_ns,g.instrument_id FROM family_start f JOIN group_event g ON g.source_ordinal=f.source_ordinal ORDER BY f.start_recv_ns"))
    bounds=DataFrame(DBInterface.execute(db,"SELECT instrument_id,min(recv_ns) lo,max(recv_ns) hi FROM group_event GROUP BY instrument_id"))
    limits=Dict(r.instrument_id=>(r.lo,r.hi) for r in eachrow(bounds))
    starts=Dict(g.instrument_id[1]=>sort(collect(g.start_recv_ns)) for g in groupby(families,:instrument_id))
    targets=NamedTuple[]
    for s in eachrow(samples)
        if s.phase in ["before_start","near_before","near_after"]
            qs=s.phase=="before_start" ? first(split(s.sample_id,":"))*":onset" : s.sample_id
            mid=get(current,(s.sample_id,"root.mid"),NaN)
            bid=get(current,(s.sample_id,"root.best_bid"),NaN);ask=get(current,(s.sample_id,"root.best_ask"),NaN)
            age=get(ages,(s.sample_id,"root.mid"),NaN)
            for h in [1,5,20,60,120,300,600,1800,3600]
                z=qmap[(qs,h)];origin_mid=get(current,(qs,"root.mid"),NaN)
                future_mid=ismissing(z.mid_change) ? NaN : origin_mid+z.mid_change
                spread=ismissing(z.to_spread) ? NaN : Float64(z.to_spread)
                good=all(isfinite,[mid,bid,ask,age,future_mid,spread]) && age<=5 && !ismissing(z.to_age_s) && z.to_age_s<=5 && !z.edge_censored
                d=good ? future_mid-mid : missing
                long,short=good ? crossing_returns(bid,ask,future_mid-spread/2,future_mid+spread/2) : (missing,missing)
                endpoint=s.cutoff_ns+h*1_000_000_000+(s.phase=="before_start" ? 1 : 0)
                for (outcome,value) in [("mid_price_change",d),("absolute_mid_price_change",ismissing(d) ? missing : abs(d))]
                    push!(targets,(sample_id=s.sample_id,outcome=outcome,horizon_s=h,label_end_ns=endpoint,value=value,disposition=good ? "observed_quote_endpoints_ages_le5s" : "missing_stale_or_censored_quote_endpoint",long_crossing_return=long,short_crossing_return=short,initial_spread=isfinite(ask-bid) ? ask-bid : missing))
                end
            end
        end
        if s.phase in ["pre120","before_start","near_before","near_after"]
            ts=starts[s.instrument_id];lo,hi=limits[s.instrument_id]
            for h in [120,300,600]
                endpoint=s.cutoff_ns+h*1_000_000_000
                good=lo<=s.cutoff_ns<=endpoint<=hi
                n=searchsortedlast(ts,endpoint)-searchsortedlast(ts,s.cutoff_ns)
                push!(targets,(sample_id=s.sample_id,outcome="first_observed_family_within_h",horizon_s=h,label_end_ns=endpoint,value=good ? Float64(n>0) : missing,disposition=good ? "selected_context_occurrence_label_not_population_hazard" : "outside_retained_group_bounds",long_crossing_return=missing,short_crossing_return=missing,initial_spread=missing))
            end
        end
    end
    CSV.write(joinpath(OUT,"model_outcomes.csv"),DataFrame(targets))
    receipt=Dict("family_count"=>749,"samples"=>nrow(samples),"contemporaneous_features"=>p,"total_columns_with_causal_changes"=>length(names),"outcome_rows"=>length(targets),"history_seconds"=>[120,300,600],"source_inputs"=>INPUT,"source_disposition_policy"=>"Every original source and master row retained; no age, clock, ID, label or teacher field becomes an input.","sampling_limitation"=>"Contexts were selected around first-observed families and nearby periods. Family-occurrence probabilities are conditional on this selected cohort, not prospective population hazards.","price_outcome_definition"=>"Future observed midquote minus contemporaneous pre-start/control midquote. Actual first-start forecast endpoints are T0+h, one nanosecond beyond strict-before-start cutoff+h. Current and future quote ages <=5s; no post-session extrapolation.","missing_policy"=>"Raw model matrix is unimputed. Each model fits preprocessing only on its training fold. Family-occurrence models use contemporaneous columns only, because pre120 contexts lack the same extended history sampling design.")
    open(joinpath(OUT,"model_input_receipt.json"),"w") do io;JSON3.write(io,receipt);end
    println(JSON3.write(receipt))
end
build()
