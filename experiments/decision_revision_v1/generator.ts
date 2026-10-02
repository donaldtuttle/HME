import type {
  Assertion,
  ExpectedDecision,
  HiddenModel,
  History,
  PairId,
  PolicyModel,
  PublicMessage,
  Side,
  Withdrawal,
} from "./types.ts";

export type Theme = {
  id: string;
  title: string;
  target: string;
  control: string;
  other: string;
  keep: { id: string; label: string };
  alt: { id: string; label: string };
  exceptionOpt: { id: string; label: string };
  constraint: string;
  constraintPremise: string;
  deadlinePhrase: string;
  exceptionName: string;
};

export const THEMES: Theme[] = [
  {
    id: "alder",
    title: "Alder render rigs",
    target: "Alder",
    control: "Birch",
    other: "Cedar",
    keep: { id: "RIG_A", label: "Rig A" },
    alt: { id: "RIG_B", label: "Rig B" },
    exceptionOpt: { id: "RIG_C", label: "Rig C" },
    constraint: "precise shadow placement",
    constraintPremise: "P_SHADOW",
    deadlinePhrase: "preview deadline",
    exceptionName: "rush color-pass",
  },
  {
    id: "harbor",
    title: "Harbor departure routes",
    target: "Harbor",
    control: "Quay",
    other: "Pier",
    keep: { id: "ROUTE_A", label: "Route A" },
    alt: { id: "ROUTE_B", label: "Route B" },
    exceptionOpt: { id: "ROUTE_C", label: "Route C" },
    constraint: "precise shoal clearance",
    constraintPremise: "P_SHOAL",
    deadlinePhrase: "departure window",
    exceptionName: "storm-bypass",
  },
  {
    id: "nimbus",
    title: "Nimbus exposure modes",
    target: "Nimbus",
    control: "Cirrus",
    other: "Stratus",
    keep: { id: "MODE_A", label: "Mode A" },
    alt: { id: "MODE_B", label: "Mode B" },
    exceptionOpt: { id: "MODE_C", label: "Mode C" },
    constraint: "precise occultation timing",
    constraintPremise: "P_OCCULT",
    deadlinePhrase: "exposure window",
    exceptionName: "priority-sky",
  },
  {
    id: "kiln",
    title: "Kiln firing lines",
    target: "Kiln",
    control: "Hearth",
    other: "Forge",
    keep: { id: "LINE_A", label: "Line A" },
    alt: { id: "LINE_B", label: "Line B" },
    exceptionOpt: { id: "LINE_C", label: "Line C" },
    constraint: "precise thermal uniformity",
    constraintPremise: "P_THERMAL",
    deadlinePhrase: "firing window",
    exceptionName: "rush-glaze",
  },
];

export const PAIR_TITLE: Record<PairId, string> = {
  changed_constraint: "Changed constraint",
  withdrawn_evidence: "Withdrawn evidence",
  scoped_exception: "Scoped exception",
  validity_timing: "Validity and timing",
};

const PAIR_CODE: Record<PairId, string> = {
  changed_constraint: "cc",
  withdrawn_evidence: "we",
  scoped_exception: "se",
  validity_timing: "vt",
};

const PAIRS: PairId[] = [
  "changed_constraint",
  "withdrawn_evidence",
  "scoped_exception",
  "validity_timing",
];

function decisionId(project: string): string {
  return `D_${project.toUpperCase()}`;
}

function message(partial: PublicMessage): PublicMessage {
  return partial;
}

function chatter(theme: Theme, index: number): PublicMessage {
  const lines = [
    `Scheduling note ${index}. Project ${theme.other} is booking a room. No premise is changed.`,
    `Interruption ${index}. The thread drifts to an equipment inventory for an unnamed shot.`,
    `Note ${index}. Someone asks whether an archive tape was labeled. No project rule is invoked.`,
    `Aside ${index}. A calendar invite mentions Project ${theme.control} and does not record a decision.`,
  ];
  return {
    index,
    id: null,
    authority: "chatter",
    type: "chatter",
    scope: [],
    effectiveAt: index,
    links: [],
    text: lines[index % lines.length],
  };
}

function drafts(theme: Theme): PublicMessage[] {
  const slots = [24, 27, 30, 33, 36, 39, 42, 45, 48];
  return slots.map((slot, ordinal) =>
    message({
      index: slot,
      id: `X${String(ordinal + 1).padStart(2, "0")}`,
      authority: "unverified-draft",
      type: "draft",
      scope: [theme.target, theme.control],
      effectiveAt: slot,
      links: ["E01"],
      text: `Unverified draft ${ordinal + 1}. An older note preferred ${theme.keep.label} for Project ${theme.target}. It mentions Project ${theme.control} only in passing. This is not an exception, nothing is withdrawn, and it does not change a premise or a deadline.`,
    }),
  );
}

