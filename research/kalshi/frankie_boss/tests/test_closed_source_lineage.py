"""New lineage binding seams; tiny closed databases, no model/source replay."""
import json
import sqlite3
import pytest
from research.kalshi.frankie_boss.closed_source_lineage import build_closed_lineage,sha256


def case(tmp_path):
    def parent(name,count):
        p=tmp_path/(name+'.sqlite');c=sqlite3.connect(p)
        c.execute('CREATE TABLE entries(ordinal INTEGER,digest TEXT)')
        c.execute('INSERT INTO entries VALUES(?,?)',(count-1,name*64));c.commit();c.close()
        return dict(path=str(p),sha256=sha256(p),count=count,head_hash=name*64)
    oldest=parent('a',3);middle=parent('b',8);final=tmp_path/'final'/'source.sqlite';final.parent.mkdir()
    links=[]
    for i,(child,pin) in enumerate(((final,middle),(middle['path'],oldest))):
        receipt=dict(schema='C15_EXPLICIT_SOURCE_RECOVERY_V1',existing_entries_rewritten=0,recovered_path=str(child),parent_path=pin['path'],parent={k:pin[k] for k in ('sha256','count','head_hash')},journal_count=4,journal_hash='c'*64)
        path=tmp_path/f'recovery-{i}.json';path.write_text(json.dumps(receipt))
        links.append(dict(recovery_receipt=dict(path=str(path),sha256=sha256(path)),closed_parent=pin))
    ingestion=final.parent/'ingestion-receipt.json';ingestion.write_text(json.dumps(dict(recovery_receipt_sha256=links[0]['recovery_receipt']['sha256'])))
    return dict(final_source_path=final,ingestion_receipt=ingestion,expected_ingestion_sha256=sha256(ingestion),links=links)


def test_failed_fork_lineage_uses_closed_parent_not_old_initial_head(tmp_path):
    args=case(tmp_path);result=build_closed_lineage(**args)
    assert result['schema']=='FRANKIE_CLOSED_SOURCE_LINEAGE_V1'
    assert [v['closed_parent']['count'] for v in result['links']]==[8,3]
    assert not args['final_source_path'].exists()  # active/final database is never opened


@pytest.mark.parametrize('defect',['order','receipt_pin','parent_tail','failure'])
def test_lineage_refuses_broken_independent_binding(tmp_path,defect):
    args=case(tmp_path)
    if defect=='order':args['links'].reverse()
    elif defect=='receipt_pin':args['links'][1]['recovery_receipt']['sha256']='f'*64
    elif defect=='parent_tail':
        p=args['links'][1]['closed_parent'];db=sqlite3.connect(p['path']);db.execute('UPDATE entries SET ordinal=8');db.commit();db.close()
    else:(args['final_source_path'].parent/'failure.json').write_text('{}')
    with pytest.raises(ValueError):build_closed_lineage(**args)


def test_rehashed_receipt_cannot_override_actual_closed_tail(tmp_path):
    args=case(tmp_path);link=args['links'][1]
    link['closed_parent']['count']=99
    path=link['recovery_receipt']['path']
    from pathlib import Path
    value=json.loads(Path(path).read_text());value['parent']['count']=99
    Path(path).write_text(json.dumps(value));link['recovery_receipt']['sha256']=sha256(path)
    with pytest.raises(ValueError,match='tail differs'):build_closed_lineage(**args)
