import os
import json

from client import AmbienceClient

if __name__ == "__main__":

  with open('name_to_id.json') as f:
      name_to_id = json.load(f)

  client = AmbienceClient(os.getenv('NAME'), name_to_id[os.getenv('NAME')])
  client.run(os.getenv('TOKEN'))