function shadowPolicy(theme: Theme): PolicyModel {
  return {
    id: "POL_CONSTRAINT",
    premises: [
      { id: theme.constraintPremise, label: theme.constraint },
      { id: "P_DEADLINE", label: `${theme.deadlinePhrase} in minutes` },
    ],
    options: [theme.keep, theme.alt],
    rules: [
      {
        id: "R_REQUIRED",
        optionId: theme.keep.id,
        unresolvedPremiseIds: [],
        conditions: [{ op: "eq", premiseId: theme.constraintPremise, value: true }],
      },
      {
        id: "R_SHORT",
        optionId: theme.alt.id,
        unresolvedPremiseIds: [],
        conditions: [
          { op: "eq", premiseId: theme.constraintPremise, value: false },
          { op: "lt", premiseId: "P_DEADLINE", value: 10 },
        ],
      },
      {
        id: "R_ELSE",
        optionId: theme.keep.id,
        unresolvedPremiseIds: [],
        conditions: [],
      },
    ],
  };
}

function exceptionPolicy(theme: Theme): PolicyModel {
  return {
    id: "POL_EXCEPTION",
    premises: [{ id: "P_EXCEPTION", label: `${theme.exceptionName} exception` }],
    options: [theme.keep, theme.exceptionOpt],
    rules: [
      {
        id: "R_EXCEPTION",
        optionId: theme.exceptionOpt.id,
        unresolvedPremiseIds: [],
        conditions: [{ op: "eq", premiseId: "P_EXCEPTION", value: true }],
      },
      {
        id: "R_DEFAULT",
        optionId: theme.keep.id,
        unresolvedPremiseIds: [],
        conditions: [{ op: "eq", premiseId: "P_EXCEPTION", value: false }],
      },
    ],
  };
}

function compatPolicy(): PolicyModel {
  return {
    id: "POL_COMPAT",
    premises: [{ id: "P_COMPAT", label: "verified compatibility support" }],
    options: [{ id: "PROCEED", label: "Proceed" }],
    rules: [
      {
        id: "R_OK",
        optionId: "PROCEED",
        unresolvedPremiseIds: [],
        conditions: [{ op: "supports_gte", premiseId: "P_COMPAT", n: 1 }],
      },
      {
        id: "R_PAUSE",
        optionId: null,
        unresolvedPremiseIds: ["P_COMPAT"],
        conditions: [{ op: "supports_gte", premiseId: "P_COMPAT", n: 0 }],
      },
    ],
  };
}

function policyText(theme: Theme, pair: PairId): string {
  if (pair === "withdrawn_evidence") {
    return `Proceed with option PROCEED only when at least one verified compatibility test for that project remains active. If none remain, pause and do not authorize an option until verification is resolved. Withdrawing a test removes that support only. It does not establish incompatibility. Public identifiers: option PROCEED; premise P_COMPAT.`;
  }
  if (pair === "scoped_exception") {
    return `Use ${theme.keep.label} unless the project is on the ${theme.exceptionName} exception list. A project on that exception list uses ${theme.exceptionOpt.label}. An exception applies only to the projects named on the list. Public identifiers: options ${theme.keep.id} and ${theme.exceptionOpt.id}; premise P_EXCEPTION.`;
  }
  return `For Project ${theme.target}, use ${theme.keep.label} while ${theme.constraint} is required. If that requirement is removed and the ${theme.deadlinePhrase} is under ten minutes, use ${theme.alt.label}. ${theme.alt.label} satisfies all remaining requirements. Otherwise keep ${theme.keep.label}. Public identifiers: options ${theme.keep.id} and ${theme.alt.id}; premises ${theme.constraintPremise} and P_DEADLINE.`;
}

type Built = {
  messages: PublicMessage[];
  model: HiddenModel;
  expected: Record<string, ExpectedDecision>;
};

function assertFact(
  evidenceId: string,
  premiseId: string,
  projectId: string,
  value: string | number | boolean,
  effectiveAt: number,
  supportToken = false,
): Assertion {
  return {
    evidenceId,
    tokenId: `${evidenceId}:${premiseId}:${projectId}`,
    premiseId,
    projectId,
    value,
    supportToken,
    effectiveAt,
  };
}

