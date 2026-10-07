import json
from pathlib import Path
def export_json(data,path):
 with Path(path).open("w",encoding="utf-8") as f:json.dump(data,f,ensure_ascii=False,indent=2)
