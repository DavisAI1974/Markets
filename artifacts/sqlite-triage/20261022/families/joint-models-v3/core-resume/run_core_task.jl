using CSV,DataFrames,JSON3,Serialization,Statistics,LinearAlgebra,Random
using EvoTrees,Clustering,MultivariateStats
include("model_rules.jl")
const BASE=get(ENV,"FAMILY_RESEARCH_DIR","/opt/frankie-box/work/family-research-20261022")
const OUT=ENV["JOINT_MODEL_OUT"]
@assert OUT==joinpath(BASE,"joint-models-v3") || startswith(OUT,joinpath(BASE,"joint-models-v3","core-resume","jobs")*"/")
const NS=Int64(1_000_000_000)
BLAS.set_num_threads(8)
function atomiccsv(name,rows)
    isempty(rows) && return
    p=joinpath(OUT,name*".csv");CSV.write(p*".tmp",DataFrame(rows));mv(p*".tmp",p;force=true)
end
function runmodels()
    packet=deserialize(joinpath(OUT,"model_matrix.jls"));x,names,samples=packet.x,packet.names,packet.samples
    targets=CSV.read(joinpath(OUT,"model_outcomes.csv"),DataFrame)
    smap=Dict(String(r.sample_id)=>i for (i,r) in enumerate(eachrow(samples)))
    lo=minimum(samples.cutoff_ns);hi=maximum(samples.cutoff_ns)+1
    bounds=[lo+fld(k*(hi-lo),4) for k in 0:4]
    metrics=NamedTuple[];predictions=NamedTuple[];errors=NamedTuple[];splits=NamedTuple[]
    for g in groupby(targets,[:outcome,:horizon_s]),fold in 2:4
        outcome=String(g.outcome[1]);h=Int(g.horizon_s[1]);binary=outcome=="first_observed_family_within_h"
        get(ENV,"CORE_PCA_ONLY","0")=="1" && continue
        selected=get(ENV,"CORE_TASK","")
        !isempty(selected) && selected!="$(outcome)|$(h)|$(fold)" && continue
        begin_ns,end_ns=bounds[fold],bounds[fold+1]
        test=[i for i in 1:nrow(g) if begin_ns<=samples.cutoff_ns[smap[g.sample_id[i]]]<end_ns && !ismissing(g.value[i])]
        tf=Set(samples.family_id[smap[g.sample_id[i]]] for i in test)
        train=[i for i in 1:nrow(g) if !ismissing(g.value[i]) && g.label_end_ns[i]<begin_ns-600NS && !(samples.family_id[smap[g.sample_id[i]]] in tf)]
        push!(splits,(outcome=outcome,horizon_s=h,fold=fold,train_n=length(train),test_n=length(test),test_start_ns=begin_ns,test_end_ns=end_ns,embargo_s=600,purge_horizon_s=h,train_family_n=length(unique(samples.family_id[smap[g.sample_id[i]]] for i in train)),test_family_n=length(tf)))
        if length(train)<30 || length(test)<10
            push!(errors,(outcome=outcome,horizon_s=h,fold=fold,model="all",disposition="insufficient_chronological_available_labels",detail="train=$(length(train));test=$(length(test))"));continue
        end
        tr=[smap[g.sample_id[i]] for i in train];te=[smap[g.sample_id[i]] for i in test]
        # The pre120 cohort lacks the same history sampling design: never let
        # deliberately unmaterialized lag columns identify cases to the classifier.
        use=binary ? findall(n->!startswith(n,"delta"),names) : collect(eachindex(names))
        prep=fitprep(x[tr,use],names[use]);a=applyprep(prep,x[tr,use]);b=applyprep(prep,x[te,use])
        y=Float64[g.value[i] for i in train];truth=Float64[g.value[i] for i in test]
        mu=mean(y);scale=binary ? 1.0 : max(std(y),1e-8);z=binary ? y : (y.-mu)./scale
        stem=replace(outcome,"_"=>"-")*"-h"*string(h)*"-fold"*string(fold)
        serialize(joinpath(OUT,stem*"-preprocessing.jls"),(prep=prep,raw_columns=use,target_mean=mu,target_scale=scale,train_sample_ids=samples.sample_id[tr],test_sample_ids=samples.sample_id[te]))
        models=binary ? ["training_frequency","ridge100","evotrees_depth3","evotrees_depth5"] : ["zero_change","training_mean","ridge100","evotrees_depth3","evotrees_depth5","evotrees_mae","evotrees_q10","evotrees_q90"]
        # Drop complete source groups (including their history and missingness
        # columns) and refit; this does not fabricate new market observations.
        groups=sort(unique(layergroup.(replace.(prep.names,r"^delta[0-9]+\."=>""))))
        append!(models,["dropgroup:"*group for group in groups])
        !binary && push!(models,"drop_history")
        for modelname in models
            try
                cols=collect(axes(a,2))
                if startswith(modelname,"dropgroup:")
                    group=modelname[11:end]
                    cols=[j for j in cols if layergroup(replace(prep.names[j],r"^delta[0-9]+\."=>""))!=group]
                elseif modelname=="drop_history"
                    cols=[j for j in cols if !startswith(prep.names[j],"delta")]
                end
                aa,bb=a[:,cols],b[:,cols]
                if modelname in ["training_frequency","training_mean"]
                    pred=fill(mu,length(test))
                elseif modelname=="zero_change"
                    pred=zeros(length(test))
                elseif modelname=="ridge100"
                    # A benchmark, not the interaction-discovery model.
                    centered=y.-mu
                    if size(aa,1)<=size(aa,2)
                        beta=aa'*((aa*aa'+100I)\centered)
                    else
                        beta=(aa'*aa+100I)\(aa'*centered)
                    end
                    pred=mu.+bb*beta
                elseif binary && length(unique(y))<2
                    pred=fill(mu,length(test))
                else
                    deep=modelname=="evotrees_depth5"
                    loss=binary ? :logloss : modelname=="evotrees_mae" ? :mae : modelname in ["evotrees_q10","evotrees_q90"] ? :quantile : :mse
                    alpha=modelname=="evotrees_q10" ? 0.1 : modelname=="evotrees_q90" ? 0.9 : 0.5
                    config=EvoTreeRegressor(loss=loss,alpha=alpha,max_depth=deep ? 5 : 3,nrounds=deep ? 120 : 80,nbins=32,min_weight=10.0,lambda=1.0,eta=0.05,rowsample=1.0,colsample=1.0,rng=20261022,device=:cpu)
                    fit=EvoTrees.fit(config;x_train=Float32.(aa),y_train=Float32.(z),verbosity=0)
                    raw=Float64.(vec(fit(Float32.(bb))))
                    pred=binary ? raw : mu.+scale.*raw
                    if !startswith(modelname,"dropgroup:") && modelname!="drop_history"
                        path=joinpath(OUT,stem*"-"*modelname*".jls")
                        serialize(path,(model=fit,features=prep.names[cols],target_mean=mu,target_scale=scale))
                    end
                end
                binary && (pred=clamp.(pred,1e-6,1-1e-6))
                @assert all(isfinite,pred)
                err=pred.-truth
                long=Float64[];short=Float64[];chosen=Float64[];active=0
                for (k,i) in enumerate(test)
                    row=g[i,:];sp=ismissing(row.initial_spread) ? missing : Float64(row.initial_spread)
                    if outcome=="mid_price_change" && !ismissing(row.long_crossing_return) && !ismissing(sp) && abs(pred[k])>sp
                        push!(chosen,pred[k]>0 ? row.long_crossing_return : row.short_crossing_return);active+=1
                    end
                    push!(predictions,(sample_id=row.sample_id,family_id=samples.family_id[te[k]],phase=samples.phase[te[k]],outcome=outcome,horizon_s=h,fold=fold,model=modelname,observed=truth[k],prediction=pred[k],long_crossing_return=row.long_crossing_return,short_crossing_return=row.short_crossing_return,initial_spread=sp))
                end
                push!(metrics,(outcome=outcome,horizon_s=h,fold=fold,model=modelname,train_n=length(train),test_n=length(test),fitted_columns=size(aa,2),train_label_mean=mu,test_label_mean=mean(truth),mae=mean(abs.(err)),rmse=sqrt(mean(err.^2)),brier=binary ? mean(err.^2) : missing,logloss=binary ? -mean(truth.*log.(pred).+(1 .-truth).*log.(1 .-pred)) : missing,direction_accuracy=outcome=="mid_price_change" ? mean(sign.(pred).==sign.(truth)) : missing,spread_threshold_active_n=active,mean_quote_crossing_return=isempty(chosen) ? missing : mean(chosen),median_quote_crossing_return=isempty(chosen) ? missing : median(chosen),quote_crossing_positive_n=count(>(1e-12),chosen),disposition="chronological_selected_cohort_exploratory"))
                println(JSON3.write(Dict("outcome"=>outcome,"h"=>h,"fold"=>fold,"model"=>modelname,"train"=>length(train),"test"=>length(test),"mae"=>mean(abs.(err)))));flush(stdout)
            catch err
                push!(errors,(outcome=outcome,horizon_s=h,fold=fold,model=modelname,disposition="execution_error",detail=sprint(showerror,err)))
                println("MODEL_ERROR ",modelname,": ",sprint(showerror,err));flush(stdout)
            end
        end
        atomiccsv("model_metrics",metrics);atomiccsv("model_predictions",predictions);atomiccsv("model_errors",errors);atomiccsv("chronological_splits",splits)
    end
    if get(ENV,"CORE_TASK","")!=""
        open(joinpath(OUT,"core_task_receipt.json"),"w") do io;JSON3.write(io,Dict("metric_rows"=>length(metrics),"prediction_rows"=>length(predictions),"error_rows"=>length(errors)));end
        return
    end
    if get(ENV,"CORE_PCA_ONLY","0")=="1"
        append!(metrics,NamedTuple.(eachrow(CSV.read(joinpath(OUT,"model_metrics.csv"),DataFrame))))
        append!(predictions,NamedTuple.(eachrow(CSV.read(joinpath(OUT,"model_predictions.csv"),DataFrame))))
    end
    # Unsupervised structure is fitted on the earliest quarter without outcomes.
    train=findall(i->samples.cutoff_ns[i]<bounds[2] && samples.phase[i] in ["before_start","near_before","near_after"],1:nrow(samples))
    prep=fitprep(x[train,:],names);z=applyprep(prep,x)
    pca=MultivariateStats.fit(PCA,permutedims(z[train,:]);method=:svd,maxoutdim=min(12,length(train)-1),pratio=1.0)
    scores=MultivariateStats.predict(pca,permutedims(z))
    CSV.write(joinpath(OUT,"pca_scores.csv"),hcat(select(samples,:sample_id,:family_id,:phase,:cutoff_ns,:chronological_quarter),DataFrame(permutedims(scores),:auto)))
    CSV.write(joinpath(OUT,"pca_loadings.csv"),hcat(DataFrame(feature=prep.names),DataFrame(MultivariateStats.projection(pca),:auto)))
    CSV.write(joinpath(OUT,"pca_variances.csv"),DataFrame(component=1:length(principalvars(pca)),variance=principalvars(pca)))
    clusters=NamedTuple[]
    for k in [3,5]
        Random.seed!(20261022+k)
        km=Clustering.kmeans(scores[:,train],k;maxiter=200,display=:none)
        for i in axes(scores,2)
            ds=[sum(abs2,scores[:,i]-km.centers[:,j]) for j in 1:k]
            push!(clusters,(sample_id=samples.sample_id[i],family_id=samples.family_id[i],phase=samples.phase[i],chronological_quarter=samples.chronological_quarter[i],model="pca_kmeans_"*string(k),cluster=argmin(ds),squared_distance=minimum(ds),training_quarter=samples.cutoff_ns[i]<bounds[2]))
        end
        serialize(joinpath(OUT,"pca-kmeans-"*string(k)*".jls"),(preprocessing=prep,pca=pca,centers=km.centers,training_sample_ids=samples.sample_id[train]))
    end
    atomiccsv("market_state_assignments",clusters)
    receipt=Dict("status"=>"completed","models"=>"EvoTrees shallow/deep, MAE, quantile tails, source-group refits, PCA and k-means; constant/ridge benchmarks","metric_rows"=>length(metrics),"prediction_rows"=>length(predictions),"error_rows"=>length(errors),"master_families"=>749,"master_samples"=>nrow(samples),"forward_folds"=>3,"embargo_seconds"=>600,"training_only_preprocessing"=>true,"live_orders"=>false,"limitation"=>"One retained day; selected overlapping contexts; no population birth-hazard or causal-effect claim; no fees, slippage, latency or guaranteed fills in quote-crossing diagnostics; all comparisons exploratory, no selected winner or significance claim.")
    open(joinpath(OUT,"model_run_receipt.json"),"w") do io;JSON3.write(io,receipt);end
    println(JSON3.write(receipt))
end
runmodels()
