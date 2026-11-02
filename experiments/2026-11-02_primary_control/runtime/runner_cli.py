"""Offline private-bundle validation only; never connects GPU, authenticates or infers."""
import argparse,json
from pathlib import Path
import control_runner
from operational_config import OperationalConfig

def main():
 p=argparse.ArgumentParser(description=__doc__)
 p.add_argument('--operational-config',required=True,type=Path)
 p.add_argument('--manifest',required=True,type=Path)
 p.add_argument('--manifest-sha256',required=True)
 args=p.parse_args()
 control_runner.configure_operational(OperationalConfig(**json.loads(args.operational_config.read_text())))
 manifest,tasks=control_runner.verify_bundle(args.manifest,args.manifest_sha256)
 print(json.dumps({'status':'OFFLINE_BUNDLE_PASS','tasks':len(tasks),'model_calls':0,'credentials_read':False}))
if __name__=='__main__':main()
