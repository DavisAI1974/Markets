using CSV,DataFrames,JSON3,SHA
include("dipole_pair_math.jl")
const BASE=get(ENV,"FAMILY_RESEARCH_DIR","/opt/frankie-box/work/family-research-20261022")
const OUT=joinpath(BASE,"dipole-audit-v1")

function readmatrix(file,T,k,n)
    data=Vector{T}(undef,k*n)
    open(joinpath(OUT,file)) do io;read!(io,data);@assert eof(io);end
    reshape(data,k,n)
end

function main()
    @assert !isfile(joinpath(OUT,"complete_pair_checks_receipt.json"))
    input=JSON3.read(read(joinpath(OUT,"complete_component_input_receipt.json"),String))
    n=Int(input.rows);names=String.(input.names);@assert length(names)==19 && n==771787
    f32=readmatrix("components-f32.bin",Float32,19,n)
    f64=readmatrix("raw-components-f64.bin",Float64,19,n)
    states=readmatrix("states-u8.bin",UInt8,19,n)
    clocks=readmatrix("clocks-i64.bin",Int64,7,n)
    @assert all(diff(clocks[1,:]).>0)
    lo,hi=extrema(clocks[5,:]);periods=[("all_retained",collect(1:n))]
    quarter=[min(4,1+Int(fld((Int128(t)-lo)*4,Int128(hi)-lo+1))) for t in clocks[5,:]]
    append!(periods,[("elapsed_quarter_"*string(q),findall(==(q),quarter)) for q in 1:4])
    rows=NamedTuple[];state_rows=NamedTuple[]
    for (precision,x) in [("classroom_float32",f32),("raw_float64",f64)],(period,ix) in periods
        for a in 1:18,b in a+1:19,strict in [false,true]
            summary,pairs=source_pair_summary(view(x,a,:),view(x,b,:),view(states,a,:),view(states,b,:),clocks,ix;strict_groups=strict)
            method=strict ? "consecutive_completed_groups_same_instrument" : "source_compressed_present"
            push!(rows,(precision=precision,period=period,left=names[a],right=names[b],method=method,summary...))
            if precision=="classroom_float32" && !strict
                for i in 1:4,j in 1:4
                    push!(state_rows,(period=period,left=names[a],right=names[b],left_state=i-1,right_state=j-1,count=pairs[i,j]))
                end
            end
        end
        println("Completed ",precision," ",period);flush(stdout)
    end
    table=DataFrame(rows)
    CSV.write(joinpath(OUT,"complete_pair_checks.csv"),table)
    CSV.write(joinpath(OUT,"complete_pair_state_counts.csv"),DataFrame(state_rows))
    report=Dict("status"=>"complete","source_rows"=>n,"components"=>19,"pairs"=>171,
        "summary_rows"=>nrow(table),"elapsed_periods"=>5,"precisions"=>["classroom_float32","raw_float64"],
        "methods"=>["source_compressed_present","consecutive_completed_groups_same_instrument"],
        "source_definition"=>"dipole_classroom.py _direction, _direction_relation and _co_movement: individual first/last PRESENT endpoint relation; paired-PRESENT compression for steps. Pearson minimum8, zero variance unavailable.",
        "sensitivity_definition"=>"Step counts require adjacent completed group ordinals, same instrument and nondecreasing known-by clock. This is additional sensitivity, never silently substituted for the original definition.",
        "endpoint_step_disagreement_rows"=>sum(table.endpoint_step_disagreement),
        "limits"=>["Endpoint relation and step dominance are distinct descriptive questions; disagreement is an open scientific item, not a logical impossibility.",
                     "One retained day. No prospective market prediction, p-value, independent-day validation or causal claim.",
                     "Continuity segment is not available in the complete compact DB sequence; adjacency sensitivity does not prove reset-free continuity."])
    open(joinpath(OUT,"complete_pair_checks_receipt.json"),"w") do io;JSON3.pretty(io,report);end
    println(JSON3.write(report))
end
main()
