# `vitalk.py`

[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

REST API interface for Viessmann Optolink

## Usage (Raspberry Pi)

```
$ sudo apt install -y git python3-pip
$ git clone git@github.com:t4ccer/vitalk-py.git
$ cd vitalk-py
$ pip install -r requirements.txt --break-system-packages
```

You may need to re-enter bash after `pip install`

### Production

```
$ gunicorn --workers 8 --bind 0.0.0.0:3001 --chdir /path/to/vitalk-py vitalk:app
```

#### Creating `systemd` unit

```
$ sudo cp vitalk-py.service.example /etc/systemd/system/vitalk-py.service
```

Then edit (`sudo nano /etc/systemd/system/vitalk-py.service`) the unit file to change `--chdir` argument to the location of your installation.

```
$ sudo systemctl enable vitalk-py
$ sudo systemctl start vitalk-py
```

You can check logs with

```
$ sudo journalctl -u vitalk-py
```

### Development

```
$ flask --app /path/to/vitalk-py/vitalk run --host 0.0.0.0 --port 3001
```
