# `vitalk.py`

[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

REST API interface for Viessmann Optolink

## Prerequisites

- `pyserial`
- `flask`

## Development

```
$ flask --app vitalk run --host 0.0.0.0 --port 3001
```

## Production

```
$ gunicorn --workers 8 --bind 0.0.0.0:3001 vitalk:app
```
