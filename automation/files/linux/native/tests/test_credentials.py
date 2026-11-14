#!/usr/bin/env python3
"""Credential configuration uses temporary fixture values only."""
import contextlib
import importlib.util
import io
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT))
spec=importlib.util.spec_from_file_location('credential_game',ROOT/'ai-game.py')
game=importlib.util.module_from_spec(spec);spec.loader.exec_module(game)

class CredentialTests(unittest.TestCase):
 def test_cli_overrides_environment_then_dotenv(self):
  with tempfile.TemporaryDirectory() as td:
   path=Path(td)/'.env'
   path.write_text('DW3_USERNAME=file-user\nDW3_PASSWORD=file-secret\nDW3_SERVER=file-server\nDW3_CHARACTER=file-character\n')
   settings=game.login_settings(username='cli-user',server='cli-server',environ={'DW3_USERNAME':'env-user','DW3_PASSWORD':'env-secret','DW3_SERVER':'env-server'},dotenv_path=path)
   self.assertEqual(settings,dict(username='cli-user',password='env-secret',server='cli-server',character='file-character'))
 def test_missing_values_do_not_include_an_account_identity(self):
  with tempfile.TemporaryDirectory() as td:
   settings=game.login_settings(environ={},dotenv_path=Path(td)/'absent')
   self.assertEqual(settings,dict(username='',password=None,server='asia',character=''))
 def test_quoted_assignments_are_literal_and_never_execute(self):
  with tempfile.TemporaryDirectory() as td:
   root=Path(td);sentinel=root/'must-not-exist';path=root/'.env'
   payload='$(touch '+str(sentinel)+')'
   path.write_text('# Full-line comment\nDW3_USERNAME="literal$user"\nDW3_PASSWORD="'+payload+'"\nDW3_CHARACTER=\'a#b=\\c"d\'\nUNKNOWN=ignored\n')
   values=game.read_dotenv(path)
   self.assertEqual(values['DW3_PASSWORD'],payload)
   self.assertEqual(values['DW3_USERNAME'],'literal$user')
   self.assertEqual(values['DW3_CHARACTER'],'a#b=\\c"d')
   self.assertNotIn('UNKNOWN',values);self.assertFalse(sentinel.exists())
 def test_unclosed_quote_errors_without_echoing_the_value(self):
  with tempfile.TemporaryDirectory() as td:
   path=Path(td)/'.env';path.write_text('DW3_PASSWORD="fixture-sensitive-text\n')
   with self.assertRaises(ValueError) as raised:game.read_dotenv(path)
   self.assertNotIn('fixture-sensitive-text',str(raised.exception))
 def check_login(self,configured_password,prompt_password=None):
  secret=configured_password or prompt_password;out=io.StringIO();fills=[]
  def request(op,**parameters):
   if op=='fill_login':fills.append(parameters);return {'server_selection':False}
   if op=='submit_login':return {'servers':['Alphamon (Ásia)']}
   return {}
  world={'phase':'world','map':'test','x':1,'y':2}
  with patch.object(game,'start',return_value={'phase':'login'}),patch.object(game,'login_settings',return_value=dict(username='fixture-user',password=configured_password,server='asia',character='fixture-character')),patch.object(game,'request',side_effect=request),patch.object(game,'wait_for',side_effect=[{'phase':'character_selection','characters':['fixture-character']},world]),patch.object(game.getpass,'getpass',return_value=prompt_password) as prompt,contextlib.redirect_stdout(out):
   result=game.login()
  self.assertEqual(result,world);self.assertEqual(fills[0]['password'],secret)
  self.assertNotIn(secret,out.getvalue())
  return prompt
 def test_configured_password_avoids_prompt_and_is_not_printed(self):
  self.check_login('configured-fixture-secret').assert_not_called()
 def test_missing_password_uses_hidden_prompt(self):
  self.check_login(None,'prompt-fixture-secret').assert_called_once()

if __name__=='__main__':unittest.main(verbosity=2)
