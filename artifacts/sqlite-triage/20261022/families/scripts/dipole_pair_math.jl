using Statistics

const STEP_NAMES=(:same_direction,:opposite_direction,:left_moved_only,:right_moved_only,:neither_moved)

function present_direction(values,states,rows)
    firstindex=0;lastindex=0
    for i in rows
        states[i]==0 || continue
        firstindex==0 && (firstindex=i)
        lastindex=i
    end
    firstindex==0 || firstindex==lastindex ? "INSUFFICIENT" :
        values[lastindex]>values[firstindex] ? "RISE" :
        values[lastindex]<values[firstindex] ? "FALL" : "FLAT"
end

relation(a,b)=a in ("RISE","FALL") && b in ("RISE","FALL") ?
    (a==b ? "SAME_DIRECTION" : "OPPOSITE_DIRECTION") : "UNRESOLVED"

function source_pair_summary(x,y,sx,sy,clocks,rows;strict_groups=false)
    p=Int[];statepairs=zeros(Int,4,4)
    for i in rows
        statepairs[Int(sx[i])+1,Int(sy[i])+1]+=1
        sx[i]==sy[i]==0 && push!(p,i)
    end
    n=length(p);xx=Float64[x[i] for i in p];yy=Float64[y[i] for i in p]
    reason=n<8 ? "FEWER_THAN_8_OVERLAPPING_PRESENT_VALUES" :
        (all(==(xx[1]),xx) || all(==(yy[1]),yy)) ? "ZERO_VARIANCE" : ""
    pearson=isempty(reason) ? cor(xx,yy) : missing
    counts=zeros(Int,5);skipped=0;gaps=0;crossinstrument=0;backward=0
    for k in 2:n
        a,b=p[k-1],p[k]
        gap=clocks[6,a]<0 || clocks[6,b]<0 || clocks[6,b]!=clocks[6,a]+1
        cross=clocks[2,b]!=clocks[2,a]
        back=clocks[5,b]<clocks[5,a]
        gaps+=gap;crossinstrument+=cross;backward+=back
        if strict_groups && (gap || cross || back)
            skipped+=1;continue
        end
        dx=sign(xx[k]-xx[k-1]);dy=sign(yy[k]-yy[k-1])
        index=dx!=0 && dy!=0 ? (dx==dy ? 1 : 2) : dx!=0 ? 3 : dy!=0 ? 4 : 5
        counts[index]+=1
    end
    dl=present_direction(x,sx,rows);dr=present_direction(y,sy,rows)
    er=relation(dl,dr)
    bothrelation=n<2 ? "UNRESOLVED" : relation(xx[end]>xx[1] ? "RISE" : xx[end]<xx[1] ? "FALL" : "FLAT",
        yy[end]>yy[1] ? "RISE" : yy[end]<yy[1] ? "FALL" : "FLAT")
    step_relation=counts[1]>counts[2] ? "SAME_DIRECTION" : counts[2]>counts[1] ? "OPPOSITE_DIRECTION" : "UNRESOLVED"
    summary=(rows=length(rows),present_overlap=n,pearson=pearson,pearson_reason=reason,
        left_direction=dl,right_direction=dr,endpoint_relation=er,both_present_endpoint_relation=bothrelation,
        same_direction=counts[1],opposite_direction=counts[2],left_moved_only=counts[3],right_moved_only=counts[4],
        neither_moved=counts[5],step_count=sum(counts),skipped_breaks=skipped,nonconsecutive_group_transitions=gaps,
        cross_instrument_transitions=crossinstrument,backward_knownby_transitions=backward,
        step_dominance_relation=step_relation,
        endpoint_step_disagreement=er!="UNRESOLVED" && step_relation!="UNRESOLVED" && er!=step_relation)
    summary,statepairs
end
