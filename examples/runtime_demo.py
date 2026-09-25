"""NumPy-only diffusion -> field runtime -> memory retrieval example.

Run from a source checkout: python examples/runtime_demo.py (NumPy required).
"""
import json
from pathlib import Path
import sys

# Direct file execution adds examples/, not the checkout root, to sys.path.
if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np

from hme_engine import SalienceConfig
from hme_runtime import EventConfig, FieldRuntime
from hme_dynamics import DynamicsConfig, FieldDynamics


def run_demo():
    simulator = FieldDynamics(DynamicsConfig(grid_size=24, num_steps=16, seed=7))
    _, trajectory, _ = simulator.evolve([0.0, 1.0, 0.0, -1.0])
    runtime = FieldRuntime(memory_size=24, encoding_resolution=8,
        event_config=EventConfig(threshold=0.2),
        salience_config=SalienceConfig(influence_write_gain=True), seed=7)
    # Demo adapter: repeat a 1D spatial row across the 2D controller input.
    for row in trajectory:
        tick = runtime.step(np.tile(row, (24, 1)), memory_payload=row,
                            memory_position=(12, 12))
    result = runtime.retrieve_memory((12, 12), query=trajectory[-1], top_k=3)
    return {
        'ticks': runtime.step_index,
        'field_events': len(runtime.event_log),
        'memory_records': len(runtime.hme.records),
        'last_write_salience': tick.meta.write_salience,
        'retrieval_outcome': result.outcome,
        'relevance_score': result.relevance_score,
        'score_is_calibrated': False,
        'state': runtime.state_summary(),
    }


if __name__ == '__main__':
    print(json.dumps(run_demo(), indent=2))
