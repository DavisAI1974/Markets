using Test
include("descriptive_math.jl")
@testset "Exact observable boundaries" begin
    t = Int64(1697581826400392980)
    keys = [(t-1, 3), (t, 4), (t, 8), (t+1, 9)]
    @test asof_index(keys, t, 5) == 2
    @test asof_index(keys, t-1, 2) == 0
    @test asof_index(keys, t, 4) == 2
    @test asof_index([(t-2,1),(t-1,10)],t,3) == 1
    @test ismissing(observed_change([t,t+10], [1.0,2.0], t, t+11))
    @test ismissing(observed_change([t,t+10], [1.0,2.0], t-1, t+10))
    @test observed_change([t,t+10], [1.0,2.0], t, t+10) == 1.0
    @test ismissing(component_value(Dict("value"=>0.0,"state"=>1,"reason"=>"NOT_F_LAST")))
    @test component_value(Dict("value"=>0.0,"state"=>0,"reason"=>"OK")) == 0.0
end
