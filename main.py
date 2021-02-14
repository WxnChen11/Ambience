import os
import json

from client import AmbienceClient

if __name__ == "__main__":
  client = AmbienceClient('Ninth Street Espresso#5861')

  # TODO: Create music handler
  # TODO: Create picture handler
  client.run(os.getenv('TOKEN'))
