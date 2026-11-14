#!/usr/bin/env python3
"""Bounded, opt-in Codex repairs. This module never controls the game."""
import fcntl
import hashlib
import json
import os
import signal
from pathlib import Path
import shutil
import subprocess
import sys
import time
import traceback

ROOT=Path(__file__).resolve().parent
TRIGGERS={'action_failed','unknown_action','local_recovery_failed'}


def repair_context(reason,state,quest,error_type=None):
    # Explicit allowlists: never copy dialogue, exception messages, credentials,
    # arbitrary request objects, environment variables or complete status blobs.
    fields=('phase','map','pid','x','y','facing','movement_ready')
    frames=[]
    if error_type and sys.exc_info()[2] is not None:
        for frame in traceback.extract_tb(sys.exc_info()[2])[-8:]:
            try:filename=str(Path(frame.filename).resolve().relative_to(ROOT))
            except ValueError:filename=Path(frame.filename).name
            frames.append({'file':filename,'line':frame.lineno,'function':frame.name})
    return {'reason':reason,'error_type':error_type,'exception_frames':frames,
            'state':{k:state[k] for k in fields if k in state},
            'quest':{k:quest[k] for k in ('chapter','step','target_map','required_action') if k in quest},
            'trace':{k:(state.get('trace') or {}).get(k) for k in ('enabled','route_type','steps_remaining')},
            'files':['autoplay.py','ai-game.py','world_map.py','linux/native/tests']}


def failure_key(context):
    state=context['state'];quest=context['quest']
    identity=[context['reason'],context.get('error_type'),state.get('map'),
              quest.get('chapter'),quest.get('step'),quest.get('target_map'),quest.get('required_action')]
    return hashlib.sha256(json.dumps(identity,sort_keys=True).encode()).hexdigest()


def restart_arguments(arguments,session,pid):
    return [sys.executable,str(ROOT/'autoplay.py'),*arguments,'--session',str(session),'--pid',str(pid)]


