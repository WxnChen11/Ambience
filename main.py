import os
import json

from client import AmbienceClient

if __name__ == "__main__":
  # Import config
  with open('config.json') as f:
    config = json.load(f)

  client = AmbienceClient(config)

  # TODO: Create music handler
  # TODO: Create picture handler
  client.run(os.getenv('TOKEN'))
