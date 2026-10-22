using SQLite,DBInterface,CSV,DataFrames,JSON3
const BASE=get(ENV,"FAMILY_RESEARCH_DIR","/opt/frankie-box/work/family-research-20261022")
const OUT=joinpath(BASE,"descriptive-v1")
db=SQLite.DB(joinpath(BASE,"alignment.sqlite"));DBInterface.execute(db,"PRAGMA query_only=ON")
sources=DataFrame(DBInterface.execute(db,"SELECT * FROM source_registry"))
receipts=CSV.read(joinpath(OUT,"group_context_receipts.csv"),DataFrame)
handles=Dict{String,IOStream}();offsets=Dict{String,Vector{UInt64}}();paths=Dict{String,String}()
for source in ["root.frames","native.member"]
    r=sources[sources.name.==source,:][1,:]
    open(r.offset_index,"r") do io
        header=JSON3.read(readline(io));a=collect(reinterpret(UInt64,read(io)))
        @assert String(header["byteorder"])=="little" && ENDIAN_BOM==0x04030201
        offsets[source]=a
    end
    handles[source]=open(r.path,"r");paths[source]=r.path
end
function record(source,ordinal)
    a=offsets[source];i=Int(ordinal)+1;handle=handles[source]
    seek(handle,a[i]);raw=read(handle,Int(a[i+1]-a[i]))
    JSON3.read(String(raw)),a[i],a[i+1]-a[i]
end
function unpack(x)
    tag=x[1]
    tag=="dict" && return Dict(String(p[1])=>unpack(p[2]) for p in x[2])
    tag=="float64" && return reinterpret(Float64,parse(UInt64,String(x[2]);base=16))
    tag=="null" && return nothing
    tag in ("list","tuple") && return [unpack(y) for y in x[2]]
    length(x)>1 ? x[2] : nothing
end
numeric(v)=v isa Real && !(v isa Bool) && isfinite(v) ? Float64(v) : missing
rows=NamedTuple[];source_receipts=NamedTuple[];checks=Ref(0)
function emit(context,name,v;basis="")
    push!(rows,(sample_id=context.sample_id,lag_s=context.lag_s,feature=name,value=numeric(v),age_s=context.age_s,anchor_basis=basis,source_ordinal=context.source_ordinal))
end
for (i,r) in enumerate(eachrow(receipts))
    packed,roff,rlen=record("root.frames",r.source_ordinal)
    member,noff,nlen=record("native.member",r.source_ordinal)
    f=Dict(String(p[1])=>p[2] for p in packed[2])
    @assert unpack(f["input_cursor"])==r.input_cursor
    @assert member["frankie_emission"]["input_cursor"]==r.input_cursor
    @assert member["instrument_id"] isa Integer
    push!(source_receipts,(sample_id=r.sample_id,lag_s=r.lag_s,source_ordinal=r.source_ordinal,input_cursor=r.input_cursor,cutoff_ns=r.cutoff_ns,known_by_ns=r.known_by_ns,age_s=r.age_s,root_path=paths["root.frames"],root_offset=roff,root_length=rlen,native_path=paths["native.member"],native_offset=noff,native_length=nlen))
    for k in ["best_bid","best_ask","mid","spread","depth_imbalance_n","depth_imbalance_full","bid_depth_full","ask_depth_full","bid_order_count_full","ask_order_count_full","bid_price_level_count_full","ask_price_level_count_full"]
        haskey(f,k) && emit(r,"root."*k,unpack(f[k]))
    end
    for (window,a) in unpack(f["activity"])
        for (k,v) in a
            if v isa AbstractDict
                for (subkey,subvalue) in v;emit(r,"root.activity."*window*"."*k*"."*subkey,subvalue);end
            else
                emit(r,"root.activity."*window*"."*k,v)
            end
        end
    end
    for (anchor,a) in pairs(member["activity_since"])
        basis=String(get(a,"anchor_basis",""))
        for (k,v) in pairs(a)
            name=String(k)
            # Anchor clocks/sequences are provenance; elapsed durations and counts are measurements.
            startswith(name,"anchor_") && continue
            name in ["side_orientation","receive_order_clean"] && continue
            if v isa JSON3.Object
                for (subkey,subvalue) in pairs(v);emit(r,"native.activity_since."*String(anchor)*"."*name*"."*String(subkey),subvalue;basis=basis);end
            else
                emit(r,"native.activity_since."*String(anchor)*"."*name,v;basis=basis)
            end
        end
    end
    for side in ["bid_levels","ask_levels"], level in member["book"][side]
        @assert abs(level["price"]-level["price_raw"]/1e9)<1e-10
        checks[]+=1
    end
    for (key,value) in pairs(member["book"])
        value isa Real && emit(r,"native.book."*String(key),value)
    end
    for side in ["bid_levels","ask_levels"], (rank,level) in enumerate(member["book"][side])
        for (key,value) in pairs(level)
            String(key)=="price_raw" && continue
            value isa Real && emit(r,"native.book."*side*".rank"*string(rank)*"."*String(key),value)
        end
    end
    for key in ["best_bid","best_ask","mid","spread"]
        a,b=unpack(f[key]),get(member["book"],key,nothing)
        if a isa Real && b isa Real;@assert abs(a-b)<1e-10;end
    end
    for k in ["component_count","formation_latency_ns","event_to_receive_latency_ns","f_last_to_decision_delay_ns","max_within_group_receive_gap_ns"]
        emit(r,"native."*k,get(member,k,nothing))
    end
    structure=member["structure"]
    for k in ["component_count","distinct_order_id_count","distinct_price_count","price_raw_span"]
        emit(r,"native.structure."*k,get(structure,k,nothing))
    end
    for k in ["action_counts","side_counts","fill_disposition_signature"]
        for (subkey,v) in pairs(get(structure,k,Dict()));emit(r,"native.structure."*k*"."*String(subkey),v);end
    end
    i%1000==0 && (println("Indexed completed-group contexts ",i,"/",nrow(receipts));flush(stdout))
end
for handle in values(handles);close(handle);end
CSV.write(joinpath(OUT,"complete_context_measurements.csv"),DataFrame(rows))
CSV.write(joinpath(OUT,"indexed_context_source_receipts.csv"),DataFrame(source_receipts))
println(JSON3.write(Dict("indexed_contexts"=>nrow(receipts),"numeric_measurement_rows"=>length(rows),"native_raw_price_unit_checks"=>checks[],"policy"=>"Read exact previously validated offsets only. All rows retained; observations carry original group clocks/cursors/ages. Source payloads remain pinned. No raw identifier, absolute timestamp, teacher knowledge or future label is a numerical feature.")))
