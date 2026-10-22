using CSV, DataFrames, Serialization, Statistics, JSON3

# Read frozen v1 states only. This performs no fitting and never rewrites v1.
const BASE = get(ENV, "FAMILY_RESEARCH_DIR", "/opt/frankie-box/work/family-research-20261022")
const INPUT = joinpath(BASE, "joint-models-v3")
const OUTPUT = joinpath(BASE, "layer-review-v3")
include(joinpath(INPUT, "scripts", "model_rules.jl"))
mkpath(OUTPUT)
packet = deserialize(joinpath(INPUT, "model_matrix.jls"))
x, names, samples = packet.x, packet.names, packet.samples
smap = Dict(String(r.sample_id) => i for (i,r) in enumerate(eachrow(samples)))
fmap = Dict(n => j for (j,n) in enumerate(names))
outcomes = CSV.read(joinpath(INPUT, "model_outcomes.csv"), DataFrame)
ol = Dict((String(r.sample_id), String(r.outcome), Int(r.horizon_s)) => r for r in eachrow(outcomes))
contrasts = CSV.read(joinpath(INPUT, "heldout_joint_response_contrasts.csv"), DataFrame)
finite_mean(v) = isempty(v) ? missing : mean(v)
function observed(feature, indices)
    mask = endswith(feature, ".__missing")
    base = mask ? feature[1:end-length(".__missing")] : feature
    v = x[indices, fmap[base]]
    mask ? Float64.(.!isfinite.(v)) : v
end
function correlation(a,b)
    good = isfinite.(a) .& isfinite.(b)
    av,bv = a[good],b[good]
    length(av)>1 && std(av)>1e-12 && std(bv)>1e-12 ? cor(av,bv) : missing
end
bin(v,q) = !isfinite(v) ? 0 : v<=q[1] ? 1 : v>q[2] ? 3 : 2
function corner_contrast(indices, ba, bb, y; minimum=10)
    cs = [[i for i in indices if ba[i]==a && bb[i]==b] for (a,b) in [(3,3),(3,1),(1,3),(1,1)]]
    counts = length.(cs)
    contrast = all(counts .>= minimum) ? mean(y[cs[1]])-mean(y[cs[2]])-mean(y[cs[3]])+mean(y[cs[4]]) : missing
    counts,contrast
