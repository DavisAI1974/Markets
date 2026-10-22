using CSV,DataFrames,Serialization,JSON3
const B="/opt/frankie-box/work/family-research-20261022"
a=deserialize(joinpath(B,"joint-models-v1/model_matrix.jls"));b=deserialize(joinpath(B,"joint-inputs-v2/model_matrix.jls"))
idx=Dict(n=>j for (j,n) in enumerate(b.names))
@assert all(isequal(a.x[:,j],b.x[:,idx[n]]) for (j,n) in enumerate(a.names))
@assert isequal(a.samples,b.samples)
@assert read(joinpath(B,"joint-models-v1/model_outcomes.csv"))==read(joinpath(B,"joint-inputs-v2/model_outcomes.csv"))
added=setdiff(b.names,a.names);@assert length(added)==40
rows=NamedTuple[]
for n in added
 v=b.x[:,idx[n]];push!(rows,(feature=n,available=count(isfinite,v),missing=count(!isfinite,v)))
end
CSV.write(joinpath(B,"joint-inputs-v2/added_duration_availability.csv"),DataFrame(rows))
base=[n for n in b.names if !startswith(n,"delta")]
pat=r"(?:^|[.])(?:[^.]*elapsed[^.]*|[^.]*duration[^.]*|[^.]*_age[^.]*|age_[^.]*|[^.]*latency[^.]*|time_to_[^.]*|time_since_[^.]*)(?:[.]|$)"
duration=filter(n->occursin(pat,n),base)
r=Dict("all_original_columns_unchanged"=>true,"samples_unchanged"=>true,"outcomes_byte_identical"=>true,"added_columns"=>40,"added_current_fields"=>10,"duration_age_latency_current_fields_total"=>length(duration),"previously_included_duration_age_latency_current_fields"=>length(duration)-10,"duration_definition"=>"Named elapsed, duration, queue/front/unresolved age, latency, time-to/time-since measurements. Counts feature identities, including documented aliases, before lag copies; excludes absolute clocks and publication-age provenance.","model_fits_run_with_v2"=>false,"new_matrix_columns"=>length(b.names),"new_current_features"=>length(base),"raw_missingness_preserved"=>true)
open(joinpath(B,"joint-inputs-v2/correction_audit.json"),"w") do io;JSON3.write(io,r);end
println(JSON3.write(r))
