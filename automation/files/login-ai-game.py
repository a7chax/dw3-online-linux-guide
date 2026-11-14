#!/usr/bin/env python3
"""Compatibility login command using the game's local control bridge."""
import argparse
import importlib.util
from pathlib import Path

spec=importlib.util.spec_from_file_location('dw3_login_control',Path(__file__).with_name('ai-game.py'))
game=importlib.util.module_from_spec(spec);spec.loader.exec_module(game)

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--username')
    parser.add_argument('--server')
    parser.add_argument('--character')
    parser.add_argument('--use-filled-password',action='store_true')
    args=parser.parse_args()
    return game.login(username=args.username,server=args.server,character=args.character,
                      use_filled=args.use_filled_password)

if __name__=='__main__':main()
