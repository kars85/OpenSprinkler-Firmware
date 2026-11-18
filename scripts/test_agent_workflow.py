"""Offline routing checks; no GitHub, Empirica or production writes."""
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

SOURCE = Path(__file__).with_name('agent-workflow.py')

class RoutingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / 'scripts').mkdir()
        target = self.root / 'scripts/agent-workflow.py'
        shutil.copyfile(SOURCE, target)
        subprocess.run(['git', 'init', '-q', str(self.root)], check=True)
        subprocess.run(['git', '-C', str(self.root), 'remote', 'add', 'origin', 'https://github.com/example/test.git'], check=True)
        self.id = '11111111-2222-4333-8444-555555555555'
        self.config = {'name':'test', 'repository':'example/test', 'project_id':self.id, 'skills':[]}
        (self.root / '.agent-workflow.json').write_text(json.dumps(self.config))
        (self.root / '.empirica').mkdir()
        (self.root / '.empirica/project.yaml').write_text('project_id: '+self.id+'\n')
        spec = importlib.util.spec_from_file_location('workflow_test', target)
        self.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.module)

    def local_context(self):
        return patch.object(self.module, 'context', return_value=(self.root, self.config))

    def test_correct_repository(self):
        root, profile = self.module.context()
        self.assertEqual(root, self.root)
        self.assertEqual(profile['project_id'], self.id)

    def test_wrong_repository_is_rejected(self):
        self.config['repository'] = 'example/other'
        (self.root / '.agent-workflow.json').write_text(json.dumps(self.config))
        with self.assertRaisesRegex(RuntimeError, 'destination'):
            self.module.context()

    def test_wrong_identity_is_rejected_before_writing(self):
        (self.root / '.empirica/project.yaml').write_text('project_id: foreign\n')
        with self.local_context(), patch.object(sys, 'argv', ['workflow','finding','--text','test','--session-id','session']), \
             patch.object(self.module.subprocess, 'run') as run:
            with self.assertRaisesRegex(RuntimeError, 'identity mismatch'):
                self.module.main()
        run.assert_not_called()

    def test_finding_requires_explicit_session(self):
        with self.local_context(), patch.object(sys, 'argv', ['workflow','finding','--text','test']), \
             patch.object(self.module.subprocess, 'run') as run:
            with self.assertRaises(SystemExit) as result:
                self.module.main()
        self.assertEqual(result.exception.code, 2)
        run.assert_not_called()

    def test_finding_routes_project_and_session(self):
        with self.local_context(), patch.object(sys, 'argv', ['workflow','finding','--text','safe test','--session-id','my-session']), \
             patch.object(self.module.subprocess, 'run', return_value=subprocess.CompletedProcess([],0)) as run:
            with self.assertRaises(SystemExit) as result:
                self.module.main()
        self.assertEqual(result.exception.code, 0)
        command=run.call_args.args[0]
        self.assertEqual(command[command.index('--project-id')+1],self.id)
        self.assertEqual(command[command.index('--session-id')+1],'my-session')
        self.assertNotIn('--global', command)

    def test_fresh_checkout_bootstraps_same_identity(self):
        (self.root / '.empirica/project.yaml').unlink()
        calls=[]
        def execute(command, **kwargs):
            calls.append(command)
            if command[1]=='project-init':
                (self.root / '.empirica/project.yaml').write_text('project_id: '+self.id+'\n')
            return subprocess.CompletedProcess(command,0)
        with self.local_context(), patch.object(sys, 'argv', ['workflow','bootstrap']), patch.object(self.module.subprocess, 'run', side_effect=execute):
            with self.assertRaises(SystemExit) as result:
                self.module.main()
        self.assertEqual(result.exception.code, 0)
        self.assertEqual([c[1] for c in calls],['project-init','project-bootstrap'])
        self.assertTrue(all(c[c.index('--project-id')+1]==self.id for c in calls))

if __name__ == '__main__':
    unittest.main()
