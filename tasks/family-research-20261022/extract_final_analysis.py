"""Read the scientific-table prefix of the saved archive without copying weights."""
import argparse,hashlib,json,pathlib,tarfile,time,urllib.request

def main():
    p=argparse.ArgumentParser();p.add_argument('--url-file',type=pathlib.Path,required=True)
    p.add_argument('--output',type=pathlib.Path,required=True);a=p.parse_args()
    url=a.url_file.read_text().strip();a.output.mkdir(parents=True,exist_ok=True)
    expected='fa195668b0d9ca489639efb60b0c07596c55865dab82d449ba04663a027b6d5d'
    expected_bytes=20696923225
    class Reader:
        def __init__(self,response):self.response=response;self.sha=hashlib.sha256();self.n=0;self.last=time.monotonic()
        def read(self,n=-1):
            data=self.response.read(n);self.sha.update(data);self.n+=len(data)
            if time.monotonic()-self.last>30:
                print(json.dumps(dict(progress_compressed_bytes=self.n,total=expected_bytes)),flush=True);self.last=time.monotonic()
            return data
    selected=[];skipped=[];total=0
    with urllib.request.urlopen(url,timeout=120) as response:
        assert int(response.headers['Content-Length'])==expected_bytes
        reader=Reader(response)
        with tarfile.open(fileobj=reader,mode='r|gz') as archive:
            for member in archive:
                name=pathlib.PurePosixPath(member.name)
                if name.parts and name.parts[0]=='parallel-63':break
                if len(name.parts)!=1 or name.name in ('','..','.'):continue
                if not member.isfile():
                    skipped.append(dict(name=member.name,reason='not_regular'));continue
                if name.suffix not in ('.csv','.json','.log','.md','.txt'):
                    skipped.append(dict(name=member.name,size=member.size,reason='non_analysis_extension'));continue
                if member.size>512*1024**2 or total+member.size>3*1024**3:
                    skipped.append(dict(name=member.name,size=member.size,reason='bounded_analysis_transport'));continue
                destination=a.output/name.name
                assert not destination.exists(),str(destination)
                sha=hashlib.sha256()
                with archive.extractfile(member) as src,destination.open('wb') as dest:
                    while block:=src.read(1024**2):dest.write(block);sha.update(block)
                assert destination.stat().st_size==member.size
                total+=member.size;selected.append(dict(name=name.name,bytes=member.size,sha256=sha.hexdigest()))
                print(json.dumps(dict(saved=name.name,bytes=member.size)),flush=True)
                (a.output/'transport-progress.json').write_text(json.dumps(dict(selected=selected,skipped=skipped),indent=2)+'\n')
    (a.output/'transport-prefix.json').write_text(json.dumps(dict(source_archive_sha256_verified_by_callback=expected,
        source_archive_bytes=expected_bytes,compressed_prefix_bytes=reader.n,status='scientific_prefix_read',
        full_archive_rehashed=False,retained_analysis_bytes=total,selected=selected,skipped=skipped),indent=2)+'\n')
    a.url_file.unlink()
    print(json.dumps(dict(status='scientific_prefix_read',files=len(selected),bytes=total)),flush=True)

if __name__=='__main__':main()
