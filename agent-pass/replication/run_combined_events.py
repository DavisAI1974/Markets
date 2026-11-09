"""Run the selected combined study stage with verified saved exact-clock inputs."""
import argparse,pathlib,tempfile
from event_common import Context
import event_chronology

def main():
    p=argparse.ArgumentParser();p.add_argument("--day",required=True);p.add_argument("--output",type=pathlib.Path,required=True)
    a=p.parse_args()
    with tempfile.TemporaryDirectory() as t:
        ctx=Context(a.day,a.output,pathlib.Path(t))
        event_chronology.tests();event_chronology.study(ctx)
        ctx.finish()
        print(ctx.summary,flush=True)
if __name__=="__main__":main()
