using CSV,DataFrames,SQLite,DBInterface,Statistics,JSON3
include("descriptive_math.jl")
const BASE=get(ENV,"FAMILY_RESEARCH_DIR","/opt/frankie-box/work/family-research-20261022")
const OUT=joinpath(BASE,"joint-models-v1")
function paths()
    samples=CSV.read(joinpath(OUT,"model_sample_master.csv"),DataFrame)
    db=SQLite.DB(joinpath(BASE,"alignment.sqlite"));DBInterface.execute(db,"PRAGMA query_only=ON")
    pc=DataFrame(DBInterface.execute(db,"SELECT * FROM price_clock ORDER BY instrument_id,available_ns,group_close_input_cursor,source_ordinal"))
    pg=Dict(g.instrument_id[1]=>g for g in groupby(pc,:instrument_id))
    pricekeys=Dict(k=>collect(zip(g.available_ns,g.group_close_input_cursor)) for (k,g) in pg)
    rows=NamedTuple[]
    for s in eachrow(samples),h in [1,5,20,60,120,300,600,1800,3600]
        g=pg[s.instrument_id];keys=pricekeys[s.instrument_id]
        a=s.cutoff_ns;b=a+h*1_000_000_000
        i=asof_index(keys,a,s.cursor_cap);j=asof_index(keys,b)
        edge=a<g.available_ns[1] || b>g.available_ns[end] || i==0 || j==0
        fa=i==0 ? missing : (a-g.available_ns[i])/1e9;ta=j==0 ? missing : (b-g.available_ns[j])/1e9
        valid=!edge && fa<=5 && ta<=5
        v=valid ? Float64.(g.price_raw[i:j])./1e9 : Float64[]
        differences=diff(v);variation=sum(abs2,differences);lengthpath=sum(abs,differences)
        push!(rows,(sample_id=s.sample_id,family_id=s.family_id,phase=s.phase,horizon_s=h,chronological_quarter=s.chronological_quarter,
                    observed_trade_increment_n=valid ? j-i : missing,from_age_s=fa,to_age_s=ta,edge_censored=edge,
                    observed_trade_range=valid ? maximum(v)-minimum(v) : missing,
                    observed_trade_quadratic_variation=valid ? variation : missing,
                    observed_trade_absolute_path=valid ? lengthpath : missing,
                    observed_trade_endpoint_change=valid ? v[end]-v[1] : missing,
                    observed_trade_path_efficiency=valid && lengthpath>0 ? abs(v[end]-v[1])/lengthpath : missing,
                    maximum_up_trade_excursion=valid ? maximum(v)-v[1] : missing,
                    maximum_down_trade_excursion=valid ? v[1]-minimum(v) : missing,
                    disposition=!valid ? "missing_stale_or_censored_endpoint" : j==i ? "no_observed_trade_update;not_a_flat_market_claim" : "observed_transaction_path;contains_microstructure_noise"))
    end
    data=DataFrame(rows);CSV.write(joinpath(OUT,"observed_price_paths.csv"),data)
    summary=NamedTuple[]
    for g in groupby(data,[:phase,:horizon_s,:chronological_quarter])
        valid=g[.!ismissing.(g.observed_trade_range),:]
        eff=collect(skipmissing(valid.observed_trade_path_efficiency))
        push!(summary,(phase=g.phase[1],horizon_s=g.horizon_s[1],chronological_quarter=g.chronological_quarter[1],master_n=nrow(g),available_n=nrow(valid),edge_censored_n=count(g.edge_censored),no_trade_update_n=count(==("no_observed_trade_update;not_a_flat_market_claim"),valid.disposition),mean_observed_range=nrow(valid)==0 ? missing : mean(valid.observed_trade_range),mean_observed_quadratic_variation=nrow(valid)==0 ? missing : mean(valid.observed_trade_quadratic_variation),mean_absolute_endpoint_move=nrow(valid)==0 ? missing : mean(abs.(valid.observed_trade_endpoint_change)),median_observed_path_efficiency=isempty(eff) ? missing : median(eff)))
    end
    CSV.write(joinpath(OUT,"observed_price_path_summary.csv"),DataFrame(summary))
    receipt=Dict("path_rows"=>nrow(data),"source_trade_rows"=>nrow(pc),"semantics"=>"Supplemental observed transaction-path diagnostics, not fitted model outcomes. Range, quadratic variation, path length and excursions use actual same-instrument trades and exact known-by/cursor boundaries; no interpolation or post-session invented prices.","limitation"=>"Absolute endpoint change in the fitted models is a movement-magnitude proxy, not full-path realized volatility. These additional trade-path measures include microstructure noise and are not executable quote paths or guaranteed adverse-excursion costs.")
    open(joinpath(OUT,"price_path_receipt.json"),"w") do io;JSON3.write(io,receipt);end
    println(JSON3.write(receipt))
end
paths()
