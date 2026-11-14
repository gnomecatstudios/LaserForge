"""Deterministic schema-1 vector workload shared by both renderer harnesses."""
import argparse
import json
import math


def fixture(count=1000):
    columns = math.ceil(math.sqrt(count))
    pitch = 380 / columns
    side = pitch * 0.7
    objects = []
    for index in range(count):
        objects.append({
            "id": f"object-{index}", "kind": "vector", "layerId": "cut",
            "name": f"Rectangle {index}", "visible": True, "locked": False,
            "transform": [1, 0, 0, 1, 10 + (index % columns) * pitch,
                          10 + (index // columns) * pitch],
            "paths": [{"closed": True, "start": {"x": 0, "y": 0}, "segments": [
                {"type": "L", "to": {"x": side, "y": 0}},
                {"type": "L", "to": {"x": side, "y": side}},
                {"type": "L", "to": {"x": 0, "y": side}},
                {"type": "L", "to": {"x": 0, "y": 0}},
            ]}],
        })
    return {
        "version": 1, "id": "benchmark", "name": f"{count} rectangles",
        "createdAt": "2026-11-14T00:00:00.000Z", "updatedAt": "2026-11-14T00:00:00.000Z",
        "machineProfileId": None, "assets": {}, "designCorner": "bl",
        "layers": [{"id": "cut", "name": "Cut", "color": "#C0392B", "visible": True,
                    "output": True, "mode": "line", "speed": 1000, "power": 100,
                    "minPower": 0, "passes": 1, "airAssist": False,
                    "line": {"kerfOffset": 0}}],
        "objects": objects,
        "jobSettings": {"origin": "absolute", "anchor": "bl", "userOrigin": None,
                        "returnToOrigin": False, "optimizeOrder": True},
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--objects", type=int, default=1000)
    options = parser.parse_args()
    if options.objects < 1 or options.objects > 100000:
        parser.error("objects must be in 1..100000")
    print(json.dumps(fixture(options.objects)))
