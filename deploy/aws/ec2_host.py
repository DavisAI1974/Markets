"""Status, start or stop one EC2 host, waiting for the state and for SSM to come online.

    python deploy/aws/ec2_host.py --instance i-... status|start|stop [--env-file scratchpad/aws.env]

Prints the instance state, type, KeepRunning tag, hours since launch and the approximate cost at
--hourly (default 3.60, the r7i.8xlarge Windows rate since the 2026-09-17 resize). Never prints a credential. `start` waits
until the SSM agent reports Online so a runner can follow immediately; `stop` waits until stopped.
"""
import argparse
import datetime
import os
import re
import sys
import time


def load_env_file(path):
    for line in open(path, encoding='utf-8', errors='replace'):
        m = re.match(r'\s*(?:export\s+)?([A-Z_]+)\s*=\s*"?([^"\n]+)"?', line)
        if m and m.group(1).startswith('AWS_'):
            os.environ[m.group(1)] = m.group(2).strip()


def describe(ec2, instance):
    r = ec2.describe_instances(InstanceIds=[instance])['Reservations'][0]['Instances'][0]
    tags = {t['Key']: t['Value'] for t in r.get('Tags', [])}
    return dict(state=r['State']['Name'], type=r['InstanceType'], launch=r['LaunchTime'],
                keep_running=tags.get('KeepRunning'), profile=r.get('IamInstanceProfile', {}).get('Arn', '').split('/')[-1])


def report(info, hourly):
    hours = (datetime.datetime.now(datetime.timezone.utc) - info['launch']).total_seconds() / 3600
    print(f"state={info['state']} type={info['type']} KeepRunning={info['keep_running']} profile={info['profile']} "
          f"since_launch={hours:.2f}h approx_cost=${hours * hourly:.2f} (at ${hourly}/h, counted only while running)")


def wait_state(ec2, instance, wanted, seconds=600):
    deadline = time.time() + seconds
    while time.time() < deadline:
        state = describe(ec2, instance)['state']
        if state == wanted:
            return state
        time.sleep(10)
    raise SystemExit(f'instance did not reach {wanted} within {seconds}s')


def wait_ssm(ssm, instance, seconds=600):
    deadline = time.time() + seconds
    while time.time() < deadline:
        info = ssm.describe_instance_information(Filters=[{'Key': 'InstanceIds', 'Values': [instance]}])['InstanceInformationList']
        if info and info[0]['PingStatus'] == 'Online':
            return info[0].get('PlatformName', '')
        time.sleep(10)
    raise SystemExit(f'SSM agent not Online within {seconds}s')