function assemble(theme: Theme, records: PublicMessage[]): PublicMessage[] {
  const byIndex = new Map(records.map((record) => [record.index, record]));
  const messages: PublicMessage[] = [];
  for (let index = 1; index <= 80; index++) {
    messages.push(byIndex.get(index) ?? chatter(theme, index));
  }
  return messages;
}

function headerRecords(
  theme: Theme,
  pair: PairId,
  body: {
    e02: string;
    e03: string;
    e04: string;
    e05: string;
    e05Effective: number;
    e05Scope: string[];
    e06: string;
    e06Scope: string[];
  },
): PublicMessage[] {
  return [
    message({
      index: 1,
      id: "E01",
      authority: "policy",
      type: "policy",
      scope: [theme.target, theme.control, theme.other],
      effectiveAt: 1,
      links: [],
      text: policyText(theme, pair),
    }),
    message({
      index: 4,
      id: "E02",
      authority: "project-lead",
      type: "state",
      scope: [theme.target],
      effectiveAt: 4,
      links: ["E01"],
      text: body.e02,
    }),
    message({
      index: 7,
      id: "E03",
      authority: "project-lead",
      type: "decision",
      scope: [theme.target],
      effectiveAt: 7,
      links: ["E01", "E02"],
      text: body.e03,
    }),
    message({
      index: 10,
      id: "E04",
      authority: "project-lead",
      type: "state",
      scope: [theme.control],
      effectiveAt: 10,
      links: ["E01"],
      text: body.e04,
    }),
    message({
      index: 14,
      id: "E06",
      authority: "project-lead",
      type: "state",
      scope: body.e06Scope,
      effectiveAt: 14,
      links: ["E01"],
      text: body.e06,
    }),
    message({
      index: 21,
      id: "E05",
      authority: "project-lead",
      type: "status",
      scope: body.e05Scope,
      effectiveAt: body.e05Effective,
      links: ["E01", "E03"],
      text: body.e05,
    }),
    ...drafts(theme),
  ];
}

function constraintBodies(theme: Theme, side: Side, timing: boolean) {
  const e02 = `Project ${theme.target} currently requires ${theme.constraint} and has an eight-minute ${theme.deadlinePhrase}.`;
  const e03 = `We selected ${theme.keep.label} for Project ${theme.target} because ${theme.constraint} is required.`;
  const e04 = `Project ${theme.control} independently requires ${theme.constraint}, uses ${theme.keep.label}, and follows the same rule.`;
  const e06 = `Project ${theme.other} requires ${theme.constraint}, uses ${theme.keep.label}, and is not one of the two decisions in the question.`;
  if (timing) {
    const effective = side === "target" ? 21 : 120;
    return {
      e02,
      e03,
      e04,
      e06,
      e06Scope: [theme.other],
      e05: `Project ${theme.target} no longer requires ${theme.constraint}. Its eight-minute ${theme.deadlinePhrase} remains. Effective time: ${effective}.`,
      e05Effective: effective,
      e05Scope: [theme.target],
    };
  }
  if (side === "target") {
    return {
      e02,
      e03,
      e04,
      e06,
      e06Scope: [theme.other],
      e05: `Project ${theme.target} no longer requires ${theme.constraint}. Its eight-minute ${theme.deadlinePhrase} remains.`,
      e05Effective: 21,
      e05Scope: [theme.target],
    };
  }
  return {
    e02,
    e03,
    e04,
    e06,
    e06Scope: [theme.other],
    e05: `Project ${theme.other} no longer requires ${theme.constraint}. Its eight-minute ${theme.deadlinePhrase} remains.`,
    e05Effective: 21,
    e05Scope: [theme.other],
  };
}

