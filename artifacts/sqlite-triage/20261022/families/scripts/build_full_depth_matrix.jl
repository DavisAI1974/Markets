using CSV,DataFrames,JSON3,Serialization,Statistics,SHA
const BASE=get(ENV,"FAMILY_RESEARCH_DIR","/opt/frankie-box/work/family-research-20261022")
const OLD=joinpath(BASE,"joint-inputs-v2")
const OUT=joinpath(BASE,"joint-inputs-v3")
include(joinpath(OLD,"scripts","model_rules.jl"))
function build()
    @assert !isfile(joinpath(OUT,"model_matrix.jls")) "refuse replacing a built matrix"
    old=deserialize(joinpath(OLD,"model_matrix.jls"))
    registry=CSV.read(joinpath(OUT,"additional_feature_registry.csv"),DataFrame)
    safe=String.(registry.feature)
    @assert all(safe_feature,safe)
    @assert isempty(intersect(safe,old.names)) "new names must not overwrite v2"
    names=vcat(safe,["delta$(lag).$n" for lag in [120,300,600] for n in safe])
    p=length(safe);fmap=Dict(n=>i for (i,n) in enumerate(safe))
    x=fill(NaN,nrow(old.samples),length(names))
    smap=Dict(String(s)=>i for (i,s) in enumerate(old.samples.sample_id))
    contexts=CSV.read(joinpath(BASE,"descriptive-v1","group_context_receipts.csv"),DataFrame)
    bysource=Dict{Int,Vector{Tuple{Int,Int}}}()
    for r in eachrow(contexts)
        sid=String(r.sample_id);lag=Int(r.lag_s)
        if lag==0
            push!(get!(bysource,Int(r.source_ordinal),Tuple{Int,Int}[]),(smap[sid],0))
        elseif endswith(sid,":onset")
            mapped=first(split(sid,":"))*":before_start"
            push!(get!(bysource,Int(r.source_ordinal),Tuple{Int,Int}[]),(smap[mapped],findfirst(==(lag),[120,300,600])))
        elseif old.samples.phase[smap[sid]] in ["near_before","near_after"]
            push!(get!(bysource,Int(r.source_ordinal),Tuple{Int,Int}[]),(smap[sid],findfirst(==(lag),[120,300,600])))
        end
    end
    seen=0
    for line in eachline(joinpath(OUT,"full_depth_values.jsonl"))
        row=JSON3.read(line);seen+=1
        for (sid,lagindex) in bysource[Int(row.source_ordinal)]
            for (n,v) in pairs(row.values)
                v===nothing && continue
                x[sid,lagindex*p+fmap[String(n)]]=Float64(v)
            end
        end
    end
    @assert seen==length(bysource)
    for k in 1:3,j in 1:p,i in axes(x,1)
        a,b=x[i,j],x[i,k*p+j]
        x[i,k*p+j]=isfinite(a)&&isfinite(b) ? a-b : NaN
    end
    @assert all(isnan,x[findall(s->s in ["onset","pre120"],old.samples.phase),p+1:end])
    allnames=vcat(old.names,names);allx=hcat(old.x,x)
    @assert isequal(allx[:,1:length(old.names)],old.x)
    @assert length(unique(old.samples.family_id))==749 && nrow(old.samples)==3745
    serialize(joinpath(OUT,"model_matrix.jls"),(x=allx,names=allnames,samples=old.samples))
    for file in ["model_sample_master.csv","model_outcomes.csv","excluded_predictor_metadata.csv"]
        cp(joinpath(OLD,file),joinpath(OUT,file);force=false)
        @assert read(joinpath(OLD,file))==read(joinpath(OUT,file))
    end
    prior=CSV.read(joinpath(OLD,"model_feature_registry.csv"),DataFrame)
    extra=DataFrame(column=length(old.names).+(1:length(names)),feature=names,group=layergroup.(replace.(names,r"^delta[0-9]+\."=>"")),causal_history=startswith.(names,"delta"))
    CSV.write(joinpath(OUT,"model_feature_registry.csv"),vcat(prior,extra))
    availability=NamedTuple[]
    for (j,n) in enumerate(names)
        for g in groupby(old.samples,[:phase,:chronological_quarter])
            ix=[smap[String(s)] for s in g.sample_id];v=x[ix,j]
            push!(availability,(feature=n,phase=String(g.phase[1]),quarter=Int(g.chronological_quarter[1]),master_n=length(ix),finite_n=count(isfinite,v),missing_n=count(!isfinite,v)))
        end
    end
    CSV.write(joinpath(OUT,"additional_feature_availability.csv"),DataFrame(availability))
    current=count(n->!startswith(n,"delta"),allnames)
    receipt=Dict("status"=>"completed","input_version"=>"joint-inputs-v3","v2_current_features"=>1896,"added_current_features"=>p,"current_features"=>current,"total_columns"=>length(allnames),"families"=>749,"samples"=>3745,"all_v2_columns_values_and_missingness_unchanged"=>true,"samples_and_outcomes_byte_identical"=>true,"additional_raw_finite_cells"=>count(isfinite,x),"model_fits_run_at_build"=>false,"history_seconds"=>[120,300,600],"source_audit"=>"additional_source_audit.json","retained_alignment"=>"unchanged 13 concepts,99 roles,confirmed second set,timestamped prices; all exact contexts remain pinned","outcome_sha256"=>bytes2hex(sha256(read(joinpath(OUT,"model_outcomes.csv")))))
    open(joinpath(OUT,"model_input_receipt.json"),"w") do io;JSON3.write(io,receipt);end
    println(JSON3.write(receipt))
end
build()
