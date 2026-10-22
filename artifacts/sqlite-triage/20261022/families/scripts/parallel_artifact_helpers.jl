"""Shared preprocessing state and final output publication for the 63-slot run."""
function save_cohort_preprocessing(path,packet)
    cached=joinpath(ENV["COHORT_CACHE"],basename(path));lock=cached*".lock"
    if !isfile(cached)
        owner=false
        try
            mkdir(lock);owner=true
        catch err
            isdir(lock) || rethrow(err)
        end
        if owner
            try
                temp=cached*".tmp."*string(getpid());serialize(temp,packet);mv(temp,cached;force=false)
            finally
                rm(lock)
            end
        else
            for attempt in 1:3000
                isfile(cached) && break;sleep(0.05)
            end
            isfile(cached) || error("shared preprocessing state was not committed")
        end
    end
    ispath(path) || symlink(cached,path)
end

function publish_parallel_outputs(out,root)
    metricrows=NamedTuple.(eachrow(CSV.read(joinpath(out,"model_metrics.csv"),DataFrame)))
    predictionrows=NamedTuple.(eachrow(CSV.read(joinpath(out,"model_predictions.csv"),DataFrame)))
    splits=Dict{Tuple{String,Int,Int},NamedTuple}()
    original=joinpath(root,"serial-prefix/chronological_splits.csv")
    splitfiles=isfile(original) ? [original] : String[]
    for job in sort(readdir(joinpath(root,"jobs");join=true))
        isdir(job) || continue
        p=joinpath(job,"chronological_splits.csv");isfile(p)&&push!(splitfiles,p)
        for state in filter(p->endswith(p,".jls"),readdir(job;join=true))
            dest=joinpath(out,basename(state))
            # Old serial states were already copied into serial-prefix. The
            # completed isolated fit is the authoritative state for a rerun key.
            islink(dest) && continue
            isfile(dest) && rm(dest)
            symlink(state,dest)
        end
    end
    for file in splitfiles,row in eachrow(CSV.read(file,DataFrame))
        key=(String(row.outcome),Int(row.horizon_s),Int(row.fold));value=NamedTuple(row)
        haskey(splits,key) && !isequal(splits[key],value) && error("split disagreement across model workers")
        splits[key]=value
    end
    CSV.write(joinpath(out,"chronological_splits.csv"),DataFrame(collect(values(splits))))
    nm=CSV.read(joinpath(out,"neural_metrics.csv"),DataFrame);np=CSV.read(joinpath(out,"neural_predictions.csv"),DataFrame)
    nr=Dict("status"=>"completed","architectures"=>["neural_tree","residual_mlp","tabm_ensemble"],
      "metric_rows"=>nrow(nm),"prediction_rows"=>nrow(np),"error_rows"=>0,"epochs"=>25,
      "execution"=>"63-slot shared-input parallel scheduler with preserved serial prefix",
      "coverage_gate"=>"NOT_PASSED","limitation"=>"Candidate benchmark; one retained aligned market day; no established tradable signal.")
    open(joinpath(out,"neural_run_receipt.json"),"w") do io;JSON3.write(io,nr);end
    metricrows,predictionrows,collect(values(splits))
end
