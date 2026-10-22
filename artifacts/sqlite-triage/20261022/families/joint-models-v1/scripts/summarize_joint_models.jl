using CSV,DataFrames,JSON3,Serialization,Statistics
include("model_rules.jl")
const BASE=get(ENV,"FAMILY_RESEARCH_DIR","/opt/frankie-box/work/family-research-20261022")
const OUT=joinpath(BASE,"joint-models-v1")
load(n)=CSV.read(joinpath(OUT,n*".csv"),DataFrame)
save(n,d)=CSV.write(joinpath(OUT,n*".csv"),d isa DataFrame ? d : DataFrame(d))
function summarize()
    metrics=load("model_metrics");append!(metrics,load("neural_metrics");promote=true)
    samples=load("model_sample_master");outcomes=load("model_outcomes")
    lookup=Dict((String(r.sample_id),String(r.outcome),Int(r.horizon_s))=>r for r in eachrow(outcomes))
    # An MAE-appropriate constant benchmark, fitted without held-out labels.
    medmetrics=NamedTuple[];medpred=NamedTuple[]
    for row in eachrow(metrics[metrics.model.=="training_mean",:])
        stem=replace(row.outcome,"_"=>"-")*"-h"*string(row.horizon_s)*"-fold"*string(row.fold)
        p=deserialize(joinpath(OUT,stem*"-preprocessing.jls"))
        m=median([lookup[(String(s),String(row.outcome),Int(row.horizon_s))].value for s in p.train_sample_ids])
        truth=Float64[lookup[(String(s),String(row.outcome),Int(row.horizon_s))].value for s in p.test_sample_ids]
        e=m.-truth
        push!(medmetrics,(outcome=row.outcome,horizon_s=row.horizon_s,fold=row.fold,model="training_median",train_n=row.train_n,test_n=row.test_n,fitted_columns=0,train_label_mean=row.train_label_mean,test_label_mean=mean(truth),mae=mean(abs.(e)),rmse=sqrt(mean(e.^2)),brier=missing,logloss=missing,direction_accuracy=row.outcome=="mid_price_change" ? mean(sign(m).==sign.(truth)) : missing,spread_threshold_active_n=0,mean_quote_crossing_return=missing,median_quote_crossing_return=missing,quote_crossing_positive_n=0,disposition="training_only_median_benchmark"))
        for (k,s) in enumerate(p.test_sample_ids)
            r=lookup[(String(s),String(row.outcome),Int(row.horizon_s))]
            sr=samples[samples.sample_id.==s,:][1,:]
            push!(medpred,(sample_id=String(s),family_id=sr.family_id,phase=sr.phase,outcome=row.outcome,horizon_s=row.horizon_s,fold=row.fold,model="training_median",observed=truth[k],prediction=m,long_crossing_return=r.long_crossing_return,short_crossing_return=r.short_crossing_return,initial_spread=r.initial_spread))
        end
    end
    save("training_median_metrics",medmetrics);append!(metrics,DataFrame(medmetrics);promote=true)
    save("all_model_fold_metrics",metrics)
    for g in groupby(metrics,[:outcome,:horizon_s,:fold]);@assert length(unique(g.test_n))==1;end
    summary=NamedTuple[]
    for g in groupby(metrics,[:outcome,:horizon_s,:model])
        n=sum(g.test_n);mae=sum(g.mae.*g.test_n)/n;rmse=sqrt(sum((g.rmse.^2).*g.test_n)/n)
        br=all(ismissing,g.brier) ? missing : sum(Float64.(g.brier).*g.test_n)/n
        push!(summary,(outcome=g.outcome[1],horizon_s=g.horizon_s[1],model=g.model[1],folds=nrow(g),heldout_prediction_n=n,weighted_mae=mae,weighted_rmse=rmse,weighted_brier=br,fold_mae=join(g.mae,"|"),fold_test_n=join(g.test_n,"|")))
    end
    sd=DataFrame(summary);save("model_comparison_summary",sd)
    baselines=Dict((r.outcome,r.horizon_s)=>r for r in eachrow(sd) if r.model in ["training_median","training_frequency"])
    comparisons=NamedTuple[]
    foldbase=Dict((r.outcome,r.horizon_s,r.fold)=>r for r in eachrow(metrics) if r.model in ["training_median","training_frequency"])
    for g in groupby(metrics,[:outcome,:horizon_s,:model])
        b=baselines[(g.outcome[1],g.horizon_s[1])]
        s=sd[(sd.outcome.==g.outcome[1]).&(sd.horizon_s.==g.horizon_s[1]).&(sd.model.==g.model[1]),:][1,:]
        diffs=[r.mae-foldbase[(r.outcome,r.horizon_s,r.fold)].mae for r in eachrow(g)]
        push!(comparisons,(outcome=g.outcome[1],horizon_s=g.horizon_s[1],model=g.model[1],baseline=b.model,heldout_n=s.heldout_prediction_n,model_mae=s.weighted_mae,baseline_mae=b.weighted_mae,relative_mae_reduction=b.weighted_mae>0 ? 1-s.weighted_mae/b.weighted_mae : missing,folds=nrow(g),folds_with_lower_mae=count(<(0),diffs),fold_mae_differences=join(diffs,"|"),disposition=occursin("_q",g.model[1]) ? "tail_estimator;not_a_point_forecast_ranking" : "exploratory_intraday_chronological_comparison"))
    end
    save("model_baseline_comparisons",comparisons)
    preds=load("model_predictions");preds=preds[.!startswith.(preds.model,"dropgroup:").&(preds.model.!="drop_history"),:]
    append!(preds,load("neural_predictions");promote=true);append!(preds,DataFrame(medpred);promote=true)
    # Verify the independent neural and boosted implementations used the same
    # observed labels and chronological held-out cohort for each output/fold.
    same=NamedTuple[]
    for g in groupby(preds,[:outcome,:horizon_s,:fold])
        canonical=nothing
        for m in groupby(g,:model)
            keys=Set((String(r.sample_id),Float64(r.observed)) for r in eachrow(m))
            if canonical===nothing
                canonical=keys
            else
                @assert keys==canonical
            end
        end
        push!(same,(outcome=g.outcome[1],horizon_s=g.horizon_s[1],fold=g.fold[1],models=length(unique(g.model)),same_heldout_sample_labels=true))
    end
    save("heldout_alignment_audit",same)
    # Tail coverage is assessed separately from mean/median prediction errors.
    tails=preds[preds.model.=="evotrees_q10",:]
    upper=Dict((r.sample_id,r.outcome,r.horizon_s,r.fold)=>r.prediction for r in eachrow(preds[preds.model.=="evotrees_q90",:]))
    coverage=NamedTuple[]
    for g in groupby(tails,[:outcome,:horizon_s,:fold])
        high=[upper[(r.sample_id,r.outcome,r.horizon_s,r.fold)] for r in eachrow(g)]
        low=g.prediction;y=g.observed
        push!(coverage,(outcome=g.outcome[1],horizon_s=g.horizon_s[1],fold=g.fold[1],heldout_n=nrow(g),nominal_interval_coverage=0.8,observed_coverage=mean((low.<=y).&(y.<=high)),crossed_interval_n=count(low.>high),mean_width=mean(high-low),lower_tail_miss_n=count(y.<low),upper_tail_miss_n=count(y.>high)))
    end
    save("quantile_interval_coverage",coverage)
    preds=leftjoin(preds,select(samples,:sample_id,:pre_direction);on=:sample_id,validate=(false,true))
    phases=NamedTuple[]
    for g in groupby(preds,[:outcome,:horizon_s,:fold,:model,:phase,:pre_direction])
        e=g.prediction-g.observed
        push!(phases,(outcome=g.outcome[1],horizon_s=g.horizon_s[1],fold=g.fold[1],model=g.model[1],phase=g.phase[1],prior_direction=g.pre_direction[1],heldout_n=nrow(g),mae=mean(abs.(e)),mean_prediction=mean(g.prediction),mean_observed=mean(g.observed),negative_absolute_change_forecast_n=g.outcome[1]=="absolute_mid_price_change" ? count(<(0),g.prediction) : 0,observed_positive_n=count(>(1e-12),g.observed),observed_negative_n=count(<(-1e-12),g.observed),observed_flat_n=count(x->abs(x)<=1e-12,g.observed),error_abs_p95=quantile(abs.(e),0.95)))
    end
    save("phase_direction_model_diagnostics",phases)
    clusters=load("market_state_assignments");regimes=NamedTuple[]
    for clustering in groupby(clusters,:model)
        cm=Dict(String(r.sample_id)=>Int(r.cluster) for r in eachrow(clustering))
        temp=copy(preds);temp.cluster=[cm[String(s)] for s in temp.sample_id]
        for g in groupby(temp,[:outcome,:horizon_s,:fold,:model,:cluster])
            e=g.prediction-g.observed
            push!(regimes,(state_model=clustering.model[1],state=g.cluster[1],outcome=g.outcome[1],horizon_s=g.horizon_s[1],fold=g.fold[1],model=g.model[1],heldout_n=nrow(g),mae=mean(abs.(e)),mean_prediction=mean(g.prediction),mean_observed=mean(g.observed),error_abs_p95=quantile(abs.(e),0.95)))
        end
    end
    save("market_state_model_diagnostics",regimes)
    # Feature contribution audit: unobserved/constant training columns stay in
    # the raw registry and are explicitly distinguished from a fitted zero effect.
    packet=deserialize(joinpath(OUT,"model_matrix.jls"));fitted=NamedTuple[]
    for r in eachrow(metrics[metrics.model.=="evotrees_depth3",:])
        stem=replace(r.outcome,"_"=>"-")*"-h"*string(r.horizon_s)*"-fold"*string(r.fold)
        p=deserialize(joinpath(OUT,stem*"-preprocessing.jls"))
        used=Set(p.raw_columns[p.prep.columns]);masks=Set(p.raw_columns[p.prep.masks]);eligible_columns=Set(p.raw_columns)
        for j in eachindex(packet.names)
            state=j in used ? "numerical_variation_fitted" : j in masks ? "missingness_only_fitted" : j in eligible_columns ? "unobserved_or_constant_in_training" : "history_sampling_not_comparable_for_this_family_label"
            push!(fitted,(outcome=r.outcome,horizon_s=r.horizon_s,fold=r.fold,feature=packet.names[j],source_group=layergroup(replace(packet.names[j],r"^delta[0-9]+\."=>"")),disposition=state))
        end
    end
    save("training_feature_dispositions",fitted)
    receipt=Dict("model_fold_metric_rows"=>nrow(metrics),"model_horizon_summary_rows"=>nrow(sd),"all_heldout_alignment_checks_passed"=>true,"alignment_checks"=>length(same),"phase_direction_diagnostic_rows"=>length(phases),"market_state_diagnostic_rows"=>length(regimes),"training_feature_disposition_rows"=>length(fitted),"quantile_coverage_rows"=>length(coverage),"comparison_policy"=>"All configurations/horizons retained. No test-based model selection, independent-trial inference, or causal interpretation. Training medians/frequencies are benchmarks; quantiles evaluated for coverage separately.")
    open(joinpath(OUT,"model_summary_receipt.json"),"w") do io;JSON3.write(io,receipt);end
    println(JSON3.write(receipt))
end
summarize()
