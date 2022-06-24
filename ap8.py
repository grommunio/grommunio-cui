#!/usr/bin/python3
import os
from pathlib import Path

import autopep8 as ap8
import black
from black import Mode, NothingChanged, InvalidInput


def fix_file(filename):
    content = ""
    with open(filename, 'r') as f:
        for line in f:
            content = ''.join([content, line])
    o = {
        'aggressive': 3,
        'diff': False,
        'exclude': {},
        'exit_code': False,
        'experimental': True,
        'files': [''],
        'hang_closing': False,
        'ignore': {'W50', 'E226', 'E24', 'W690'},
        'ignore_local_config': False,
        'in_place': False,
        'indent_size': 4,
        'jobs': 1,
        'line_range': None,
        'list_fixes': False,
        'max_line_length': 79,
        'pep8_passes': -1,
        'recursive': False,
        'verbose': 1
    }
    res = ap8.fix_code(content, options=o)
    nl = '\n'
    print(f"Before {content.count(nl)} and after: {res.count(nl)}")
    return res


def main():
    cur_path = '.'
    process_walk(cur_path, False)
    print('Ende')


def process_walk(cur_path, inplace=True):
    walker = list(os.walk(cur_path))
    for t in walker:
        for f in t[2]:
            if not f[-2:] == 'py' or f[-6:-3] == 'opt':
                continue
            fix = fix_file(f"{t[0]}{os.sep}{f}")
            mode = Mode(
                line_length=79
            )
            try:
                fix2 = black.format_file_contents(fix, fast=False, mode=mode)
            except NothingChanged as e:
                print(f"Error while processing {f}: {e}")
                fix2 = fix
            except InvalidInput as e:
                print(f"Error while processing {f}: {e}")
                fix2 = fix
            opt = '_opt' if not inplace else ''
            new_f = f"{t[0]}{os.sep}{os.path.splitext(f)[0]}{opt}{os.path.splitext(f)[1]}"
            with open(new_f, 'w') as w:
                nl = '\n'
                print(f"before fix2 was {fix.count(nl)} and now is {fix2.count(nl)}")
                w.write(fix2)
                w.close()
                print(f"Optimized file {new_f} written.")


if __name__ == '__main__':
    main()
