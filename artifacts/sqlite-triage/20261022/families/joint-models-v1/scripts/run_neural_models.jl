# Official NeuroTabModels source/API: per-observation architectures only.
# No attention across inference observations, future-row retrieval, or test stopping.
using CSV,DataFrames,JSON3,Serialization,Statistics,LinearAlgebra
using NeuroTabModels, Zygote
using NeuroTabModels.Models: NeuroTreeConfig,ResNetConfig,TabMConfig
include("model_rules.jl")
const BASE=get(ENV,"FAMILY_RESEARCH_DIR","/opt/frankie-box/work/family-research-20261022")
const OUT=joinpath(BASE,"joint-models-v1")
BLAS.set_num_threads(8)
function savecsv(name,rows)
    isempty(rows) && return
    p=joinpath(OUT,name*".csv");CSV.write(p*".tmp",DataFrame(rows));mv(p*".tmp",p;force=true)
end
function neural()
    packet=deserialize(joinpath(OUT,"model_matrix.jls"));x,samples=packet.x,packet.samples
    outcomes=CSV.read(joinpath(OUT,"model_outcomes.csv"),DataFrame)
    smap=Dict(String(r.sample_id)=>i for (i,r) in enumerate(eachrow(samples)))
    lo=minimum(samples.cutoff_ns);hi=maximum(samples.cutoff_ns)+1
    bounds=[lo+fld(k*(hi-lo),4) for k in 0:4]
    metrics=NamedTuple[];predictions=NamedTuple[];errors=NamedTuple[]
    configs=[("neural_tree",NeuroTreeConfig(depth=3,ntrees=8,actA=:tanh)),
             ("residual_mlp",ResNetConfig(stack_size=2,hidden_size=32,dropout=0.1)),
             ("tabm_ensemble",TabMConfig(k=8,n_blocks=2,d_block=32,dropout=0.1,arch_type=:tabm))]
    for g in groupby(outcomes,[:outcome,:horizon_s]),fold in 2:4
        outcome=String(g.outcome[1]);h=Int(g.horizon_s[1]);binary=outcome=="first_observed_family_within_h"
        stem=replace(outcome,"_"=>"-")*"-h"*string(h)*"-fold"*string(fold)
        begin_ns,end_ns=bounds[fold],bounds[fold+1]
        test=[i for i in 1:nrow(g) if begin_ns<=samples.cutoff_ns[smap[g.sample_id[i]]]<end_ns && !ismissing(g.value[i])]
        tf=Set(samples.family_id[smap[g.sample_id[i]]] for i in test)
        train=[i for i in 1:nrow(g) if !ismissing(g.value[i]) && g.label_end_ns[i]<begin_ns-600_000_000_000 && !(samples.family_id[smap[g.sample_id[i]]] in tf)]
        if length(train)<30 || length(test)<10
            push!(errors,(outcome=outcome,horizon_s=h,fold=fold,model="all_neural",disposition="insufficient_chronological_available_labels",detail="same eligibility as main comparison"));continue
        end
        tr=[smap[g.sample_id[i]] for i in train];te=[smap[g.sample_id[i]] for i in test]
        use=binary ? findall(n->!startswith(n,"delta"),packet.names) : collect(eachindex(packet.names))
        p=(prep=fitprep(x[tr,use],packet.names[use]),raw_columns=use,train_sample_ids=samples.sample_id[tr],test_sample_ids=samples.sample_id[te])
        lookup=Dict(String(r.sample_id)=>r for r in eachrow(g))
        y=Float32[lookup[String(s)].value for s in p.train_sample_ids]
        truth=Float64[lookup[String(s)].value for s in p.test_sample_ids]
        a=Float32.(applyprep(p.prep,x[tr,p.raw_columns]));b=Float32.(applyprep(p.prep,x[te,p.raw_columns]))
        fnames=["x"*string(j) for j in axes(a,2)]
        dtrain=DataFrame(a,Symbol.(fnames));dtrain.response=y
        dtest=DataFrame(b,Symbol.(fnames))
        for (modelname,arch) in configs
            try
                if length(unique(y))<2
                    pred=fill(Float64(mean(y)),length(te));disposition="constant_training_target;no_neural_fit"
                else
                    config=NeuroTabRegressor(arch;loss=binary ? :logloss : :mse,nrounds=25,lr=0.003f0,wd=0.001f0,batchsize=128,seed=20261022,device=:cpu,backend=:zygote,scale_target=!binary)
                    model=NeuroTabModels.fit(config,dtrain;feature_names=fnames,target_name="response",verbosity=0)
                    pred=Float64.(vec(model(dtest)))
                    serialize(joinpath(OUT,stem*"-"*modelname*".jls"),(model=model,raw_columns=p.raw_columns,prep=p.prep,feature_names=fnames))
                    disposition="fixed_25_epochs;chronological_selected_cohort"
                end
                binary && (pred=clamp.(pred,1e-6,1-1e-6))
                @assert length(pred)==length(truth) && all(isfinite,pred)
                err=pred.-truth;chosen=Float64[]
                for (k,sid) in enumerate(p.test_sample_ids)
                    r=lookup[String(sid)];sp=r.initial_spread
                    if outcome=="mid_price_change" && !ismissing(sp) && !ismissing(r.long_crossing_return) && abs(pred[k])>sp
                        push!(chosen,pred[k]>0 ? r.long_crossing_return : r.short_crossing_return)
                    end
                    push!(predictions,(sample_id=String(sid),family_id=samples.family_id[te[k]],phase=samples.phase[te[k]],outcome=outcome,horizon_s=h,fold=fold,model=modelname,observed=truth[k],prediction=pred[k],long_crossing_return=r.long_crossing_return,short_crossing_return=r.short_crossing_return,initial_spread=sp))
                end
                push!(metrics,(outcome=outcome,horizon_s=h,fold=fold,model=modelname,train_n=length(tr),test_n=length(te),fitted_columns=size(a,2),train_label_mean=Float64(mean(y)),test_label_mean=mean(truth),mae=mean(abs.(err)),rmse=sqrt(mean(err.^2)),brier=binary ? mean(err.^2) : missing,logloss=binary ? -mean(truth.*log.(pred).+(1 .-truth).*log.(1 .-pred)) : missing,direction_accuracy=outcome=="mid_price_change" ? mean(sign.(pred).==sign.(truth)) : missing,spread_threshold_active_n=length(chosen),mean_quote_crossing_return=isempty(chosen) ? missing : mean(chosen),median_quote_crossing_return=isempty(chosen) ? missing : median(chosen),quote_crossing_positive_n=count(>(1e-12),chosen),disposition=disposition))
                println(JSON3.write(Dict("model"=>modelname,"outcome"=>outcome,"h"=>h,"fold"=>fold,"train"=>length(tr),"test"=>length(te),"mae"=>mean(abs.(err)))));flush(stdout)
            catch e
                push!(errors,(outcome=outcome,horizon_s=h,fold=fold,model=modelname,disposition="execution_error",detail=sprint(showerror,e)))
                println("NEURAL_ERROR ",modelname,": ",sprint(showerror,e));flush(stdout)
            end
            savecsv("neural_metrics",metrics);savecsv("neural_predictions",predictions);savecsv("neural_errors",errors)
        end
    end
    receipt=Dict("status"=>"completed","architectures"=>[r[1] for r in configs],"metric_rows"=>length(metrics),"prediction_rows"=>length(predictions),"error_rows"=>length(errors),"epochs"=>25,"target_or_horizon_selection"=>"all predeclared output definitions; no test-set tuning","inference"=>"per-observation architectures; frozen training preprocessing and normalization; no cross-observation inference attention","limitation"=>"One retained day and dependent selected contexts; no causal influence or established tradability claim.")
    open(joinpath(OUT,"neural_run_receipt.json"),"w") do io;JSON3.write(io,receipt);end
    println(JSON3.write(receipt))
end
neural()
