#!/usr/bin/env python3
import importlib.util,json,os
from pathlib import Path
import sys,tempfile,unittest
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT))
class RepairTests(unittest.TestCase):
 def module(self):
  self.assertTrue((ROOT/'codex_repair.py').exists(),'Repair worker missing')
  spec=importlib.util.spec_from_file_location('repair_test',ROOT/'codex_repair.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
 def test_sanitizes_context_and_requires_repeated_real_failure(self):
  m=self.module()
  with tempfile.TemporaryDirectory() as td:
   r=m.CodexRepair(Path(td),root=ROOT)
   state={'map':'s450','x':1,'y':2,'password':'SECRET','username':'PRIVATE','main_quest':{'chapter':5,'step':3},'dialogue':{'text':'SECRET'}}
   context=m.repair_context('action_failed',state,{'chapter':5,'step':3},'RuntimeError')
   self.assertNotIn('SECRET',json.dumps(context));self.assertNotIn('PRIVATE',json.dumps(context))
   for reason in ['battle_wait','focus_lost','stale_state','story_choice']:
    self.assertFalse(r.observe(m.repair_context(reason,state,{})))
   self.assertFalse(r.observe(context));self.assertFalse(r.observe(context));self.assertTrue(r.observe(context))
 def test_fake_worker_flags_verification_restart_and_attempt_persistence(self):
  m=self.module()
  with tempfile.TemporaryDirectory() as td:
   root=Path(td);(root/'autoplay.py').write_text('old');session=root/'session';session.mkdir();calls=[]
   class Process:
    pid=987
    def poll(self):return 0
   def popen(command,**kwargs):
    calls.append((command,kwargs));self.assertIn('Repair only',kwargs['stdin'].read());(root/'autoplay.py').write_text('fixed');return Process()
   class Verified:returncode=0
   r=m.CodexRepair(session,root=root,popen=popen,run=lambda *a,**k:Verified())
   context=m.repair_context('action_failed',{'map':'s450'}, {},'RuntimeError')
   with patch.dict(os.environ,{'DW3_PASSWORD':'SECRET'}):result=r.repair(context)
   self.assertTrue(result['restart']);command,kwargs=calls[0]
   self.assertIn('--sandbox',command);self.assertIn('workspace-write',command);self.assertIn('--ask-for-approval',command);self.assertIn('on-request',command);self.assertIn('approvals_reviewer=auto_review',command);self.assertEqual(kwargs['cwd'],str(root));self.assertNotIn('DW3_PASSWORD',kwargs['env']);self.assertEqual(command[-1],'-')
   self.assertFalse(m.CodexRepair(session,root=root).eligible(context))
   other=m.repair_context('unknown_action',{'map':'other'}, {})
   self.assertFalse(m.CodexRepair(session,root=root).eligible(other))
 def test_failure_or_unchanged_worker_never_restarts(self):
  m=self.module()
  with tempfile.TemporaryDirectory() as td:
   root=Path(td);(root/'autoplay.py').write_text('unchanged');(root/'session').mkdir()
   class Process:
    pid=988
    def poll(self):return 0
   r=m.CodexRepair(root/'session',root=root,popen=lambda *a,**k:Process(),run=lambda *a,**k:self.fail('Must not verify unchanged source'))
   self.assertFalse(r.repair(m.repair_context('action_failed',{},{}))['restart'])
 def test_restart_arguments_pin_existing_session_and_pid(self):
  m=self.module();args=m.restart_arguments(['--repair-with-codex','--pid','123'],ROOT/'session',123)
  self.assertEqual(args[-4:],['--session',str(ROOT/'session'),'--pid','123']);self.assertIn('--repair-with-codex',args)
 def test_supervisor_spawns_only_after_repeated_failure_and_requests_restart(self):
  self.module()
  spec=importlib.util.spec_from_file_location('repair_autoplay',ROOT/'autoplay.py');a=importlib.util.module_from_spec(spec);spec.loader.exec_module(a)
  class Repair:
   count=0
   def observe(self,context):self.count+=1;return self.count>=3
   def repair(self,context,check_stop):check_stop();return {'restart':True,'reason':'verified'}
  class Game:
   LATEST=ROOT
   from contextlib import contextmanager
   @contextmanager
   def navigation_lease(self):yield
  with tempfile.TemporaryDirectory() as td:
   supervisor=a.Supervisor(Game(),Path(td),repair_with_codex=True,repair_manager=Repair())
   supervisor.state={'map':'s450'};supervisor.quest={};supervisor.publish=lambda *a,**k:None
   supervisor.maybe_repair('action_failed');supervisor.maybe_repair('action_failed')
   self.assertFalse(supervisor.restart_requested)
   with self.assertRaises(a.StopRequested):supervisor.maybe_repair('action_failed')
   self.assertTrue(supervisor.restart_requested)
 def test_second_worker_is_blocked_by_lock(self):
  import fcntl
  m=self.module()
  with tempfile.TemporaryDirectory() as td:
   r=m.CodexRepair(Path(td),popen=lambda *a,**k:self.fail('Second worker spawned'))
   with (Path(td)/'repair.lock').open('a+') as lease:
    fcntl.flock(lease,fcntl.LOCK_EX|fcntl.LOCK_NB)
    self.assertEqual(r.repair(m.repair_context('action_failed',{},{}))['reason'],'repair_already_running')
 def test_restart_releases_supervisor_lease(self):
  import fcntl
  self.module()
  spec=importlib.util.spec_from_file_location('repair_fixtures',ROOT/'linux/native/tests/test_autoplay.py');f=importlib.util.module_from_spec(spec);spec.loader.exec_module(f)
  class Repair:
   calls=0
   def observe(self,context):self.calls+=1;return self.calls>=3
   def repair(self,context,check_stop):return {'restart':True,'reason':'verified'}
  with tempfile.TemporaryDirectory() as td:
   session=Path(td);clock=f.Clock();game=f.Game(f.world(),session)
   def fail(**kwargs):raise ValueError('fixture error')
   game.follow_trace=fail
   supervisor=f.autoplay.Supervisor(game,session,window_factory=f.Windows(),clock=clock.monotonic,sleep=clock.sleep,repair_with_codex=True,repair_manager=Repair())
   report=supervisor.run(max_cycles=30)
   self.assertEqual(report['reason'],'repair_restart');self.assertFalse(report['active']);self.assertIsNone(supervisor.window)
   with (session/'autoplay.lock').open('a+') as lease:fcntl.flock(lease,fcntl.LOCK_EX|fcntl.LOCK_NB)
 def test_failed_verification_never_requests_restart(self):
  m=self.module()
  with tempfile.TemporaryDirectory() as td:
   root=Path(td);(root/'autoplay.py').write_text('old');(root/'session').mkdir()
   class Process:
    pid=989
    def poll(self):return 0
   def spawn(*a,**k):(root/'autoplay.py').write_text('changed');return Process()
   class Failed:returncode=1
   repair=m.CodexRepair(root/'session',root=root,popen=spawn,run=lambda *a,**k:Failed())
   result=repair.repair(m.repair_context('action_failed',{},{}))
   self.assertFalse(result['restart']);self.assertEqual(result['reason'],'verification_failed')
if __name__=='__main__':unittest.main(verbosity=2)
