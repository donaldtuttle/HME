"""Synthetic project histories. Gold labels never enter retrieval or reader inputs."""
from __future__ import annotations

import hashlib
import json
import random
from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class Message:
    id: str
    sequence: int
    text: str

    def render(self) -> str:
        return f"[{self.id}; turn {self.sequence}] {self.text}"


@dataclass(frozen=True)
class Question:
    id: str
    category: str
    text: str
    answer: str | None
    evidence_ids: tuple[str, ...]
    stale_answers: tuple[str, ...] = ()
    other_project_answers: tuple[str, ...] = ()


@dataclass(frozen=True)
class Scenario:
    seed: int
    messages: tuple[Message, ...]
    questions: tuple[Question, ...]

    def public_history(self) -> list[dict]:
        return [asdict(m) for m in self.messages]

    def to_dict(self) -> dict:
        return asdict(self)

    def digest(self) -> str:
        data = json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(data.encode()).hexdigest()


def scenario(seed: int) -> Scenario:
    """80 ordered, fully visible statements; five questions after interruption.

    Templates are shared between development and test. Test seeds change names,
    values, placement and distractors; this is not a held-out-language benchmark.
    IDs are assigned by chronology, never by evidence status.
    """
    rng = random.Random(seed)
    labels = rng.sample(["Alder", "Cedar", "Juniper", "Maple", "Aspen", "Birch",
                         "Willow", "Spruce", "Hazel", "Laurel", "Rowan", "Elm"], 4)
    project, other = (f"{labels[i]}-{rng.randrange(100, 1000)}" for i in (0, 1))
    materials = rng.sample(["brushed aluminum", "powder-coated steel", "recycled nylon",
                            "clear polycarbonate", "natural oak", "anodized titanium"], 3)
    old_date, new_date, other_date = rng.sample(
        ["October 6", "October 9", "October 14", "October 20", "November 3", "November 12"], 3)
    rejected = rng.choice(["adhesive bonding", "press-fit joints", "magnetic fasteners"])
    reason = rng.choice(["failed the vibration test", "exceeded the repair budget",
                         "prevented tool-free servicing"])
    next_task = rng.choice(["assemble the validation unit", "start the endurance test",
                            "measure the enclosure clearance", "run the acceptance inspection"])
    blocker = rng.choice(["replacement seal", "calibration fixture", "mounting bracket"])
    updates = {
        "material_old": f"For project {project}, the approved enclosure material is {materials[0]}.",
        "deadline_old": f"For project {project}, the delivery deadline is {old_date}.",
        "rejection": f"For project {project}, we rejected {rejected} because it {reason}.",
        "pending": f"For project {project}, the next pending task is '{next_task}'. It is blocked only by the {blocker} arriving.",
        "other_material": f"For project {other}, the approved enclosure material is {materials[2]}.",
        "other_deadline": f"For project {other}, the delivery deadline is {other_date}.",
        "material_new": f"Correction for project {project}: replace the earlier enclosure material with {materials[1]}. This is the approved material now.",
        "deadline_new": f"Correction for project {project}: delivery moved from {old_date} to {new_date}. The earlier deadline is superseded.",
        "arrived": f"For project {project}, the {blocker} has now arrived. No additional blockers were reported.",
    }
    early = sorted(rng.sample(range(1, 22), 6))
    later = sorted(rng.sample(range(30, 49), 3))
    slots = dict(zip(early + later, updates))
    topics = ["packing labels", "test fixtures", "supplier quotes", "shipping cartons",
              "workshop shelving", "review agendas", "inspection photos", "cable routing"]
    notes = ["a review is scheduled", "the checklist needs formatting", "photos were archived",
             "the supplier sent a catalog", "the team requested a diagram", "notes were filed"]
    records, evidence = [], {}
    for turn in range(1, 81):
        key = slots.get(turn)
        if key:
            text = updates[key]
            evidence[key] = f"m{turn:03d}"
        else:
            # Late interruptions can mention the similar project, but introduce
            # no answer to the target's deliberately absent purchase-order fact.
            topic_project = rng.choice([other, f"{labels[2]}-planning", f"{labels[3]}-planning"])
            text = f"For project {topic_project}, regarding {rng.choice(topics)}: {rng.choice(notes)}. Reference note {rng.randrange(1000, 9999)}."
        records.append(Message(f"m{turn:03d}", turn, text))
    questions = (
        Question("recall", "recall", f"For project {project}, why did we reject {rejected}? Copy the stated reason without 'because it'.",
                 reason, (evidence["rejection"],)),
        Question("update", "correction", f"What is the current delivery deadline for project {project}?",
                 new_date, (evidence["deadline_new"],), (old_date,), (other_date,)),
        Question("absent", "abstention", f"What purchase-order number was assigned to project {project}?",
                 None, ()),
        Question("focus", "project_focus", f"What enclosure material is currently approved for project {project}?",
                 materials[1], (evidence["material_new"],), (materials[0],), (materials[2],)),
        Question("resume", "resumption", f"Returning to project {project}, which pending task can proceed now that its blocker has cleared? Copy the task's name.",
                 next_task, (evidence["pending"], evidence["arrived"])),
    )
    return Scenario(seed, tuple(records), questions)


def normalize_answer(value: str | None) -> str | None:
    if value is None:
        return None
    return " ".join(value.casefold().strip(" \n\t.'\"").split())


def score(question: Question, response: dict, visible_ids: set[str]) -> dict:
    """Constrained short-answer scoring, not an open-ended hallucination judge."""
    valid = (isinstance(response, dict) and set(response) == {"answer", "evidence_ids"}
             and (response["answer"] is None or isinstance(response["answer"], str))
             and isinstance(response["evidence_ids"], list)
             and all(isinstance(x, str) for x in response["evidence_ids"])
             and len(set(response["evidence_ids"])) == len(response["evidence_ids"]))
    if not valid:
        return {"valid_format": False, "answer_correct": False, "grounded_correct": False,
                "unverified_answer": True, "false_answer_on_absent": question.answer is None,
                "stale_answer": False, "wrong_project_answer": False}
    answer = normalize_answer(response["answer"])
    cited = set(response["evidence_ids"])
    correct = answer == normalize_answer(question.answer)
    grounded = correct and cited == set(question.evidence_ids) and cited <= visible_ids
    # Incorrect or uncited answers are unverified under this answer key; that
    # does not establish that every such answer is a hallucination in free prose.
    return {"valid_format": True, "answer_correct": correct, "grounded_correct": grounded,
            "unverified_answer": response["answer"] is not None and not grounded,
            "false_answer_on_absent": question.answer is None and response["answer"] is not None,
            "stale_answer": answer in {normalize_answer(x) for x in question.stale_answers},
            "wrong_project_answer": answer in {normalize_answer(x) for x in question.other_project_answers}}