class CodexRepair:
    def __init__(self,session,root=ROOT,*,popen=subprocess.Popen,run=subprocess.run,
                 clock=time.time,sleep=time.sleep,cooldown=600):
        self.session=Path(session);self.root=Path(root);self.path=self.session/'repair-state.json'
        self.popen=popen;self.run=run;self.clock=clock;self.sleep=sleep;self.cooldown=cooldown

    def read(self):
        try:return json.loads(self.path.read_text())
        except FileNotFoundError:return {'observations':{},'attempts':{},'total_attempts':0,'last_started':0}

    def save(self,state):
        self.session.mkdir(parents=True,exist_ok=True)
        temporary=self.path.with_suffix('.tmp');temporary.write_text(json.dumps(state,indent=2)+'\n')
        temporary.chmod(0o600);temporary.replace(self.path)

    def eligible(self,context):
        if context['reason'] not in TRIGGERS:return False
        state=self.read()
        if state.get('status')=='running_or_awaiting_approval' and state.get('worker_pid'):
            try:os.kill(state['worker_pid'],0);return False
            except ProcessLookupError:pass
            except PermissionError:return False
        return (not state['attempts'].get(failure_key(context)) and state['total_attempts']<3
                and (not state['total_attempts'] or self.clock()-state['last_started']>=self.cooldown))

    def observe(self,context):
        if context['reason'] not in TRIGGERS:return False
        state=self.read();key=failure_key(context)
        state['observations'][key]=state['observations'].get(key,0)+1;self.save(state)
        return state['observations'][key]>=3 and self.eligible(context)

    def sources(self):
        files=[*self.root.glob('*.py'),*(self.root/'linux/native/tests').glob('test_*.py')]
        return {str(path.relative_to(self.root)):hashlib.sha256(path.read_bytes()).hexdigest() for path in files}

    def repair(self,context,check_stop=lambda:None):
        self.session.mkdir(parents=True,exist_ok=True)
        with (self.session/'repair.lock').open('a+') as lease:
            try:fcntl.flock(lease,fcntl.LOCK_EX|fcntl.LOCK_NB)
            except BlockingIOError:return {'restart':False,'reason':'repair_already_running'}
            if not self.eligible(context):return {'restart':False,'reason':'repair_limited'}
            state=self.read();key=failure_key(context);started=self.clock()
            state['total_attempts']+=1;state['last_started']=started;state['attempts'][key]={'started':started}
            directory=self.session/'repairs'/f"{state['total_attempts']:03d}-{key[:12]}";directory.mkdir(parents=True,exist_ok=True)
            (directory/'context.json').write_text(json.dumps(context,indent=2)+'\n')
            report=directory/'report.md'
            prompt=('Repair only the specific repeated Python controller failure described in context.json below. '
                    'Use the existing dw3-linux-control skill and isolated fixtures. Add a regression test, '
                    'fix the narrow conditional or planner problem, and run relevant tests. '
                    'Use uv sync --locked for dependencies and uv run --locked for Python commands. '
                    'The parent has paused all game input. DO NOT control, start, restart, attach to, '
                    'log in to, or send input to any game. DO NOT start another controller or Codex worker. '
                    'Do not read .env, credentials, authentication/session secrets or raw session logs. '
                    'Do not change Java, native libraries, credentials, Codex settings, this repair mechanism, '
                    'or unrelated files. Do not git push or publish. Keep host approval settings; if approval '
                    'is required, wait for the user and describe the blocker. Finish with changed files and tests.\n\n'
                    +json.dumps(context,indent=2)+'\n')
            (directory/'prompt.txt').write_text(prompt)
            command=[shutil.which('codex') or 'codex','--sandbox','workspace-write','--ask-for-approval','on-request',
                     '-c','approvals_reviewer=auto_review','exec','--skip-git-repo-check','--cd',str(self.root),'-o',str(report),'-']
            before=self.sources();process=None
            state.update(status='starting',context_file=str(directory/'context.json'),log_file=str(directory/'worker.log'),report_file=str(report),worker_pid=None)
            self.save(state)
            try:
                environment={k:v for k,v in os.environ.items() if not k.startswith('DW3_')}
                environment['PYTHONDONTWRITEBYTECODE']='1'
                with (directory/'prompt.txt').open() as input_file,(directory/'worker.log').open('w') as log:
                    process=self.popen(command,cwd=str(self.root),stdin=input_file,stdout=log,stderr=subprocess.STDOUT,env=environment,start_new_session=True)
                    state.update(status='running_or_awaiting_approval',worker_pid=process.pid);self.save(state)
                    while process.poll() is None:
                        check_stop();self.sleep(.2)
                    check_stop();exit_code=process.poll()
                changed=sorted(path for path,digest in self.sources().items() if before.get(path)!=digest)
                state.update(worker_exit=exit_code,changed_files=changed,worker_pid=None)
                if exit_code!=0:state['status']='worker_failed'
                elif not changed:state['status']='no_source_change'
                else:
                    state['status']='verifying';self.save(state)
                    with (directory/'verification.log').open('w') as log:
                        verification=self.run([shutil.which('uv') or 'uv','run','--locked','python','-m','unittest','discover','-s','linux/native/tests'],
                            cwd=str(self.root),stdout=log,stderr=subprocess.STDOUT,timeout=180,env=environment)
                    check_stop();state['status']='verified' if verification.returncode==0 else 'verification_failed'
                    state['verification_exit']=verification.returncode
            except BaseException as error:
                if process is not None and process.poll() is None:
                    try:os.killpg(process.pid,signal.SIGTERM)
                    except ProcessLookupError:pass
                    try:process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        try:os.killpg(process.pid,signal.SIGKILL)
                        except ProcessLookupError:pass
                        process.wait(timeout=5)
                state.update(status='repair_interrupted' if not isinstance(error,Exception) else 'repair_failed',worker_pid=None,error_type=type(error).__name__)
                self.save(state)
                if not isinstance(error,Exception) or type(error).__name__=='StopRequested':raise
                return {'restart':False,'reason':state['status']}
            self.save(state)
            return {'restart':state['status']=='verified','reason':state['status'],'report_file':str(report)}
