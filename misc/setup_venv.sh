#!/bin/bash

venv=./venv
if [ -n "$1" ]; then
    venv=$1
fi
if [ ! -d ${venv} ]; then
    virtualenv --python=python3 ${venv}
fi
source ${venv}/bin/activate
pip install --upgrade  pip
pip install --upgrade pyshark
