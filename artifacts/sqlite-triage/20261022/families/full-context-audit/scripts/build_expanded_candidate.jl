using CSV,DataFrames,JSON3,Serialization,Statistics,SHA
const BASE=get(ENV,"FAMILY_RESEARCH_DIR","/opt/frankie-box/work/family-research-20261022")
const OUT=joinpath(BASE,"joint-inputs-v4-candidate-20261022")
const MINNS=Int64(1697577903329548912)
function gzlines(f,path)
    open(`gzip -dc $path`) do io
        for line in eachline(io);f(JSON3.read(line));end
    end
end
function build()
    mkpath(OUT);@assert !isfile(joinpath(OUT,"model_matrix.jls"))
    old=deserialize(joinpath(BASE,"joint-inputs-v3/model_matrix.jls"))
    samples=old.samples;n=nrow(samples);smap=Dict(String(s)=>i for (i,s) in enumerate(samples.sample_id))
    contexts=CSV.read(joinpath(BASE,"descriptive-v1/group_context_receipts.csv"),DataFrame)
    bysource=Dict{Int,Vector{Tuple{Int,Int,Int64}}}();allcontexts=Tuple{Int,Int,Int64}[]
    for r in eachrow(contexts)
        sid=String(r.sample_id);lag=Int(r.lag_s);i=0;k=0
        if lag==0;i=smap[sid]
        elseif endswith(sid,":onset");i=smap[first(split(sid,":"))*":before_start"];k=findfirst(==(lag),[120,300,600])
        elseif samples.phase[smap[sid]] in ["near_before","near_after"];i=smap[sid];k=findfirst(==(lag),[120,300,600])
        else;continue;end
        item=(i,k,Int64(r.cutoff_ns));push!(get!(bysource,Int(r.source_ordinal),Tuple{Int,Int,Int64}[]),item);push!(allcontexts,item)
    end
    native=joinpath(BASE,"joint-inputs-v4");names=String[];vocab=Dict{String,Vector{String}}()
    for prefix in ["native_second","root_full"]
        reg=CSV.File(joinpath(native,prefix=="native_second" ? "native_second_full_feature_registry.csv" : "root_full_feature_registry.csv"))
        append!(names,["v4."*String(r.feature) for r in reg if r.kind=="numeric"])
        obj=JSON3.read(read(joinpath(native,prefix*"_category_vocabulary.json"),String))
        for (key,levels) in pairs(obj)
            field=String(key);vocab[field]=String.(levels)
            append!(names,["v4.category."*field*"="*level for level in vocab[field]])
        end
    end
    @assert length(unique(names))==length(names)
    p=length(names);fmap=Dict(name=>j for (j,name) in enumerate(names));x=fill(NaN,n,4p)
    println("Expanded native/ROOT current columns ",p);flush(stdout)
    for filename in ["native_second_full_context_values.jsonl.gz","root_full_context_values.jsonl.gz"]
        seen=Ref(0)
        gzlines(joinpath(native,filename)) do row
            ordinal=Int(row.source_ordinal);seen[]+=1
            for (i,k,cutoff) in bysource[ordinal]
                @assert Int64(row.known_by_ns)<=cutoff && Int(row.input_cursor)<=samples.cursor_cap[i]
                for (key,value) in pairs(row.numeric)
                    value===nothing && continue;x[i,k*p+fmap["v4."*String(key)]]=Float64(value)
                end
                for (key,value) in pairs(row.categories)
                    field=String(key);observed=String(value)
                    for level in vocab[field];x[i,k*p+fmap["v4.category."*field*"="*level]]=observed==level ? 1.0 : 0.0;end
                end
            end
        end
        @assert seen[]==6265;println("Loaded ",filename);flush(stdout)
    end
    for k in 1:3,j in 1:p,i in 1:n
        a,b=x[i,j],x[i,k*p+j];x[i,k*p+j]=isfinite(a)&&isfinite(b) ? a-b : NaN
    end
    # Store only changing history events, then discard columns provably constant
    # for every context. Training-only preprocessing remains responsible for all
    # other column selection, imputation, scaling and missingness masks.
    ev=Dict{String,Vector{Tuple{Int64,Float64}}}()
    age=Dict{String,Vector{Tuple{Int64,Union{Nothing,Int64}}}}()
    function add(name,t,value)
        v=value===nothing ? NaN : Float64(value)
        a=get!(ev,name,Tuple{Int64,Float64}[])
        if isempty(a)||!isequal(last(a)[2],v);push!(a,(t,v));end
    end
    # Category levels are schema indicators. A level appearing after training is
    # constant zero/missing in training and is removed by the unchanged fitprep.
    catlevels=Dict{String,Set{String}}();catstart=Dict{String,Int64}()
    lines=Ref(0)
    gzlines(joinpath(BASE,"external-scope-history-v4/scope_feature_timeline.jsonl.gz")) do row
        t=Int64(row.effective_ns);prefix="external_history."*String(row.point)*"|"*String(row.scope_id)*"|"
        for (field,value) in pairs(row.numeric);add(prefix*String(field),t,value);end
        for (field,value) in pairs(row.categories)
            key=prefix*"category."*String(field);encoded=String(JSON3.write(value))
            levels=get!(catlevels,key,Set{String}());start=get!(catstart,key,t)
            if !(encoded in levels)
                push!(levels,encoded)
                start<t && add(key*"="*encoded,start,0.0)
            end
            for level in levels;add(key*"="*level,t,level==encoded ? 1.0 : 0.0);end
        end
        # Exact Int64 clocks remain in the source sidecar. Only relative ages
        # are numerical inputs; never cast an absolute nanosecond to Float64.
        for field in ["current.known_by_ns","previous.known_by_ns"]
            value=get(row.clock_provenance,Symbol(field),nothing)
            name=prefix*replace(field,"known_by_ns"=>"age_s")
            a=get!(age,name,Tuple{Int64,Union{Nothing,Int64}}[])
            stamp=value===nothing ? nothing : Int64(value)
            if isempty(a)||!isequal(last(a)[2],stamp);push!(a,(t,stamp));end
        end
        lines[]+=1
        lines[]%25000==0 && (println("History timeline rows ",lines[]);flush(stdout))
    end
    kept=sort(vcat([key for (key,a) in ev if length(a)>1 || (first(a)[1]>MINNS && isfinite(first(a)[2]))],
      [key for (key,a) in age if any(v->v[2]!==nothing,a)]))
    q=length(kept);z=fill(NaN,n,4q);println("Dynamic history/age current columns ",q,"; constant history columns retained in provenance ",length(ev)-q);flush(stdout)
    for (j,key) in enumerate(kept)
        isage=haskey(age,key);a=isage ? age[key] : ev[key];times=first.(a)
        for (i,k,cutoff) in allcontexts
            idx=searchsortedlast(times,cutoff);idx==0 && continue;v=a[idx][2]
            if isage;v=v===nothing ? NaN : Float64(cutoff-v)/1e9;end
            z[i,k*q+j]=v
        end
    end
    for k in 1:3,j in 1:q,i in 1:n
        a,b=z[i,j],z[i,k*q+j];z[i,k*q+j]=isfinite(a)&&isfinite(b) ? a-b : NaN
    end
    extra=vcat(names,["delta$(lag).$name" for lag in [120,300,600] for name in names],kept,["delta$(lag).$name" for lag in [120,300,600] for name in kept])
    allnames=vcat(old.names,extra);allx=hcat(old.x,x,z)
    @assert length(unique(allnames))==length(allnames) && n==3745 && length(unique(samples.family_id))==749
    @assert isequal(view(allx,:,1:length(old.names)),old.x)
    for file in ["model_sample_master.csv","model_outcomes.csv","excluded_predictor_metadata.csv"]
        cp(joinpath(BASE,"joint-inputs-v3",file),joinpath(OUT,file);force=false)
    end
    serialize(joinpath(OUT,"model_matrix.jls"),(x=allx,names=allnames,samples=samples))
    CSV.write(joinpath(OUT,"model_feature_registry.csv"),DataFrame(column=1:length(allnames),feature=allnames,causal_history=startswith.(allnames,"delta")))
    report=Dict("status"=>"completed_candidate","coverage_gate"=>"NOT_PASSED","user_priority"=>"one verification pass, start Julia promptly; unresolved semantic coverage explicitly retained",
      "samples"=>n,"families"=>749,"columns"=>length(allnames),"expanded_native_root_current"=>p,"history_current"=>q,"history_timeline_rows"=>lines[],
      "all_v3_values_and_missingness_unchanged"=>true,"outcome_sha256"=>bytes2hex(sha256(read(joinpath(OUT,"model_outcomes.csv")))),
      "remaining"=>["Complete knowledge/99-plane semantic consumer ledger and unit mappings; candidate is not a fully certified v4 result.","Posthoc knowledge and complete episode outcomes are research evidence, not backdated predictors."])
    open(joinpath(OUT,"model_input_receipt.json"),"w") do io;JSON3.write(io,report);end
    println(JSON3.write(report));flush(stdout)
end
build()
