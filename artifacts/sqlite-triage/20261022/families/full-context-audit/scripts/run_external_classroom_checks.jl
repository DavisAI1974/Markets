using CSV,DataFrames,JSON3,SHA
include("dipole_pair_math.jl")
include("external_classroom_math.jl")
const BASE=get(ENV,"FAMILY_RESEARCH_DIR","/opt/frankie-box/work/family-research-20261022")
const OUT=joinpath(BASE,"external-classroom-audit-v1")
const NATIVE=joinpath(BASE,"dipole-audit-v1")

function binary_matrix(file,T,k,n)
    data=Vector{T}(undef,k*n)
    open(joinpath(NATIVE,file)) do io;read!(io,data);@assert eof(io);end
    reshape(data,k,n)
end

function main()
    @assert !isfile(joinpath(OUT,"external_classroom_check_receipt.json"))
    input=JSON3.read(read(joinpath(OUT,"original_series_known_values.json"),String))
    receipt=JSON3.read(read(joinpath(NATIVE,"complete_component_input_receipt.json"),String))
    n=Int(receipt.rows);names=String.(receipt.names)
    clocks=binary_matrix("clocks-i64.bin",Int64,7,n)
    @assert n==771787 && clocks[4,end]==1697662799696377528
    times=clocks[4,:]
    f32=binary_matrix("components-f32.bin",Float32,19,n)
    f64=binary_matrix("raw-components-f64.bin",Float64,19,n)
    states=binary_matrix("states-u8.bin",UInt8,19,n)
    values=Dict{String,Vector{Float64}}();codes=Dict{String,Vector{UInt8}}()
    segments=NamedTuple[];series_rows=NamedTuple[]
    for entry in input.series
        name=String(entry.name)
        x,s,idx=align_external_known(entry.known,times);values[name]=x;codes[name]=s
        starts=vcat(1,findall(!=(0),diff(idx)).+1);ends=vcat(starts[2:end].-1,n)
        for (a,b) in zip(starts,ends)
            k=idx[a];known=k==0 ? nothing : entry.known[k]
            push!(segments,(series=name,first_cursor=clocks[1,a],last_cursor=clocks[1,b],rows=b-a+1,
                first_receive_ns=times[a],last_receive_ns=times[b],known_index=k,
                published_ns=k==0 ? missing : Int64(known.published_ns),
                source_ordinal=k==0 ? missing : Int(known.source_ordinal),state=Int(s[a]),
                value=s[a]==0 ? x[a] : missing,reason=k==0 ? "NO_VALUE_PUBLISHED_AT_OR_BEFORE_THE_ROW_TIME" : something(known.reason,"")))
        end
        push!(series_rows,(series=name,table=String(entry.table),column=String(entry.column),where_json=JSON3.write(entry.where),
            known_values=length(entry.known),present=sum(s.==0),missing=sum(s.==1),invalid=sum(s.==2),ablated=sum(s.==3),
            direction=present_direction(x,s,1:n),terminal_state=Int(s[end]),terminal_value=s[end]==0 ? x[end] : missing))
    end
    external=String[String(e.name) for e in input.series]
    pairlist=vcat([(a,b) for a in external for b in names],[(external[i],external[j]) for i in 1:length(external)-1 for j in i+1:length(external)])
    @assert length(pairlist)==2040
    claimed=Set((String(c.evidence_refs[1].left),String(c.evidence_refs[1].right)) for c in input.claims)
    @assert length(claimed)==441 && issubset(claimed,Set(pairlist))
    lo,hi=extrema(times)
    quarters=[min(4,1+Int(fld((Int128(t)-lo)*4,Int128(hi)-lo+1))) for t in times]
    periods=vcat([("all_retained",collect(1:n))],[("elapsed_quarter_"*string(q),findall(==(q),quarters)) for q in 1:4])
    bypair=Vector{Vector{NamedTuple}}(undef,length(pairlist))
    pair_state_rows=Vector{Vector{NamedTuple}}(undef,length(pairlist))
    Threads.@threads for p in eachindex(pairlist)
        a,b=pairlist[p];out=NamedTuple[];state_out=NamedTuple[]
        for precision in ["classroom_float32","raw_native_float64"],(period,ix) in periods,strict in [false,true]
            basecase=precision=="classroom_float32" && period=="all_retained" && !strict
            basecase || (a,b) in claimed || continue
            # External series are Float64 in the original definition; only native inputs change precision.
            native=precision=="classroom_float32" ? f32 : f64
            j=findfirst(==(b),names)
            y=j===nothing ? values[b] : view(native,j,:)
            sy=j===nothing ? codes[b] : view(states,j,:)
            summary,sp=source_pair_summary(values[a],y,codes[a],sy,clocks,ix;strict_groups=strict)
            method=strict ? "consecutive_completed_groups_same_instrument" : "source_compressed_present"
            push!(out,(left=a,right=b,precision=precision,period=period,method=method,summary...))
            if basecase
                for u in 1:4,v in 1:4
                    push!(state_out,(left=a,right=b,left_state=u-1,right_state=v-1,count=sp[u,v]))
                end
            end
        end
        bypair[p]=out;pair_state_rows[p]=state_out
    end
    rows=reduce(vcat,bypair);table=DataFrame(rows)
    CSV.write(joinpath(OUT,"external_pair_checks.csv"),table)
    CSV.write(joinpath(OUT,"external_pair_state_counts.csv"),DataFrame(reduce(vcat,pair_state_rows)))
    CSV.write(joinpath(OUT,"external_series_alignment.csv"),DataFrame(series_rows))
    CSV.write(joinpath(OUT,"external_series_segments.csv"),DataFrame(segments))
    original=filter(r->r.precision=="classroom_float32" && r.period=="all_retained" && r.method=="source_compressed_present",table)
    lookup=Dict((r.left,r.right)=>r for r in eachrow(original));checks=NamedTuple[]
    for claim in input.claims
        ref=claim.evidence_refs[1];r=lookup[(String(ref.left),String(ref.right))]
        expected=Dict(String(k)=>Int(v) for (k,v) in pairs(ref.steps))
        actual=Dict(String(k)=>Int(r[k]) for k in STEP_NAMES)
        ok=expected==actual && String(claim.declared_endpoint_relation)==r.endpoint_relation
        push!(checks,(finding_id=String(claim.finding_id),left=r.left,right=r.right,
            status=ok ? "reproduced_descriptive_claim" : "not_fully_reproduced",
            claimed_endpoint_relation=String(claim.declared_endpoint_relation),actual_endpoint_relation=r.endpoint_relation,
            expected_steps_json=JSON3.write(expected),actual_steps_json=JSON3.write(actual),
            present_overlap=r.present_overlap,pearson=r.pearson,pearson_reason=r.pearson_reason,
            nonconsecutive_group_transitions=r.nonconsecutive_group_transitions,research_status="open"))
    end
    CSV.write(joinpath(OUT,"external_classroom_claim_checks.csv"),DataFrame(checks))
    report=Dict("schema"=>"EXTERNAL_CLASSROOM_CHECKS_V1","status"=>"complete","coverage_gate"=>"NOT_PASSED",
        "source_rows"=>n,"external_series"=>length(external),"known_values"=>sum(r.known_values for r in series_rows),
        "original_relationships"=>nrow(original),"claims_checked"=>length(checks),
        "claims_reproduced"=>count(r->r.status=="reproduced_descriptive_claim",checks),
        "claims_not_fully_reproduced"=>count(r->r.status!="reproduced_descriptive_claim",checks),
        "pair_summary_rows"=>nrow(table),"alignment_segments"=>length(segments),"julia_threads"=>Threads.nthreads(),
        "endpoint_relation_counts"=>Dict(k=>count(==(k),original.endpoint_relation) for k in unique(original.endpoint_relation)),
        "pearson_available"=>count(!ismissing,original.pearson),
        "pearson_unavailable_reasons"=>Dict(k=>count(==(k),original.pearson_reason) for k in unique(original.pearson_reason) if k!=""),
        "precision_rule"=>"Original external values Float64 plus native classroom Float32. Separate raw-native Float64 sensitivity.",
        "pearson_rule"=>"Julia centered Pearson; minimum 8 and exact constant-vector guard; not asserted bit-identical to original OpenBLAS-32 reduction.",
        "period_rule"=>"Quarter sensitivity uses elapsed receive time, matching original external alignment clock.",
        "limitations"=>["Reproduction checks stored step counts and endpoint relations; a reproduced hypothesis is not prospective evidence.",
          "Strict adjacency does not prove reset-free continuity; complete compact source lacks continuity segments.",
          "All 2040 original pairs checked; additional precision/quarter/adjacency sensitivities restricted to the 441 filed claim pairs.",
          "No expanded history, full v4 matrix or fitted model is asserted by this component."])
    open(joinpath(OUT,"external_classroom_check_receipt.json"),"w") do io;JSON3.pretty(io,report);end
    println(JSON3.write(report))
end
main()
