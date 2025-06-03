# Livekit transcription / traduction agent

A livekit transcription / traduction agent based on [Gladia](https://www.gladia.io/)

## Running Locally

1. Create a .env.local file with the required keys
2. Run the following commands

```shell
$ python3.11 -m venv venv
$ source ./venv/bin/activate
$ pip install -r requirements.txt
$ python agent.py download-files
$ python agent.py dev
```