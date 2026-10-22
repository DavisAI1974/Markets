using Test
include("model_rules.jl")
@testset "causal model preparation" begin
    x=[1.0 NaN;3.0 NaN;NaN NaN]
    p=fitprep(x,["measured","not_observed"])
    a=applyprep(p,[NaN 1e9;5.0 1e10])
    @test p.medians[1]==2.0
    @test size(a,2)==2 # measured value and its observed missingness; unseen column unused
    @test a[1,1]==0
    @test a[1,2]==1
    @test size(applyprep(p,[NaN -1e99]),2)==2
    @test !safe_feature("native.book.order_id")
    @test !safe_feature("root.activity.ts_recv_ns")
    @test safe_feature("native.structure.distinct_order_id_count")
    @test safe_feature("native.formation_latency_ns")
    @test numeric_missing_mask([NaN,1.0,Inf])==[1.0,0.0,1.0]
    for anchor in ["last_book_reset","last_f_last_same_side","last_touch_change","last_trade","session_open"], clock in ["event","recv"]
        @test safe_feature("native.activity_since.$anchor.elapsed_$(clock)_ns")
    end
    @test !safe_feature("native.activity_since.last_trade.event_ns")
    @test !safe_feature("native.activity_since.last_trade.recv_ns")
    @test !safe_feature("external.weather.published_ns")
    @test !safe_feature("lifecycle.response.elapsed_event_ns")
    long,short=crossing_returns(3.000,3.002,3.003,3.005)
    @test long≈0.001
    @test short≈-0.005
end