def report_frankie_access(ec2, ssm, instance):
    """Read control-plane recovery evidence without dispatching a host command."""
    import json
    from botocore.exceptions import ClientError
    def emit(kind, value):
        print(kind + ' ' + json.dumps(value, default=str, sort_keys=True), flush=True)
    host = ec2.describe_instances(InstanceIds=[instance])['Reservations'][0]['Instances'][0]
    emit('ACCESS_HOST', {key: host.get(key) for key in (
        'InstanceId', 'State', 'PublicIpAddress', 'PrivateIpAddress', 'SubnetId',
        'VpcId', 'KeyName', 'SecurityGroups', 'BlockDeviceMappings')})
    emit('SSM_AGENT', [{key: row.get(key) for key in (
        'InstanceId', 'PingStatus', 'LastPingDateTime', 'AgentVersion', 'PlatformName')}
        for row in ssm.describe_instance_information(
            Filters=[{'Key': 'InstanceIds', 'Values': [instance]}])['InstanceInformationList']])
    for command in ('00d2cb24-815f-4aeb-8d91-2048ba862098',
                    'c5b13e53-0db5-4d68-8049-9994e3e0ce16',
                    '45ee9699-936c-4872-998e-12465406c9ea'):
        try:
            inv = ssm.get_command_invocation(CommandId=command, InstanceId=instance)
            fields = {key: inv.get(key) for key in (
                'CommandId', 'Status', 'StatusDetails', 'ResponseCode',
                'ExecutionStartDateTime', 'ExecutionEndDateTime')}
            fields['stdout_chars'] = len(inv.get('StandardOutputContent', ''))
            fields['stderr_chars'] = len(inv.get('StandardErrorContent', ''))
            emit('SSM_INVOCATION', fields)
            rows = ssm.list_command_invocations(CommandId=command, InstanceId=instance, Details=True)
            for row in rows['CommandInvocations']:
                emit('SSM_DETAIL', {key: row.get(key) for key in (
                    'CommandId', 'Status', 'StatusDetails', 'TraceOutput')})
                for plugin in row.get('CommandPlugins', []):
                    emit('SSM_PLUGIN', {key: plugin.get(key) for key in (
                        'Name', 'Status', 'StatusDetails', 'ResponseCode',
                        'ResponseStartDateTime', 'ResponseFinishDateTime')})
        except ClientError as exc:
            emit('ACCESS_ERROR', {'command': command, 'code': exc.response['Error']['Code']})
    peers = ec2.describe_instances(Filters=[
        {'Name': 'vpc-id', 'Values': [host['VpcId']]},
        {'Name': 'instance-state-name', 'Values': ['running']}])
    emit('ACCESS_PEERS', [{key: row.get(key) for key in (
        'InstanceId', 'PrivateIpAddress', 'SecurityGroups', 'PlatformDetails')}
        for reservation in peers['Reservations'] for row in reservation['Instances']])
    emit('SSM_MANAGED', [{key: row.get(key) for key in (
        'InstanceId', 'PingStatus', 'PlatformName')}
        for row in ssm.describe_instance_information()['InstanceInformationList']])
    volumes = ec2.describe_volumes(VolumeIds=[x['Ebs']['VolumeId']
                                            for x in host['BlockDeviceMappings']])
    emit('ACCESS_VOLUMES', [{key: row.get(key) for key in (
        'VolumeId', 'Size', 'VolumeType', 'State')} for row in volumes['Volumes']])
    groups = ec2.describe_security_groups(GroupIds=[x['GroupId'] for x in host['SecurityGroups']])
    emit('ACCESS_INGRESS', [{'id': x['GroupId'], 'rules': x['IpPermissions']}
                            for x in groups['SecurityGroups']])
    for label, call, kwargs in (
        ('SERIAL_ACCESS', ec2.get_serial_console_access_status, {}),
        ('EIC_ENDPOINTS', ec2.describe_instance_connect_endpoints,
         {'Filters': [{'Name': 'vpc-id', 'Values': [host['VpcId']]}]})):
        try:
            result = call(**kwargs)
            if label == 'SERIAL_ACCESS':
                emit(label, {'enabled': result.get('SerialConsoleAccessEnabled')})
            else:
                emit(label, [{key: x.get(key) for key in (
                    'InstanceConnectEndpointId', 'State', 'SubnetId', 'SecurityGroupIds')}
                    for x in result.get('InstanceConnectEndpoints', [])])
        except ClientError as exc:
            emit('ACCESS_ERROR', {'operation': label, 'code': exc.response['Error']['Code']})


