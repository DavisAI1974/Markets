# Add separately labelled, actually published station/measurement observations.
# Never replace the latest source report's M value with an unstamped value.
using CSV,DataFrames,SQLite,DBInterface,JSON3,Statistics
const BASE=get(ENV,"FAMILY_RESEARCH_DIR","/opt/frankie-box/work/family-research-20261022")
const OUT=joinpath(BASE,"descriptive-v1")
db=SQLite.DB(joinpath(BASE,"alignment.sqlite"));DBInterface.execute(db,"PRAGMA query_only=ON")
samples=CSV.read(joinpath(OUT,"samples.csv"),DataFrame)
source=DataFrame(DBInterface.execute(db,"SELECT * FROM external_row WHERE point_name='weather.obs_hourly' ORDER BY published_ns,source_ordinal"))
fields=["alti","drct","dwpf","feel","gust","ice_accretion_1hr","ice_accretion_3hr","ice_accretion_6hr","mslp","p01i","peak_wind_drct","peak_wind_gust","relh","sknt","skyl1","skyl2","skyl3","skyl4","snowdepth","tmpf","vsby"]
stations=Set{String}();history=Dict{Tuple{String,String},Vector{Tuple{Int64,Int64,Union{Missing,Int64},Float64}}}()
for r in eachrow(source)
    j=JSON3.read(r.row_json);station=String(j["station"]);push!(stations,station)
    for field in fields
        v=get(j,field,nothing)
        v=v isa AbstractString ? tryparse(Float64,v) : v
        v isa Real && isfinite(v) || continue
        push!(get!(history,(station,field),Tuple{Int64,Int64,Union{Missing,Int64},Float64}[]),(r.published_ns,r.source_ordinal,r.event_time_ns,Float64(v)))
    end
end
rows=NamedTuple[];coverage=NamedTuple[]
for station in sort(collect(stations)), field in fields
    h=get(history,(station,field),Tuple{Int64,Int64,Union{Missing,Int64},Float64}[])
    times=[r[1] for r in h]
    for s in eachrow(samples)
        i=searchsortedlast(times,s.cutoff_ns-1)
        push!(rows,(sample_id=s.sample_id,feature="external_last_observed.weather.obs_hourly|station="*station*"."*field,station=station,measurement=field,value=i==0 ? missing : h[i][4],published_ns=i==0 ? missing : h[i][1],event_time_ns=i==0 ? missing : h[i][3],source_ordinal=i==0 ? missing : h[i][2],publication_age_s=i==0 ? missing : (s.cutoff_ns-h[i][1])/1e9,event_age_s=i==0 || ismissing(h[i][3]) ? missing : (s.cutoff_ns-h[i][3])/1e9,disposition=i==0 ? "no earlier numerical observation in pinned source" : "historical published observation; not current report value"))
    end
end
df=DataFrame(rows);CSV.write(joinpath(OUT,"external_last_observed_measurements.csv"),df)
df=leftjoin(df,select(samples,:sample_id,:phase);on=:sample_id)
for g in groupby(df,[:station,:measurement,:phase])
    ages=collect(skipmissing(g.publication_age_s))
    push!(coverage,(station=g.station[1],measurement=g.measurement[1],phase=g.phase[1],master_n=nrow(g),available_n=count(!ismissing,g.value),missing_n=count(ismissing,g.value),median_publication_age_s=isempty(ages) ? missing : median(ages),max_publication_age_s=isempty(ages) ? missing : maximum(ages)))
end
CSV.write(joinpath(OUT,"input_last_observed_weather_availability.csv"),DataFrame(coverage))
println(JSON3.write(Dict("stations"=>length(stations),"measurements_per_station"=>length(fields),"added_observation_rows"=>nrow(df),"policy"=>"Same-station, same-field, actually published historical measurement; timestamp, age, source ordinal retained; latest-report missingness remains unchanged; no interpolation or future backfill.")))
