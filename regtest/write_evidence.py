import json
import sys
from pathlib import Path

from sovereign_l402.evidence import build_evidence

output, observations_path, commit, images_path = sys.argv[1:]
observations = [
    json.loads(line)
    for line in Path(observations_path).read_text(encoding="utf-8").splitlines()
    if line.strip()
]
images = json.loads(Path(images_path).read_text(encoding="utf-8"))
evidence = build_evidence(observations, commit=commit, images=images)
Path(output).write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")

