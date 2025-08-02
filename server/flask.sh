#!/bin/bash

cd /media/nanotrik/DATA/_LUKY/DiscogsApp/server
export FLASK_APP=app.py
sudo /home/nanotrik/miniconda3/bin/python app.py -h 0.0.0.0 -p 5000