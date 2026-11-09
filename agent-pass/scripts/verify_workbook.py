"""Verify exported cell values, exact text clocks, and workbook row totals."""
from common import ROOT
import json,math
from openpyxl import load_workbook

source=json.loads((ROOT/'cache/workbook-input.json').read_text())
book=load_workbook(ROOT/'research-tables.xlsx',read_only=True,data_only=False)
assert len(book.worksheets)==len(source)
rows=0;clocks=0
for sheet,table in zip(book.worksheets,source):
    expected=[table['columns'],*table['rows']]
    actual_rows=list(sheet.iter_rows(max_col=len(table['columns']),values_only=True))
    assert len(actual_rows)==len(expected),(sheet.title,len(actual_rows),len(expected))
    for index,(actual,wanted) in enumerate(zip(actual_rows,expected)):
        assert len(actual)==len(wanted)
        for column,(a,b) in enumerate(zip(actual,wanted)):
            if isinstance(b,(int,float)) and not isinstance(b,bool):
                assert isinstance(a,(int,float)) and math.isclose(a,b,rel_tol=1e-14,abs_tol=1e-12),(sheet.title,index,column,a,b)
            else:assert a==b,(sheet.title,index,column,a,b)
            if index and table['columns'][column].endswith('_ns') and b is not None:
                assert isinstance(a,str) and a.startswith("'"),(sheet.title,index,column,a)
                clocks+=1
        rows+=int(index>0)
print('Verified workbook:',len(source),'sheets,',rows,'source rows,',clocks,'exact text clocks')