def inspect_frankie_over_ssh(ec2, instance, region):
    """One read-only host command; remove this operation's temporary access on exit."""
    import base64
    import hashlib
    import ipaddress
    import json
    import pathlib
    import subprocess
    import tempfile
    import urllib.request
    import uuid
    import boto3
    if instance != 'i-035994afa8bdf66a5' or region != 'us-east-1':
        raise SystemExit('canonical Frankie box required')
    def emit(kind, value):
        print(kind + ' ' + json.dumps(value, sort_keys=True), flush=True)
    host=ec2.describe_instances(InstanceIds=[instance])['Reservations'][0]['Instances'][0]
    if host['State']['Name'] != 'running':
        raise SystemExit('running box required; no start or restart performed')
    address=str(ipaddress.IPv4Address(host['PublicIpAddress']))
    console=ec2.get_console_output(InstanceId=instance,Latest=True).get('Output','')
    host_keys=re.findall(r'(ssh-ed25519|ecdsa-sha2-nistp256|ssh-rsa) ([A-Za-z0-9+/]+={0,3})(?:\s|$)',console)
    if not host_keys:
        try:
            decoded=base64.b64decode(console,validate=True).decode('utf-8',errors='replace')
            host_keys=re.findall(r'(ssh-ed25519|ecdsa-sha2-nistp256|ssh-rsa) ([A-Za-z0-9+/]+={0,3})(?:\s|$)',decoded)
        except (ValueError, UnicodeError):
            pass
    if not host_keys:
        raise SystemExit('No authenticated EC2 console host key available; refusing unverified SSH')
    runner_ip=str(ipaddress.IPv4Address(urllib.request.urlopen(
        'https://checkip.amazonaws.com',timeout=15).read().decode().strip()))
    nic=next(x for x in host['NetworkInterfaces'] if x['Attachment']['DeviceIndex']==0)['NetworkInterfaceId']
    original=sorted(x['GroupId'] for x in ec2.describe_network_interfaces(
        NetworkInterfaceIds=[nic])['NetworkInterfaces'][0]['Groups'])
    group=None
    operation='frankie-recovery-'+uuid.uuid4().hex
    with tempfile.TemporaryDirectory(prefix=operation+'-') as temp:
        key=pathlib.Path(temp)/'access'
        subprocess.run(['ssh-keygen','-q','-t','ed25519','-N','','-f',str(key)],check=True)
        known=pathlib.Path(temp)/'known_hosts'
        known.write_text(''.join(address+' '+kind+' '+value+'\n' for kind,value in host_keys))
        emit('SSH_HOST_KEYS', [hashlib.sha256(base64.b64decode(value)).hexdigest() for kind,value in host_keys])
        eic=boto3.client('ec2-instance-connect',region_name=region)
        def push_key():
            response=eic.send_ssh_public_key(InstanceId=instance,InstanceOSUser='ubuntu',
                AvailabilityZone=host['Placement']['AvailabilityZone'],
                SSHPublicKey=key.with_suffix('.pub').read_text())
            if response.get('Success') is not True:
                raise RuntimeError('Instance Connect key not accepted')
        push_key()
        try:
            group=ec2.create_security_group(GroupName=operation,Description='Temporary exact-runner Frankie recovery SSH',
                                           VpcId=host['VpcId'])['GroupId']
            emit('TEMPORARY_ACCESS_CREATED',dict(group=group,interface=nic,source=runner_ip+'/32',port=22))
            ec2.authorize_security_group_ingress(GroupId=group,IpPermissions=[
                dict(IpProtocol='tcp',FromPort=22,ToPort=22,
                     IpRanges=[dict(CidrIp=runner_ip+'/32',Description=operation)])])
            before=sorted(x['GroupId'] for x in ec2.describe_network_interfaces(
                NetworkInterfaceIds=[nic])['NetworkInterfaces'][0]['Groups'])
            if before!=original:
                raise RuntimeError('network groups changed concurrently; refusing attachment')
            ec2.modify_network_interface_attribute(NetworkInterfaceId=nic,Groups=original+[group])
            actual=sorted(x['GroupId'] for x in ec2.describe_network_interfaces(
                NetworkInterfaceIds=[nic])['NetworkInterfaces'][0]['Groups'])
            if actual!=sorted(original+[group]):
                raise RuntimeError('temporary network access readback differs')
            push_key()
            command=['ssh','-T','-i',str(key),'-o','IdentitiesOnly=yes','-o','BatchMode=yes',
                     '-o','StrictHostKeyChecking=yes','-o','UserKnownHostsFile='+str(known),
                     '-o','ConnectTimeout=20','-o','ServerAliveInterval=15','-o','ServerAliveCountMax=2',
                     'ubuntu@'+address,'sudo -n /opt/frankie-box/venv/bin/python -I -S -B -']
            completed=subprocess.run(command,input="\nimport hashlib,json,os,pathlib,stat,time\nroot=pathlib.Path('/opt/frankie-box/work/monday-calculations/full-20211004-20260927-r1-48')\nassert root.resolve(strict=True)==root\ndef pin(path):\n    raw=path.read_bytes()\n    return dict(path=str(path),bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest(),value=json.loads(raw))\nspace=os.statvfs(root)\nout=dict(at=time.time(),available_bytes=space.f_bavail*space.f_frsize,\n         free_including_reserved_bytes=space.f_bfree*space.f_frsize)\nproc=pathlib.Path('/proc/59092')\nout['pid59092_exists']=proc.exists()\nif proc.exists():\n    fields=(proc/'stat').read_text().rsplit(')',1)[1].split()\n    out['pid59092_state']=fields[0]\n    out['pid59092_token']=pathlib.Path('/proc/sys/kernel/random/boot_id').read_text().strip()+':'+fields[19]\nout['progress']=pin(root/'progress.json')\ncp=root/'work/bedrock/recovery-8c03f629f01747158535f3cfa4f01f2d/checkpoints'\nout['checkpoint']=pin(cp/'checkpoint-000000.json')\nout['descriptor']=pin(cp/'controller-state-000000.json')\nout['targets']=[]\nfor relative in [\"work/bedrock/recovery-03a70711353a433c989b18074d7baacd/ledgers/exact_member_rows.jsonl\",\"work/bedrock/recovery-d4b20c8f7e834d7abb1a435ff8199442/ledgers/exact_member_rows.jsonl\",\"work/bedrock/recovery-7bd18d968a384248b02e58c74f5456c6/ledgers/exact_member_rows.jsonl\",\"work/bedrock/ledgers/exact_member_rows.jsonl\",\"work/bedrock/recovery-f13de5640bf549feaae493d8861bfae1/ledgers/exact_member_rows.jsonl\"]:\n    path=root/relative\n    row=dict(path=str(path),exists=path.exists(),symlink=path.is_symlink())\n    if path.exists():\n        info=path.lstat()\n        row.update(bytes=info.st_size,mtime_ns=info.st_mtime_ns,links=info.st_nlink,\n                   allocated_bytes=info.st_blocks*512,regular=stat.S_ISREG(info.st_mode))\n    out['targets'].append(row)\nout['retention']=[]\nfor directory in sorted((root/'work/retention').glob('superseded-members-*')):\n    row=dict(path=str(directory),files=[])\n    if directory.is_symlink():\n        raise RuntimeError('linked retention directory')\n    for path in sorted(directory.iterdir()):\n        if path.suffix=='.json':\n            row['files'].append(pin(path))\n    out['retention'].append(row)\nprint('RECOVERY_INSPECTION '+json.dumps(out,sort_keys=True),flush=True)\n",text=True,check=False,timeout=180)
            emit('SSH_INSPECTION_EXIT',dict(returncode=completed.returncode))
            if completed.returncode:
                raise SystemExit(completed.returncode)
        finally:
            if group:
                current=sorted(x['GroupId'] for x in ec2.describe_network_interfaces(
                    NetworkInterfaceIds=[nic])['NetworkInterfaces'][0]['Groups'])
                if group in current:
                    ec2.modify_network_interface_attribute(NetworkInterfaceId=nic,
                        Groups=[value for value in current if value!=group])
                after=sorted(x['GroupId'] for x in ec2.describe_network_interfaces(
                    NetworkInterfaceIds=[nic])['NetworkInterfaces'][0]['Groups'])
                if group in after:
                    raise RuntimeError('temporary recovery group still attached')
                from botocore.exceptions import ClientError
                for attempt in range(6):
                    try:
                        ec2.delete_security_group(GroupId=group)
                        break
                    except ClientError as exc:
                        if exc.response['Error']['Code']!='DependencyViolation' or attempt==5:
                            raise
                        time.sleep(2)
                emit('TEMPORARY_ACCESS_REMOVED',dict(group=group,interface=nic,remaining_groups=after))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--instance', required=True)
    parser.add_argument('--region', default='us-east-2')
    parser.add_argument('--env-file')
    parser.add_argument('--hourly', type=float, default=3.60)  # r7i.8xlarge Windows since 2026-09-17 (was 1.80 at r7i.4xlarge)
    parser.add_argument('--label', default='', help='snapshot: short label written into the Name tag')
    parser.add_argument('--device', default='xvdf', help='snapshot: block device of the data volume (E:), default xvdf')
    parser.add_argument('--type', default='', help='resize: the new instance type (r7i.8xlarge = 32 vCPU/256 GiB, r7i.12xlarge = 48 vCPU/384 GiB)')
    parser.add_argument('action', choices=('status', 'start', 'stop', 'snapshot', 'snapshots', 'resize', 'recovery-inspect'))
    args = parser.parse_args()
    if args.env_file:
        load_env_file(args.env_file)
    import boto3
    ec2 = boto3.client('ec2', region_name=args.region)
    ssm = boto3.client('ssm', region_name=args.region)
    info = describe(ec2, args.instance)
    report(info, args.hourly)
    if args.action == 'status' and args.instance == 'i-035994afa8bdf66a5' and args.region == 'us-east-1':
        report_frankie_access(ec2, ssm, args.instance)
    if args.action == 'recovery-inspect':
        inspect_frankie_over_ssh(ec2, args.instance, args.region)
    if args.action == 'start':
        if info['state'] == 'stopping':
            wait_state(ec2, args.instance, 'stopped')
        if describe(ec2, args.instance)['state'] == 'stopped':
            ec2.start_instances(InstanceIds=[args.instance])
        wait_state(ec2, args.instance, 'running')
        print('SSM Online:', wait_ssm(ssm, args.instance))
    elif args.action == 'stop':
        if info['state'] in ('running', 'pending'):
            ec2.stop_instances(InstanceIds=[args.instance])
        wait_state(ec2, args.instance, 'stopped')
        report(describe(ec2, args.instance), args.hourly)
    elif args.action == 'resize':
        # Instance type changes only while STOPPED (EC2 refuses otherwise); the volumes, the SSM profile
        # and the KeepRunning tag are untouched. The compact reader's data_workers=48 is a cap, so a larger
        # type simply yields more dedicated worker CPUs (vCPUs minus the reserved consumer CPU).
        if not args.type:
            raise SystemExit('resize requires --type')
        if info['state'] != 'stopped':
            raise SystemExit(f"resize requires a stopped instance; state={info['state']} (run stop first)")
        if info['type'] == args.type:
            print(f'already {args.type}; nothing changed')
        else:
            ec2.modify_instance_attribute(InstanceId=args.instance, InstanceType={'Value': args.type})
            after = describe(ec2, args.instance)
            if after['type'] != args.type:
                raise SystemExit(f"resize did not take: type={after['type']}")
            print(f"resized {info['type']} -> {after['type']} (stopped; starts at the new size on the next start)")
            report(after, args.hourly)
    elif args.action == 'snapshot':
        # Point-in-time EBS snapshot of the data volume: survives terminate, corruption and a bad cycle.
        # Taken while STOPPED it is crash-consistent by construction; while running it is still consistent
        # for files not being written. Incremental: only changed blocks are stored after the first.
        r = ec2.describe_instances(InstanceIds=[args.instance])['Reservations'][0]['Instances'][0]
        volumes = {m['DeviceName'].replace('/dev/', ''): m['Ebs']['VolumeId'] for m in r['BlockDeviceMappings']}
        if args.device not in volumes:
            raise SystemExit(f'device {args.device} not attached; attached: {sorted(volumes)}')
        name = f"{args.instance}-{args.device}-{datetime.datetime.now(datetime.timezone.utc):%Y%m%dT%H%M%SZ}" + (f'-{args.label}' if args.label else '')
        snap = ec2.create_snapshot(VolumeId=volumes[args.device], Description=name,
                                   TagSpecifications=[{'ResourceType': 'snapshot', 'Tags': [{'Key': 'Name', 'Value': name},
                                                       {'Key': 'Instance', 'Value': args.instance}, {'Key': 'Device', 'Value': args.device}]}])
        print(f"snapshot {snap['SnapshotId']} of {volumes[args.device]} ({args.device}) started, state={snap['State']}, name={name}")
        deadline = time.time() + 3600
        while time.time() < deadline:
            state = ec2.describe_snapshots(SnapshotIds=[snap['SnapshotId']])['Snapshots'][0]
            if state['State'] == 'completed':
                print(f"snapshot {snap['SnapshotId']} completed, {state['VolumeSize']} GiB volume"); break
            if state['State'] == 'error':
                raise SystemExit('snapshot failed')
            time.sleep(15)
    elif args.action == 'snapshots':
        snaps = ec2.describe_snapshots(Filters=[{'Name': 'tag:Instance', 'Values': [args.instance]}])['Snapshots']
        for s_ in sorted(snaps, key=lambda x: x['StartTime']):
            tags = {t['Key']: t['Value'] for t in s_.get('Tags', [])}
            print(f"{s_['SnapshotId']} {s_['StartTime']:%Y-%m-%dT%H:%MZ} {s_['State']:9} {s_['VolumeSize']:4} GiB {tags.get('Name','')}")
    return 0


if __name__ == '__main__':
    sys.exit(main())
