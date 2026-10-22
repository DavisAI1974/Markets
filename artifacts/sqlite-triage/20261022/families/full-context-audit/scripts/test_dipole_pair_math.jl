using Test
include("dipole_pair_math.jl")

@testset "Source-defined dipole checks and explicit continuity sensitivity" begin
    clocks=zeros(Int64,7,4);clocks[2,:].=7;clocks[5,:]=[1,2,3,4];clocks[6,:]=[0,1,2,3]
    s=UInt8[0,0,0,0];x=[0.,1.,2.,3.];y=[3.,2.,1.,0.]
    a,_=source_pair_summary(x,y,s,s,clocks,1:4)
    @test a.opposite_direction==3 && a.same_direction==0 && a.present_overlap==4
    @test a.endpoint_relation=="OPPOSITE_DIRECTION"
    @test ismissing(a.pearson) && a.pearson_reason=="FEWER_THAN_8_OVERLAPPING_PRESENT_VALUES"
    # Original classroom definition compresses PRESENT observations across gaps.
    missing=UInt8[0,1,0,0]
    b,_=source_pair_summary(x,y,missing,s,clocks,1:4)
    c,_=source_pair_summary(x,y,missing,s,clocks,1:4;strict_groups=true)
    @test b.step_count==2 && b.nonconsecutive_group_transitions==1
    @test c.step_count==1 && c.skipped_breaks==1
    clocks[2,4]=8
    d,_=source_pair_summary(x,y,s,s,clocks,1:4;strict_groups=true)
    @test d.skipped_breaks==1 && d.cross_instrument_transitions==1
    z,states=source_pair_summary(zeros(4),zeros(4),s,s,clocks,1:4)
    @test z.present_overlap==4 && z.neither_moved==3 && states[1,1]==4
    u,_=source_pair_summary(x,y,fill(UInt8(1),4),s,clocks,1:4)
    @test u.present_overlap==0 && u.left_direction=="INSUFFICIENT" && u.step_count==0
    @test relation("FLAT","RISE")=="UNRESOLVED"
end
