#!/bin/sh
gunicorn main:app -w 2 --timeout 30 --threads 1 -b 0.0.0.0:80