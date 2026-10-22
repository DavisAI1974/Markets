using Test
include("external_classroom_math.jl")
@testset "Exact external classroom alignment" begin
    t=Int64(1697662799696377528)
    known=[(published_ns=t,state=0,value=2.),(published_ns=t,state=1,value=nothing),
           (published_ns=t+1,state=2,value=nothing),(published_ns=t+2,state=0,value=0.)]
    values,states,indices=align_external_known(known,[t-1,t,t+1,t+2])
    @test indices==[0,2,3,4]
    @test states==[1,1,2,0]
    @test all(isnan,values[1:3])
    @test values[4]==0.
    @test_throws AssertionError align_external_known(reverse(known),[t])
end
