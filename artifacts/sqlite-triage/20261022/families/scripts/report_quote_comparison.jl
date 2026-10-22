using CSV, DataFrames, Statistics, JSON3
const BASE=get(ENV,"FAMILY_RESEARCH_DIR","/opt/frankie-box/work/family-research-20261022")
const OUT=get(ENV,"FAMILY_ANALYSIS_OUT",joinpath(BASE,"enriched-v2"))
q=CSV.read(joinpath(OUT,"quote_windows.csv"),DataFrame)
t=CSV.read(joinpath(OUT,"elapsed_windows.csv"),DataFrame)
d=leftjoin(q,select(t,:sample_id,:horizon_s,:change,:from_age_s=>:trade_from_age_s,:to_age_s=>:trade_to_age_s,:pre_direction,:pre120_change);on=[:sample_id,:horizon_s],validate=(true,true))
CSV.write(joinpath(OUT,"quote_trade_pairs.csv"),d)
rows=NamedTuple[]
for g in groupby(d,[:phase,:horizon_s,:pre_direction])
    for quarter in [0,1,2,3,4], maxage in [5.0,30.0,Inf]
        h=quarter==0 ? g : g[g.chronological_quarter.==quarter,:]
        valid=[i for i in 1:nrow(h) if !ismissing(h.mid_change[i]) && !ismissing(h.change[i]) && !ismissing(h.trade_from_age_s[i]) && !ismissing(h.from_age_s[i]) && h.from_age_s[i]<=maxage && h.to_age_s[i]<=maxage && h.trade_from_age_s[i]<=maxage && h.trade_to_age_s[i]<=maxage]
        mid=Float64[h.mid_change[i] for i in valid];trade=Float64[h.change[i] for i in valid]
        signed_mid=Float64[sign(h.pre120_change[i])*h.mid_change[i] for i in valid if !ismissing(h.pre120_change[i]) && abs(h.pre120_change[i])>1e-12]
        signed_trade=Float64[sign(h.pre120_change[i])*h.change[i] for i in valid if !ismissing(h.pre120_change[i]) && abs(h.pre120_change[i])>1e-12]
        push!(rows,(phase=g.phase[1],horizon_s=g.horizon_s[1],pre_direction=g.pre_direction[1],chronological_quarter=quarter,max_endpoint_age_s=maxage,
                    master_n=nrow(h),available_pair_n=length(valid),quote_edge_censored_n=count(h.edge_censored),
                    mean_mid_change=isempty(mid) ? missing : mean(mid),mean_trade_change=isempty(trade) ? missing : mean(trade),
                    median_mid_change=isempty(mid) ? missing : median(mid),median_trade_change=isempty(trade) ? missing : median(trade),
                    mid_up_n=count(>(1e-12),mid),mid_down_n=count(<(-1e-12),mid),mid_flat_n=count(x->abs(x)<=1e-12,mid),
                    trade_up_n=count(>(1e-12),trade),trade_down_n=count(<(-1e-12),trade),trade_flat_n=count(x->abs(x)<=1e-12,trade),
                    sign_disagreement_n=count(i->sign(abs(mid[i])<1e-12 ? 0 : mid[i])!=sign(abs(trade[i])<1e-12 ? 0 : trade[i]),eachindex(mid)),
                    signed_pair_n=length(signed_mid),mean_signed_mid_change=isempty(signed_mid) ? missing : mean(signed_mid),mean_signed_trade_change=isempty(signed_trade) ? missing : mean(signed_trade)))
    end
end
CSV.write(joinpath(OUT,"quote_trade_summary.csv"),DataFrame(rows))
ready=JSON3.read(read(joinpath(OUT,"all_additions_ready.json"),String),Dict{String,Any})
@assert ready["all_agreed_areas_accounted_for"] && ready["structural_counter_mismatches"]==0
ready["final_analysis_started"]=true;ready["final_analysis_completed"]=true
ready["quote_trade_pair_rows"]=nrow(d);ready["quote_trade_summary_rows"]=length(rows)
ready["analysis_policy"]="One enriched descriptive batch; frozen baseline reused; all additions present before numerical rerun; no fitted model or backtest."
open(joinpath(OUT,"completed_analysis_receipt.json"),"w") do io;JSON3.write(io,ready);end
println(JSON3.write(ready))