end
audit, cells, strata, feature_audit = NamedTuple[],NamedTuple[],NamedTuple[],NamedTuple[]
prep_cache = Dict()
for (pair_id,row) in enumerate(eachrow(contrasts))
    key = (String(row.outcome),Int(row.horizon_s),Int(row.fold))
    p = get!(prep_cache,key) do
        stem = replace(key[1],"_"=>"-")*"-h$(key[2])-fold$(key[3])-preprocessing.jls"
        deserialize(joinpath(INPUT,stem))
    end
    tr,te = [smap[String(s)] for s in p.train_sample_ids],[smap[String(s)] for s in p.test_sample_ids]
    atr,btr = observed(row.feature_a,tr),observed(row.feature_b,tr)
    a,b = observed(row.feature_a,te),observed(row.feature_b,te)
    qa,qb = quantile(filter(isfinite,atr),[.25,.75]),quantile(filter(isfinite,btr),[.25,.75])
    ba,bb = bin.(a,Ref(qa)),bin.(b,Ref(qb))
    ors = [ol[(String(s),key[1],key[2])] for s in p.test_sample_ids]
    @assert all(!ismissing(r.value) for r in ors)
    y = Float64[r.value for r in ors]
    ss = samples[te,:]
    identity = (pair_id=pair_id,outcome=key[1],horizon_s=key[2],fold=key[3],model=String(row.model),feature_a=String(row.feature_a),feature_b=String(row.feature_b))
    blocks = fld.(ss.cutoff_ns,Int64(1800_000_000_000))
    joint = isfinite.(a) .& isfinite.(b)
    counts,delta = corner_contrast(eachindex(y),ba,bb,y)
    @assert join(counts,"|")==row.corner_counts
    @assert ismissing(delta)==ismissing(row.observed_four_cell_contrast)
    @assert ismissing(delta) || isapprox(delta,row.observed_four_cell_contrast;atol=1e-14,rtol=1e-10)
    push!(audit,merge(identity,(heldout_n=length(te),joint_finite_n=count(joint),a_missing_n=count(.!isfinite.(a)),b_missing_n=count(.!isfinite.(b)),both_missing_n=count(.!isfinite.(a).&.!isfinite.(b)),a_train_q25=qa[1],a_train_q75=qa[2],b_train_q25=qb[1],b_train_q75=qb[2],train_corr=correlation(atr,btr),test_corr=correlation(a,b),test_equal_finite_n=count(joint .& (a.==b)),corner_counts=join(counts,"|"),contrast=delta,heldout_family_n=length(unique(ss.family_id)),heldout_30min_blocks=length(unique(blocks)))))
    for aa in 0:3,bc in 0:3
        ix = findall((ba.==aa).&(bb.==bc))
        vals = y[ix]
        spreads = Float64[ors[i].initial_spread for i in ix if !ismissing(ors[i].initial_spread)]
        prior = [ss.pre120_change[i] for i in ix if !ismissing(ss.pre120_change[i])]
        push!(cells,merge(identity,(bin_a=aa,bin_b=bc,n=length(ix),family_n=length(unique(ss.family_id[ix])),blocks_30min_n=length(unique(blocks[ix])),first_cutoff_ns=isempty(ix) ? missing : minimum(ss.cutoff_ns[ix]),last_cutoff_ns=isempty(ix) ? missing : maximum(ss.cutoff_ns[ix]),mean_outcome=finite_mean(vals),median_outcome=isempty(vals) ? missing : median(vals),mean_initial_spread=finite_mean(spreads),mean_pre120_change=finite_mean(prior),before_start_n=count(==("before_start"),ss.phase[ix]),onset_n=count(==("onset"),ss.phase[ix]),pre120_n=count(==("pre120"),ss.phase[ix]),near_before_n=count(==("near_before"),ss.phase[ix]),near_after_n=count(==("near_after"),ss.phase[ix]))))
    end
    # Diagnostic matching is post-hoc, not a new validation or causal estimator.
    for mode in ["phase","prior_direction","30min","phase_direction_30min"]
        groups = Dict{String,Vector{Int}}()
        for i in eachindex(y)
            label = mode=="phase" ? String(ss.phase[i]) : mode=="prior_direction" ? String(ss.pre_direction[i]) : mode=="30min" ? string(blocks[i]) : "$(ss.phase[i])|$(ss.pre_direction[i])|$(blocks[i])"
            push!(get!(groups,label,Int[]),i)
        end
        for (label,ix) in sort(collect(groups);by=first)
            cn,cd = corner_contrast(ix,ba,bb,y)
            cn5,cd5 = corner_contrast(ix,ba,bb,y;minimum=5)
            push!(strata,merge(identity,(matching=mode,stratum=label,n=length(ix),corner_counts=join(cn,"|"),contrast_min10=cd,contrast_min5=cd5)))
        end
    end
end
# Availability at all 3745 saved contexts, without deleting missing families.
selected = sort(unique(vcat(String.(contrasts.feature_a),String.(contrasts.feature_b))))
for feature in selected
    values = observed(feature,collect(axes(x,1)))
    for g in groupby(samples,[:phase,:chronological_quarter])
        ix = [smap[String(s)] for s in g.sample_id]
        v = values[ix]; vf=filter(isfinite,v)
        push!(feature_audit,(feature=feature,phase=String(g.phase[1]),quarter=Int(g.chronological_quarter[1]),master_n=length(v),finite_n=length(vf),missing_n=length(v)-length(vf),unique_finite_n=length(unique(vf)),minimum=isempty(vf) ? missing : minimum(vf),maximum=isempty(vf) ? missing : maximum(vf),negative_n=count(<(0),vf)))
    end
end
for (filename,rows) in [("pair_audit",audit),("response_cells_with_missingness",cells),("matched_context_contrasts",strata),("selected_feature_availability",feature_audit)]
    CSV.write(joinpath(OUTPUT,filename*".csv"),DataFrame(rows))
end
receipt=Dict("mode"=>"saved_v3_read_only_postprocessing_no_fit","pair_rows"=>length(audit),"response_cell_rows"=>length(cells),"matched_strata_rows"=>length(strata),"availability_rows"=>length(feature_audit),"selected_features"=>length(selected),"all_original_corner_counts_and_contrasts_reproduced"=>true,"bin_0"=>"source-unavailable raw value; __missing features themselves are observed binary indicators","matching"=>"posthoc descriptive; integer nanosecond half-hour blocks; minimum ten per corner primary, five sensitivity; no p-values or independent sample claims","v2_fit"=>false)
open(joinpath(OUTPUT,"review_receipt.json"),"w") do io; JSON3.write(io,receipt);end
println(JSON3.write(receipt))
