#!/bin/env python3
import argparse
import os.path
import sys

def print_cmd_log(file_name):
    with open(file_name, 'r') as f:
        for line in f:
            cmds = line.split('\x03')
            for c in cmds:
                print(c.encode('utf-8'))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Command cmd reader')
    parser.add_argument('cmdfile',
                        help='cmd file to decode')
    args = parser.parse_args()

    file_name = args.cmdfile
    if not os.path.isfile(file_name):
        print('"{}" does not exist'.format(file_name), file=sys.stderr)
        sys.exit(-1)

    print_cmd_log(file_name)