function buildModel(
  theme: Theme,
  pair: PairId,
  side: Side,
): { model: HiddenModel; expected: Record<string, ExpectedDecision>; records: PublicMessage[] } {
  const targetId = decisionId(theme.target);
  const controlId = decisionId(theme.control);
  const keep = theme.keep.id;

  if (pair === "withdrawn_evidence") {
    const t2Project = side === "target" ? theme.other : theme.target;
    const records = headerRecords(theme, pair, {
      e02: `Compatibility test T1 for Project ${theme.target} is verified and active.`,
      e03: `We selected PROCEED for Project ${theme.target} because T1 was verified and active.`,
      e04: `Compatibility test C1 for Project ${theme.control} is verified and active. Project ${theme.control} selected PROCEED and follows the same rule.`,
      e06:
        side === "target"
          ? `Compatibility test T2 is verified and active for Project ${theme.other}, not for Project ${theme.target}.`
          : `Compatibility test T2 is verified and active for Project ${theme.target} and is independent of T1.`,
      e06Scope: [t2Project],
      e05: `Compatibility test T1 for Project ${theme.target} is withdrawn. No replacement test is named in this note.`,
      e05Effective: 21,
      e05Scope: [theme.target],
    });
    const t1 = assertFact("E02", "P_COMPAT", theme.target, true, 4, true);
    const c1 = assertFact("E04", "P_COMPAT", theme.control, true, 10, true);
    const t2 = assertFact("E06", "P_COMPAT", t2Project, true, 14, true);
    const withdrawals: Withdrawal[] = [
      { evidenceId: "E05", tokenId: t1.tokenId, effectiveAt: 21 },
    ];
    const expected: Record<string, ExpectedDecision> =
      side === "target"
        ? {
            [targetId]: { action: "DEFER", optionId: null, decisive: ["P_COMPAT"], unresolved: ["P_COMPAT"] },
            [controlId]: { action: "RETAIN", optionId: "PROCEED", decisive: ["P_COMPAT"], unresolved: [] },
          }
        : {
            [targetId]: { action: "RETAIN", optionId: "PROCEED", decisive: ["P_COMPAT"], unresolved: [] },
            [controlId]: { action: "RETAIN", optionId: "PROCEED", decisive: ["P_COMPAT"], unresolved: [] },
          };
    const supports: Record<string, string[][]> =
      side === "target"
        ? {
            [targetId]: [["E01", "E02", "E03", "E05"]],
            [controlId]: [["E01", "E04"]],
          }
        : {
            [targetId]: [["E01", "E03", "E06"]],
            [controlId]: [["E01", "E04"]],
          };
    return {
      records,
      expected,
      model: {
        policyEvidenceId: "E01",
        policy: compatPolicy(),
        assertions: [t1, c1, t2],
        withdrawals,
        decisions: [
          { id: targetId, projectId: theme.target, recordedOptionId: "PROCEED", recordId: "E03" },
          { id: controlId, projectId: theme.control, recordedOptionId: "PROCEED", recordId: "E04" },
        ],
        cutoff: 80,
        supports,
      },
    };
  }

  if (pair === "scoped_exception") {
    const namesTarget = side === "target";
    const records = headerRecords(theme, pair, {
      e02: `Project ${theme.target} is not on the ${theme.exceptionName} exception list.`,
      e03: `We selected ${theme.keep.label} for Project ${theme.target} because it is not on the ${theme.exceptionName} exception list.`,
      e04: `Project ${theme.control} is not on the ${theme.exceptionName} exception list, uses ${theme.keep.label}, and follows the same rule.`,
      e06: `Project ${theme.other} is not named by any earlier exception list and uses ${theme.keep.label}.`,
      e06Scope: [theme.other],
      e05: namesTarget
        ? `The ${theme.exceptionName} exception list now names Project ${theme.target}. It does not name Project ${theme.control}.`
        : `The ${theme.exceptionName} exception list now names Project ${theme.other}. It does not name Project ${theme.target} or Project ${theme.control}.`,
      e05Effective: 21,
      e05Scope: namesTarget ? [theme.target] : [theme.other],
    });
    const assertions: Assertion[] = [
      assertFact("E02", "P_EXCEPTION", theme.target, false, 4),
      assertFact("E04", "P_EXCEPTION", theme.control, false, 10),
      assertFact("E06", "P_EXCEPTION", theme.other, false, 14),
      assertFact("E05", "P_EXCEPTION", namesTarget ? theme.target : theme.other, true, 21),
    ];
    const expected: Record<string, ExpectedDecision> = namesTarget
      ? {
          [targetId]: {
            action: "REVISE",
            optionId: theme.exceptionOpt.id,
            decisive: ["P_EXCEPTION"],
            unresolved: [],
          },
          [controlId]: { action: "RETAIN", optionId: keep, decisive: ["P_EXCEPTION"], unresolved: [] },
        }
      : {
          [targetId]: { action: "RETAIN", optionId: keep, decisive: ["P_EXCEPTION"], unresolved: [] },
          [controlId]: { action: "RETAIN", optionId: keep, decisive: ["P_EXCEPTION"], unresolved: [] },
        };
    const supports: Record<string, string[][]> = namesTarget
      ? {
          [targetId]: [
            ["E01", "E03", "E05"],
            ["E01", "E02", "E03", "E05"],
          ],
          [controlId]: [["E01", "E04"]],
        }
      : {
          [targetId]: [["E01", "E02", "E03"]],
          [controlId]: [["E01", "E04"]],
        };
    return {
      records,
      expected,
      model: {
        policyEvidenceId: "E01",
        policy: exceptionPolicy(theme),
        assertions,
        withdrawals: [],
        decisions: [
          { id: targetId, projectId: theme.target, recordedOptionId: keep, recordId: "E03" },
          { id: controlId, projectId: theme.control, recordedOptionId: keep, recordId: "E04" },
        ],
        cutoff: 80,
        supports,
      },
    };
  }

  const timing = pair === "validity_timing";
  const revise = side === "target";
  const bodies = constraintBodies(theme, side, timing);
  const records = headerRecords(theme, pair, bodies);
  const assertions: Assertion[] = [
    assertFact("E02", theme.constraintPremise, theme.target, true, 4),
    assertFact("E02", "P_DEADLINE", theme.target, 8, 4),
    assertFact("E04", theme.constraintPremise, theme.control, true, 10),
    assertFact("E06", theme.constraintPremise, theme.other, true, 14),
  ];
  if (timing || revise) {
    const project = timing || revise ? (timing ? theme.target : side === "target" ? theme.target : theme.other) : theme.other;
    assertions.push(
      assertFact("E05", theme.constraintPremise, project, false, bodies.e05Effective),
      assertFact("E05", "P_DEADLINE", project, 8, bodies.e05Effective),
    );
  } else {
    assertions.push(
      assertFact("E05", theme.constraintPremise, theme.other, false, 21),
      assertFact("E05", "P_DEADLINE", theme.other, 8, 21),
    );
  }
  const premise = theme.constraintPremise;
  const expected: Record<string, ExpectedDecision> = revise
    ? {
        [targetId]: {
          action: "REVISE",
          optionId: theme.alt.id,
          decisive: [premise, "P_DEADLINE"].sort(),
          unresolved: [],
        },
        [controlId]: { action: "RETAIN", optionId: keep, decisive: [premise], unresolved: [] },
      }
    : {
        [targetId]: { action: "RETAIN", optionId: keep, decisive: [premise], unresolved: [] },
        [controlId]: { action: "RETAIN", optionId: keep, decisive: [premise], unresolved: [] },
      };
  const supports: Record<string, string[][]> = revise
    ? {
        [targetId]: [
          ["E01", "E03", "E05"],
          ["E01", "E02", "E03", "E05"],
        ],
        [controlId]: [["E01", "E04"]],
      }
    : {
        [targetId]: [["E01", "E02", "E03"]],
        [controlId]: [["E01", "E04"]],
      };
  return {
    records,
    expected,
    model: {
      policyEvidenceId: "E01",
      policy: shadowPolicy(theme),
      assertions,
      withdrawals: [],
      decisions: [
        { id: targetId, projectId: theme.target, recordedOptionId: keep, recordId: "E03" },
        { id: controlId, projectId: theme.control, recordedOptionId: keep, recordId: "E04" },
      ],
      cutoff: 80,
      supports,
    },
  };
}

