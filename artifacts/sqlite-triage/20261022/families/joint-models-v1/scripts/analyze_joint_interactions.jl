using CSV,DataFrames,JSON3,Serialization,Statistics,EvoTrees
include("model_rules.jl")
const BASE=get(ENV,"FAMILY_RESEARCH_DIR","/opt/frankie-box/work/family-research-20261022")
const OUT=joinpath(BASE,"joint-models-v1")
function analyze()
    packet=deserialize(joinpath(OUT,"model_matrix.jls"));x,names,samples=packet.x,packet.names,packet.samples
    smap=Dict(String(r.sample_id)=>i for (i,r) in enumerate(eachrow(samples)))
    fmap=Dict(n=>j for (j,n) in enumerate(names))
    outcomes=CSV.read(joinpath(OUT,"model_outcomes.csv"),DataFrame)
    ol=Dict((String(r.sample_id),String(r.outcome),Int(r.horizon_s))=>r for r in eachrow(outcomes))
    splits=NamedTuple[];pairs=NamedTuple[];cells=NamedTuple[];contrasts=NamedTuple[]
    function observed(feature,indices)
        mask=endswith(feature,".__missing");base=mask ? feature[1:end-length(".__missing")] : feature
        j=fmap[base]
        mask ? numeric_missing_mask(x[indices,j]) : x[indices,j]
    end
    files=sort(filter(n->occursin(r"-evotrees_depth[35]\.jls$",n),readdir(OUT)))
    for file in files
        matchinfo=match(r"^(.*)-h([0-9]+)-fold([234])-(evotrees_depth[35])\.jls$",file)
        matchinfo===nothing && continue
        outcome=replace(matchinfo[1],"-"=>"_");h=parse(Int,matchinfo[2]);fold=parse(Int,matchinfo[3]);modelname=matchinfo[4]
        r=deserialize(joinpath(OUT,file));model=r.model
        p=deserialize(joinpath(OUT,replace(file,r"-evotrees_depth[35]\.jls$"=>"-preprocessing.jls")))
        tr=[smap[String(s)] for s in p.train_sample_ids];te=[smap[String(s)] for s in p.test_sample_ids]
        fcounts=Dict{Int,Tuple{Int,Float64}}();pc=Dict{Tuple{Int,Int},Tuple{Int,Float64}}()
        for tree in model.trees
            # EvoTrees 0.18.8 predict.jl/shap.jl use binary-heap child nodes 2n,2n+1.
            for node in findall(tree.split)
                feature=tree.feat[node];gain=Float64(tree.gain[node]);count,total=get(fcounts,feature,(0,0.0));fcounts[feature]=(count+1,total+gain)
                ancestor=fld(node,2)
                while ancestor>0
                    if tree.split[ancestor] && tree.feat[ancestor]!=feature
                        key=minmax(feature,tree.feat[ancestor]);count,total=get(pc,key,(0,0.0));pc[key]=(count+1,total+gain)
                    end
                    ancestor=fld(ancestor,2)
                end
            end
        end
        totalgain=sum(last(v) for v in values(fcounts);init=0.0)
        for (f,(n,g)) in fcounts
            push!(splits,(outcome=outcome,horizon_s=h,fold=fold,model=modelname,feature=r.features[f],source_group=layergroup(replace(r.features[f],r"^delta[0-9]+\."=>"")),split_count=n,training_gain=g,within_fit_gain_share=totalgain==0 ? 0.0 : g/totalgain))
        end
        ranked=sort(collect(pc);by=t->last(t.second),rev=true)
        for (rank,(key,(n,g))) in enumerate(ranked)
            a,b=r.features[key[1]],r.features[key[2]]
            push!(pairs,(outcome=outcome,horizon_s=h,fold=fold,model=modelname,training_rank=rank,feature_a=a,feature_b=b,conditional_split_pair_n=n,conditional_training_gain=g))
        end
        # All split pairs are saved. The response grids below are selected using
        # training gain only, never using the held-out response or profitability.
        for (key,(n,g)) in first(ranked,min(5,length(ranked)))
            an,bn=r.features[key[1]],r.features[key[2]]
            a,b=observed(an,tr),observed(bn,tr);av=filter(isfinite,a);bv=filter(isfinite,b)
            (isempty(av) || isempty(bv)) && continue
            qa=quantile(av,[0.25,0.75]);qb=quantile(bv,[0.25,0.75])
            at,bt=observed(an,te),observed(bn,te)
            vals=Dict{Tuple{Int,Int},Vector{Float64}}()
            for (k,sid) in enumerate(p.test_sample_ids)
                row=ol[(String(sid),outcome,h)]
                isfinite(at[k]) && isfinite(bt[k]) && !ismissing(row.value) || continue
                ba=at[k]<=qa[1] ? 1 : at[k]>qa[2] ? 3 : 2
                bb=bt[k]<=qb[1] ? 1 : bt[k]>qb[2] ? 3 : 2
                push!(get!(vals,(ba,bb),Float64[]),row.value)
            end
            for ba in 1:3,bb in 1:3
                v=get(vals,(ba,bb),Float64[])
                push!(cells,(outcome=outcome,horizon_s=h,fold=fold,model=modelname,feature_a=an,feature_b=bn,bin_a=ba,bin_b=bb,a_train_q25=qa[1],a_train_q75=qa[2],b_train_q25=qb[1],b_train_q75=qb[2],heldout_pair_n=length(v),mean_outcome=isempty(v) ? missing : mean(v),median_outcome=isempty(v) ? missing : median(v),disposition=length(v)<10 ? "thin_observed_cell" : "observed_cell;not_causal"))
            end
            corners=[get(vals,k,Float64[]) for k in [(3,3),(3,1),(1,3),(1,1)]]
            enough=all(length(v)>=10 for v in corners)
            delta=enough ? mean(corners[1])-mean(corners[2])-mean(corners[3])+mean(corners[4]) : missing
            push!(contrasts,(outcome=outcome,horizon_s=h,fold=fold,model=modelname,feature_a=an,feature_b=bn,corner_counts=join(length.(corners),"|"),observed_four_cell_contrast=delta,disposition=enough ? "exploratory_heldout_contrast;confounding_and_dependence_unresolved" : "insufficient_heldout_corner_counts"))
        end
    end
    for (name,rows) in [("fitted_split_features",splits),("fitted_conditional_split_pairs",pairs),("heldout_joint_response_cells",cells),("heldout_joint_response_contrasts",contrasts)]
        !isempty(rows) && CSV.write(joinpath(OUT,name*".csv"),DataFrame(rows))
    end
    # Changes in error after source-group refitting are evaluated on identical
    # chronological test sets; redundant blocks may substitute for each other.
    m=CSV.read(joinpath(OUT,"model_metrics.csv"),DataFrame)
    base=Dict((r.outcome,r.horizon_s,r.fold)=>r for r in eachrow(m) if r.model=="evotrees_depth3")
    ab=NamedTuple[]
    for row in eachrow(m)
        startswith(row.model,"dropgroup:") || row.model=="drop_history" || continue
        b=base[(row.outcome,row.horizon_s,row.fold)]
        push!(ab,(outcome=row.outcome,horizon_s=row.horizon_s,fold=row.fold,source_group=row.model,test_n=row.test_n,full_model_mae=b.mae,drop_group_mae=row.mae,drop_minus_full_mae=row.mae-b.mae,full_brier=b.brier,drop_brier=row.brier,disposition="positive_delta_means_group_helped_this_fit;not_causal;all_comparisons_retained"))
    end
    CSV.write(joinpath(OUT,"source_group_ablation_comparisons.csv"),DataFrame(ab))
    receipt=Dict("fitted_feature_rows"=>length(splits),"conditional_split_pair_rows"=>length(pairs),"heldout_cell_rows"=>length(cells),"heldout_contrast_rows"=>length(contrasts),"group_ablation_rows"=>length(ab),"pair_selection"=>"top five pairs per model selected only on training conditional split gain; full pair inventory saved","meaning"=>"Conditional tree paths and observed heldout strata are interaction candidates, not proof of physical synergy or causal influence. No synthetic future rows, test-based pair selection, or feature backfill.")
    open(joinpath(OUT,"interaction_analysis_receipt.json"),"w") do io;JSON3.write(io,receipt);end
    println(JSON3.write(receipt))
end
analyze()
