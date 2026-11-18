#!/usr/bin/env python3
"""Project routing and Empirica entrypoint. Run from any directory in this checkout."""
import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import uuid

def context():
    root = Path(__file__).resolve().parents[1]
    config = json.loads((root / '.agent-workflow.json').read_text())
    uuid.UUID(config['project_id'])
    actual = subprocess.check_output(['git', '-C', str(root), 'rev-parse', '--show-toplevel'], text=True).strip()
    if Path(actual).resolve() != root:
        raise RuntimeError('Workflow file is outside its owning Git checkout')
    origin = subprocess.check_output(['git', '-C', str(root), 'remote', 'get-url', 'origin'], text=True).strip()
    match = re.fullmatch(r'(?:https://github\.com/|git@github\.com:)([^/]+/[^/]+?)(?:\.git)?', origin)
    if not match or match[1].lower() != config['repository'].lower():
        raise RuntimeError('GitHub destination does not match this checkout origin')
    return root, config

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['verify', 'status', 'bootstrap', 'session', 'finding', 'search'])
    parser.add_argument('--text')
    parser.add_argument('--session-id')
    args = parser.parse_args()
    root, config = context()
    if args.action == 'status':
        print(json.dumps(config, indent=2)); return
    project = root / '.empirica/project.yaml'
    if not project.exists():
        if args.action != 'bootstrap':
            raise RuntimeError('Run bootstrap to initialize this checkout under its existing project identity')
        subprocess.run(['empirica','project-init','--project-id',config['project_id'],
                        '--project-name',config['name'],'--non-interactive','--output','json'],cwd=root,check=True)
    found = re.search(r'^project_id:\s*[\'\"]?([\w-]+)', project.read_text(), re.M)
    if not found or found[1] != config['project_id']:
        raise RuntimeError('Empirica identity mismatch; do not write into another project')
    if args.action == 'verify':
        for name in config['skills']:
            for base in ['skills', '.agents/skills', '.claude/skills']:
                if not (root / base / name / 'SKILL.md').is_file():
                    raise RuntimeError('Missing skill entrypoint: '+base+'/'+name)
        for path in ['.claude/commands/abc.md','.claude/commands/intake.md','docs/agent-workflow.md']:
            if not (root/path).is_file():raise RuntimeError('Missing workflow file: '+path)
        print(json.dumps({'ok':True,'repository':config['repository'],'project_id':config['project_id']})); return
    if args.action in ['finding','search'] and not args.text:
        parser.error('--text is required for '+args.action)
    if args.action == 'finding' and not args.session_id:
        parser.error('--session-id from this conversation is required for finding')
    commands = {
      'bootstrap':['project-bootstrap','--include-live-state','--depth','minimal'],
      'session':['session-create','--ai-id','workflow'],
      'finding':['finding-log','--session-id',args.session_id or '', '--finding',args.text or '', '--scope','project','--visibility','local','--epistemic-source','search'],
      'search':['project-search','--task',args.text or '', '--type','focused','--limit','5']}
    env = dict(os.environ, EMPIRICA_PROJECT_ID=config['project_id'])
    result = subprocess.run(['empirica',*commands[args.action],'--project-id',config['project_id'],'--output','json'],cwd=root,env=env)
    raise SystemExit(result.returncode)

if __name__ == '__main__':
    try:main()
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
        print('Workflow error: '+str(error),file=sys.stderr);sys.exit(1)
