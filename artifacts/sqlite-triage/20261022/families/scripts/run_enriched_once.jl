# Freeze all available inputs before entering this single enriched analysis batch.
using JSON3
base=get(ENV,"FAMILY_RESEARCH_DIR","/opt/frankie-box/work/family-research-20261022")
out=get(ENV,"FAMILY_ANALYSIS_OUT",joinpath(base,"enriched-v2"))
ready=JSON3.read(read(joinpath(out,"all_additions_ready.json"),String))
@assert ready["all_agreed_areas_accounted_for"] && ready["families"]==749
@assert ready["structural_counter_mismatches"]==0
for name in ["enriched_context_measurements.csv","quote_windows.csv","remaining_gaps.csv","enrichment_receipt.json"]
    @assert isfile(joinpath(out,name))
end
module EnrichedAssociations
include("summarize_descriptive.jl")
end
module EnrichedContextChanges
include("compare_context_changes.jl")
end
module EnrichedCoverage
include("report_descriptive.jl")
end
module EnrichedQuoteComparison
include("report_quote_comparison.jl")
end
println("ENRICHED_ALL_ADDITIONS_ANALYSIS_COMPLETE")