function queryFor(theme: Theme): string {
  const targetId = decisionId(theme.target);
  const controlId = decisionId(theme.control);
  return `What should Project ${theme.target} use now, what should Project ${theme.control} use, and which records support those choices? Decision identifiers ${targetId} and ${controlId}. Effective-time cutoff is 80. Later-scheduled records are not effective. Return both decisions.`;
}

export function buildCorpus(): History[] {
  const histories: History[] = [];
  THEMES.forEach((theme, themeIndex) => {
    const flip = themeIndex % 2 === 1;
    for (const pair of PAIRS) {
      for (const side of ["target", "control"] as const) {
        const built = buildModel(theme, pair, side);
        const blindDigit = (side === "target") !== flip ? "1" : "2";
        const id = `${theme.id}-${PAIR_CODE[pair]}-${blindDigit}`;
        histories.push({
          id,
          blindLabel: id,
          familyId: theme.id,
          familyTitle: theme.title,
          pairId: pair,
          pairTitle: PAIR_TITLE[pair],
          side,
          messages: assemble(theme, built.records),
          query: queryFor(theme),
          queriedDecisionIds: [decisionId(theme.target), decisionId(theme.control)],
          model: built.model,
          expected: built.expected,
        });
      }
    }
  });
  return histories;
}

export function actionTally(histories: History[]): Record<string, number> {
  const tally: Record<string, number> = { RETAIN: 0, REVISE: 0, DEFER: 0 };
  for (const history of histories) {
    const target = history.model.decisions[0];
    if (!target) continue;
    const action = history.expected[target.id]?.action;
    if (action) tally[action] += 1;
  }
  return tally;
}
