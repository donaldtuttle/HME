import { useMemo, useState } from "react";
import { BookMarked, BookOpen, Download, FlaskConical, Scale, ShieldCheck } from "lucide-react";
import { ARM_LABEL, buildPackets } from "../../../experiments/decision_revision_v1/memory.ts";
import { CORPUS } from "../../../experiments/decision_revision_v1/corpus.ts";
import { diagnoseHistory } from "../../../experiments/decision_revision_v1/diagnose.ts";
import { ARM_SUMMARY, BASELINE_SUMMARY, PREFLIGHT } from "../../../experiments/decision_revision_v1/report.ts";
import { parseReaderJson, scoreHistory, type Score } from "../../../experiments/decision_revision_v1/score.ts";
import { solve } from "../../../experiments/decision_revision_v1/solver.ts";
import { toPublic } from "../../../experiments/decision_revision_v1/text.ts";
import { Guide } from "./Guide";
import type { ArmId, History, Packet, PublicMessage } from "../../../experiments/decision_revision_v1/types.ts";

type View = "guide" | "read" | "bench" | "protocol" | "checks" | "export";

const VIEWS: { id: View; label: string; icon: typeof BookOpen }[] = [
  { id: "guide", label: "Guide", icon: BookMarked },
  { id: "read", label: "Read", icon: BookOpen },
  { id: "bench", label: "Bench", icon: Scale },
  { id: "protocol", label: "Protocol", icon: FlaskConical },
  { id: "checks", label: "Checks", icon: ShieldCheck },
  { id: "export", label: "Export", icon: Download },
];

const ARMS: ArmId[] = [
  "summary_recent",
  "nn_full",
  "nn_projected",
  "hme_hybrid",
  "decision_ledger",
];

function templateFor(history: History): string {
  return JSON.stringify(
    {
      decisions: history.queriedDecisionIds.map((id) => ({
        decision_id: id,
        action: "RETAIN",
        selected_option_id: null,
        decisive_premise_ids: [],
        unresolved_premise_ids: [],
        evidence_ids: [],
      })),
    },
    null,
    2,
  );
}

function download(filename: string, contents: string, type: string) {
  const blob = new Blob([contents], { type });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  anchor.click();
  URL.revokeObjectURL(url);
}

export function Workbench() {
  const [view, setView] = useState<View>("guide");
  const [historyId, setHistoryId] = useState(CORPUS[0]?.id ?? "");
  const [arm, setArm] = useState<ArmId>("decision_ledger");
  const history = CORPUS.find((item) => item.id === historyId) ?? CORPUS[0];

  return (
    <div className="min-h-screen bg-paper text-ink">
      <header className="border-b border-line">
        <div className="mx-auto flex max-w-6xl flex-col gap-4 px-4 py-5 sm:px-6 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <p className="font-mono text-xs tracking-widest text-muted uppercase">HME-CM-REV-1 · Design</p>
            <h1 className="mt-1 text-2xl font-medium tracking-tight">Decision revision bench</h1>
            <p className="mt-2 max-w-2xl text-sm leading-relaxed text-muted">
              Given a declared rule and later evidence, keep a plan, revise it, or wait. The revised action is never written as an instruction. This is an illustrative fixture. It is not a model run and not a registered result.
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            <Tag>Illustrative fixture</Tag>
            <Tag>Field not tested</Tag>
            <Tag>No model calls</Tag>
            <a
              href="./decision_revision_v1.zip"
              download="decision_revision_v1.zip"
              className="inline-flex min-h-11 items-center text-sm text-accent underline"
            >
              decision_revision_v1.zip
            </a>
          </div>
        </div>
        <nav className="mx-auto flex max-w-6xl gap-1 overflow-x-auto px-4 sm:px-6" aria-label="Sections">
          {VIEWS.map((item) => {
            const Icon = item.icon;
            const active = view === item.id;
            return (
              <button
                key={item.id}
                type="button"
                onClick={() => setView(item.id)}
                className={
                  "flex min-h-11 shrink-0 items-center gap-2 border-b-2 px-3 text-sm " +
                  (active ? "border-accent text-ink" : "border-transparent text-muted")
                }
              >
                <Icon className="size-4" aria-hidden="true" />
                {item.label}
              </button>
            );
          })}
        </nav>
      </header>
      <main className="mx-auto max-w-6xl px-4 py-6 sm:px-6">
        {history ? (
          <>
            {view === "read" && (
              <Reader history={history} arm={arm} onArm={setArm} onHistory={setHistoryId} />
            )}
            {view === "bench" && (
              <Bench history={history} arm={arm} onArm={setArm} onHistory={setHistoryId} />
            )}
          </>
        ) : null}
        {view === "guide" && (
          <Guide
            onTryExample={() => {
              setHistoryId("alder-cc-1");
              setArm("decision_ledger");
              setView("read");
            }}
          />
        )}
        {view === "protocol" && <Protocol />}
        {view === "checks" && <Checks />}
        {view === "export" && <ExportPanel />}
      </main>
    </div>
  );
}

function Tag({ children }: { children: string }) {
  return (
    <span className="border border-line bg-inset px-2 py-1 font-mono text-xs tracking-wide text-muted uppercase">
      {children}
    </span>
  );
}

function HistoryPick({
  history,
  onHistory,
  blind,
}: {
  history: History;
  onHistory: (id: string) => void;
  blind: boolean;
}) {
  const families = useMemo(() => {
    const map = new Map<string, History[]>();
    for (const item of CORPUS) {
      const list = map.get(item.familyId) ?? [];
      list.push(item);
      map.set(item.familyId, list);
    }
    return [...map.entries()];
  }, []);

  return (
    <label className="block text-sm">
      <span className="font-mono text-xs tracking-widest text-muted uppercase">History</span>
      <select
        className="mt-1 min-h-11 w-full border border-line bg-inset px-3 text-sm"
        value={history.id}
        onChange={(event) => onHistory(event.target.value)}
      >
        {families.map(([familyId, rows]) => (
          <optgroup key={familyId} label={blind ? familyId : rows[0]?.familyTitle ?? familyId}>
            {rows.map((row) => (
              <option key={row.id} value={row.id}>
                {blind ? row.blindLabel : `${row.blindLabel} · ${row.pairTitle} · ${row.side}`}
              </option>
            ))}
          </optgroup>
        ))}
      </select>
    </label>
  );
}

function ArmPick({ arm, onArm }: { arm: ArmId; onArm: (arm: ArmId) => void }) {
  return (
    <div>
      <p className="font-mono text-xs tracking-widest text-muted uppercase">Memory packet</p>
      <div className="mt-2 flex flex-wrap gap-2">
        {ARMS.map((id) => (
          <button
            key={id}
            type="button"
            onClick={() => onArm(id)}
            className={
              "min-h-11 border px-3 text-sm " +
              (arm === id ? "border-accent bg-accent text-paper" : "border-line bg-inset text-ink")
            }
          >
            {ARM_LABEL[id]}
          </button>
        ))}
      </div>
    </div>
  );
}

function PacketView({ packet, query }: { packet: Packet; query: string }) {
  return (
    <section className="border border-line bg-inset">
      <header className="flex flex-wrap items-baseline justify-between gap-2 border-b border-line px-4 py-3">
        <div>
          <h2 className="text-sm font-medium">{ARM_LABEL[packet.arm]}</h2>
          <p className="font-mono text-xs text-muted">
            {packet.words} words · {packet.evidenceIds.length} records
          </p>
        </div>
        {packet.fieldStatus === "MECHANISM_NOT_TESTED" && (
          <span className="border border-ink px-2 py-1 font-mono text-xs">MECHANISM_NOT_TESTED</span>
        )}
      </header>
      <div className="space-y-3 px-4 py-3 text-sm leading-relaxed">
        {packet.notes.map((note) => (
          <p key={note} className="text-muted">
            {note}
          </p>
        ))}
        <p className="border border-line bg-paper px-3 py-2">{query}</p>
      </div>
      <ol className="max-h-[32rem] divide-y divide-line overflow-auto border-t border-line">
        {packet.messages.map((message) => (
          <MessageRow key={`${message.index}-${message.id ?? "chat"}`} message={message} />
        ))}
      </ol>
    </section>
  );
}

function MessageRow({ message, mark }: { message: PublicMessage; mark?: boolean }) {
  return (
    <li className={"px-4 py-3 text-sm leading-relaxed " + (mark ? "bg-accent-soft" : "")}>
      <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
        <span className="font-mono text-xs text-muted">{String(message.index).padStart(2, "0")}</span>
        {message.id && <span className="font-mono text-xs">{message.id}</span>}
        <span className="font-mono text-xs tracking-wide text-muted uppercase">{message.type}</span>
        {message.id && (
          <span className="font-mono text-xs text-muted">
            effective {message.effectiveAt}
            {message.scope.length ? ` · ${message.scope.join(", ")}` : ""}
          </span>
        )}
      </div>
      <p className="mt-1">{message.text}</p>
    </li>
  );
}

function Reader({
  history,
  arm,
  onArm,
  onHistory,
}: {
  history: History;
  arm: ArmId;
  onArm: (arm: ArmId) => void;
  onHistory: (id: string) => void;
}) {
  const packet = useMemo(
    () => buildPackets(toPublic(history)).find((item) => item.arm === arm),
    [history, arm],
  );
  const [drafts, setDrafts] = useState<Record<string, string>>({});
  const [attempts, setAttempts] = useState<
    Record<string, { score: Score | null; error: string | null; revealed: boolean }>
  >({});
  const key = `${history.id}:${arm}`;
  const draft = drafts[key] ?? templateFor(history);
  const attempt = attempts[key];

  function submit() {
    if (!packet) return;
    const parsed = parseReaderJson(draft);
    if (!parsed.ok) {
      setAttempts((current) => ({ ...current, [key]: { score: null, error: parsed.error, revealed: false } }));
      return;
    }
    const score = scoreHistory(history, parsed.value, packet.evidenceIds);
    setAttempts((current) => ({ ...current, [key]: { score, error: null, revealed: false } }));
  }

  return (
    <div className="grid gap-6 lg:grid-cols-[minmax(0,1.1fr)_minmax(0,0.9fr)]">
      <div className="space-y-4">
        <HistoryPick history={history} onHistory={onHistory} blind />
        <ArmPick arm={arm} onArm={onArm} />
        {packet && <PacketView packet={packet} query={history.query} />}
      </div>
      <div className="space-y-4">
        <section className="border border-line bg-inset p-4">
          <h2 className="text-sm font-medium">Your answer</h2>
          <p className="mt-2 text-sm leading-relaxed text-muted">
            Use only the packet. RETAIN keeps the current option. REVISE names the one option the rule now supports. DEFER authorizes nothing and names the unresolved premise. Cite record ids that are actually in the packet.
          </p>
          <textarea
            className="mt-3 min-h-72 w-full border border-line bg-paper p-3 font-mono text-xs leading-relaxed"
            value={draft}
            spellCheck={false}
            aria-label="Decision JSON"
            onChange={(event) => {
              setDrafts((current) => ({ ...current, [key]: event.target.value }));
              setAttempts((current) => {
                const next = { ...current };
                delete next[key];
                return next;
              });
            }}
          />
          <button
            type="button"
            onClick={submit}
            className="mt-3 min-h-11 bg-accent px-4 text-sm text-paper"
          >
            Score this response
          </button>
        </section>
        {attempt && (
          <ScoreCard
            attempt={attempt}
            onReveal={() =>
              setAttempts((current) => ({
                ...current,
                [key]: { ...attempt, revealed: true },
              }))
            }
            history={history}
            packetIds={packet?.evidenceIds ?? []}
          />
        )}
      </div>
    </div>
  );
}

function ScoreCard({
  attempt,
  onReveal,
  history,
  packetIds,
}: {
  attempt: { score: Score | null; error: string | null; revealed: boolean };
  onReveal: () => void;
  history: History;
  packetIds: string[];
}) {
  if (attempt.score && !attempt.score.scorable) {
    return (
      <section className="border border-line bg-paper-2 p-4" role="alert">
        <h2 className="text-sm font-medium">Fixture integrity failure</h2>
        <p className="mt-2 text-sm leading-relaxed">{attempt.score.integrityError}</p>
        <p className="mt-2 text-sm text-muted">No outcome is awarded. This history is excluded from outcome totals; it is not a reader failure.</p>
      </section>
    );
  }
  if (attempt.error || !attempt.score || !attempt.score.formatOk) {
    return (
      <section className="border border-line bg-paper-2 p-4">
        <h2 className="text-sm font-medium">Format failure</h2>
        <p className="mt-2 text-sm leading-relaxed">
          {attempt.error ?? attempt.score?.formatError ?? "The response could not be scored."}
        </p>
        <p className="mt-2 text-sm text-muted">Primary outcome is 0. This is a scored failure, not a transport error.</p>
      </section>
    );
  }
  const score = attempt.score;
  return (
    <section className="border border-line bg-inset p-4">
      <div className="flex items-end justify-between gap-4">
        <div>
          <p className="font-mono text-xs tracking-widest text-muted uppercase">Primary outcome</p>
          <p className="text-4xl font-medium tracking-tight">{score.primary}</p>
          <p className="text-sm text-muted">Grounded selective accuracy. Both decisions, or nothing.</p>
        </div>
        <dl className="grid grid-cols-2 gap-x-4 gap-y-1 text-sm">
          <dt className="text-muted">Target</dt>
          <dd className="font-mono">{score.targetGrounded}</dd>
          <dt className="text-muted">Control</dt>
          <dd className="font-mono">{score.controlGrounded}</dd>
          <dt className="text-muted">Action only</dt>
          <dd className="font-mono">{score.actionOnly}</dd>
        </dl>
      </div>
      <ul className="mt-4 space-y-2">
        {score.decisions.map((decision) => (
          <li key={decision.decisionId} className="border border-line bg-paper px-3 py-2 text-sm">
            <span className="font-mono text-xs">{decision.decisionId}</span>
            <span className="ml-2">{decision.grounded ? "Grounded" : "Not grounded"}</span>
            <span className="mt-1 block text-muted">
              {[
                decision.actionOk ? null : "action",
                decision.optionOk ? null : "option",
                decision.premisesOk ? null : "premises",
                decision.unresolvedOk ? null : "unresolved",
                decision.supportOk ? null : "support set",
                decision.evidenceInPacket ? null : "not in packet",
              ]
                .filter(Boolean)
                .join(" · ") || "Accepted support set, and it was in the packet."}
            </span>
          </li>
        ))}
      </ul>
      {!attempt.revealed ? (
        <button type="button" onClick={onReveal} className="mt-4 min-h-11 border border-ink px-4 text-sm">
          Reveal evaluator key
        </button>
      ) : (
        <Reveal history={history} packetIds={packetIds} />
      )}
    </section>
  );
}

function Reveal({ history, packetIds }: { history: History; packetIds: string[] }) {
  const solved = solve(history.model);
  const sibling = CORPUS.find(
    (item) => item.familyId === history.familyId && item.pairId === history.pairId && item.id !== history.id,
  );
  return (
    <div className="mt-4 space-y-3 border-t border-line pt-4">
      <p className="font-mono text-xs tracking-widest text-muted uppercase">
        Evaluator key · {history.pairTitle} · {history.side} side
      </p>
      {solved.map((decision) => (
        <div key={decision.decisionId} className="border border-line bg-paper px-3 py-2 text-sm">
          <p className="font-mono text-xs">{decision.decisionId}</p>
          <p className="mt-1">
            {decision.action}
            {decision.optionId ? ` → ${decision.optionId}` : " → no option"}
          </p>
          <p className="text-muted">
            Rule {decision.matchedRuleId}. Premises {decision.decisivePremiseIds.join(", ") || "none"}.
            Unresolved {decision.unresolvedPremiseIds.join(", ") || "none"}.
          </p>
        </div>
      ))}
      <p className="text-sm text-muted">
        Packet held {packetIds.length ? packetIds.join(", ") : "no records"}.
        {sibling ? ` Matched history: ${sibling.blindLabel}.` : ""} The matched histories were not shown together during the trial.
      </p>
    </div>
  );
}

function Bench({
  history,
  arm,
  onArm,
  onHistory,
}: {
  history: History;
  arm: ArmId;
  onArm: (arm: ArmId) => void;
  onHistory: (id: string) => void;
}) {
  const [full, setFull] = useState(false);
  const diagnostics = useMemo(() => diagnoseHistory(history), [history]);
  const current = diagnostics.find((row) => row.arm === arm) ?? diagnostics[0];
  const sibling = CORPUS.find(
    (item) => item.familyId === history.familyId && item.pairId === history.pairId && item.id !== history.id,
  );
  const diff = sibling
    ? history.messages.find((message, index) => message.text !== sibling.messages[index]?.text || message.effectiveAt !== sibling.messages[index]?.effectiveAt)
    : undefined;
  const visible = history.messages.filter((message) => full || message.id);

  return (
    <div className="space-y-4">
      <p className="border border-line bg-paper-2 px-4 py-3 text-sm leading-relaxed">
        Author bench. The evaluator key is visible here. Do not treat oracle scores as a model result. Hybrid remains MECHANISM_NOT_TESTED.
      </p>
      <div className="grid gap-4 lg:grid-cols-[16rem_minmax(0,1fr)]">
        <HistoryPick history={history} onHistory={onHistory} blind={false} />
        <div className="text-sm leading-relaxed">
          <p className="font-medium">{history.familyTitle}</p>
          <p className="text-muted">
            {history.pairTitle}. This side is {history.side}. The matched history is {sibling?.blindLabel ?? "missing"}.
            {diff ? ` They differ at ${diff.id ?? "a chatter line"}, message ${diff.index}.` : ""}
          </p>
        </div>
      </div>
      <div className="grid gap-6 lg:grid-cols-2">
        <section className="border border-line bg-inset">
          <header className="flex items-center justify-between border-b border-line px-4 py-3">
            <h2 className="text-sm font-medium">Public history</h2>
            <button type="button" className="min-h-11 text-sm text-accent" onClick={() => setFull((value) => !value)}>
              {full ? "Records only" : "All 80 messages"}
            </button>
          </header>
          <ol className="max-h-[36rem] divide-y divide-line overflow-auto">
            {visible.map((message) => (
              <MessageRow key={message.index} message={message} mark={message.id === diff?.id} />
            ))}
          </ol>
        </section>
        <div className="space-y-4">
          <section className="border border-line bg-inset p-4">
            <h2 className="text-sm font-medium">Reference solver</h2>
            <ul className="mt-3 space-y-2">
              {solve(history.model).map((decision) => (
                <li key={decision.decisionId} className="border border-line bg-paper px-3 py-2 text-sm">
                  <p className="font-mono text-xs">{decision.decisionId}</p>
                  <p>
                    {decision.action}
                    {decision.optionId ? ` → ${decision.optionId}` : ""}
                  </p>
                  <p className="text-muted">
                    {decision.premiseTrace
                      .map((row) =>
                        row.supportCount
                          ? `${row.premiseId} supports ${row.supportCount}`
                          : `${row.premiseId} ${row.known ? String(row.value) : "unknown"}`,
                      )
                      .join(" · ")}
                  </p>
                </li>
              ))}
            </ul>
          </section>
          <ArmPick arm={arm} onArm={onArm} />
          {current && (
            <section className="border border-line bg-paper px-4 py-3 text-sm leading-relaxed">
              <p>
                {current.score.scorable ? `Oracle on this packet: primary ${current.score.primary}.` : `Fixture integrity failure: ${current.score.integrityError}`} Complete support{" "}
                {current.supportAvailable ? "present" : "missing"}.
                {current.score.missedRevision ? " Missed a revision." : ""}
                {current.score.falseRevision ? " False revision." : ""}
                {current.score.inappropriateCommitment ? " Committed under DEFER." : ""}
              </p>
              <p className="mt-2 font-mono text-xs text-muted">{current.packet.evidenceIds.join(" ")}</p>
              <p className="mt-2 text-muted">
                The oracle applies the formal policy to packet-visible events. It is not a deployable reader and cannot establish an HME advantage.
              </p>
            </section>
          )}
        </div>
      </div>
    </div>
  );
}

function Protocol() {
  return (
    <article className="max-w-3xl space-y-8 text-sm leading-relaxed">
      <section>
        <h2 className="text-lg font-medium tracking-tight">Question</h2>
        <p className="mt-2">
          Under the same reader and memory-packet allowance, does an HME retrieval contribution improve evidence-grounded decision revision beyond ordinary retrieval and a structured decision ledger?
        </p>
        <p className="mt-2 text-muted">
          This workbench does not answer that question. It implements the proposed task so the contracts can be reviewed. Status remains DESIGN. Nothing here is LOCKED_NOT_EXECUTED.
        </p>
      </section>
      <section>
        <h2 className="text-lg font-medium tracking-tight">Actions</h2>
        <table className="mt-3 w-full border-collapse text-left">
          <thead>
            <tr className="border-b border-line font-mono text-xs tracking-wide text-muted uppercase">
              <th className="py-2 pr-3 font-normal">Action</th>
              <th className="py-2 font-normal">Required meaning</th>
            </tr>
          </thead>
          <tbody>
            <tr className="border-b border-line">
              <td className="py-2 pr-3 font-mono text-xs">RETAIN</td>
              <td className="py-2">The declared policy still supports the current option.</td>
            </tr>
            <tr className="border-b border-line">
              <td className="py-2 pr-3 font-mono text-xs">REVISE</td>
              <td className="py-2">The policy now supports exactly one other option.</td>
            </tr>
            <tr>
              <td className="py-2 pr-3 font-mono text-xs">DEFER</td>
              <td className="py-2">A required fact is unresolved. Do not authorize an option. Withdrawing a source does not prove the opposite.</td>
            </tr>
          </tbody>
        </table>
      </section>
      <section>
        <h2 className="text-lg font-medium tracking-tight">Four matched pairs</h2>
        <ul className="mt-2 space-y-2">
          <li>Changed constraint. The requirement lifts on the queried project, or only on a different project.</li>
          <li>Withdrawn evidence. The sole support is withdrawn, or an independent test still stands.</li>
          <li>Scoped exception. The exception names the queried project, or only a similar one.</li>
          <li>Validity and timing. The same update is effective before the cutoff, or scheduled after it.</li>
        </ul>
        <p className="mt-2 text-muted">
          Each family holds eight histories: three target REVISE, four target RETAIN, one target DEFER. The control decision always stays. The fixture has four families, 32 histories. The proposal’s 480-history matrix is a planning count, not this corpus.
        </p>
      </section>
      <section>
        <h2 className="text-lg font-medium tracking-tight">What would count later</h2>
        <p className="mt-2">
          A history scores 1 only when both decisions have the correct action, option, premises, and an accepted support set that was actually in the packet. Families, not messages, would be the resampling unit. The proposed gates — five points over full NN and over the ledger, a field contribution above zero, and tight bounds on false revision and control damage — are review margins, not findings.
        </p>
      </section>
      <section>
        <h2 className="text-lg font-medium tracking-tight">What this does not claim</h2>
        <p className="mt-2">
          No autonomous judgment, no causal faithfulness of explanations, no consciousness, no physical QOFT validity, no consolidation result, and no general superiority of holographic memory. The lexical arms are signed-hash stand-ins, not CM-1’s pinned embedder. The hybrid field is not linked.
        </p>
      </section>
    </article>
  );
}

function Checks() {
  const failed = PREFLIGHT.filter((check) => !check.pass).length;
  return (
    <div className="space-y-8">
      <section>
        <h2 className="text-lg font-medium tracking-tight">Preflight</h2>
        <p className="mt-2 text-sm text-muted">
          {failed === 0 ? "All fixture checks passed." : `${failed} checks failed.`} These checks guard the generator. They are not an evaluation.
        </p>
        <ul className="mt-4 divide-y divide-line border-y border-line">
          {PREFLIGHT.map((check) => (
            <li key={check.id} className="grid gap-1 py-3 sm:grid-cols-[14rem_minmax(0,1fr)]">
              <p className="font-mono text-xs">
                <span className={check.pass ? "text-accent" : "text-ink"}>{check.pass ? "PASS" : "FAIL"}</span>
                <span className="mt-1 block text-muted">{check.id}</span>
              </p>
              <p className="text-sm leading-relaxed">{check.detail}</p>
            </li>
          ))}
        </ul>
      </section>
      <section>
        <h2 className="text-lg font-medium tracking-tight">Oracle on the fixture packets</h2>
        <p className="mt-2 max-w-3xl text-sm leading-relaxed text-muted">
          A perfect policy-applier, restricted to each packet. Use it to see whether the needed records survived retrieval. It is not a reader model, and a higher number is not an HME advantage. Hybrid copies the projected arm because the field is not connected.
          Histories with fixture integrity failures are excluded from outcome totals.
        </p>
        <div className="mt-4 overflow-x-auto">
          <table className="w-full border-collapse text-left text-sm">
            <thead>
              <tr className="border-b border-line font-mono text-xs tracking-wide text-muted uppercase">
                <th className="py-2 pr-3 font-normal">Arm</th>
                <th className="py-2 pr-3 font-normal">Grounded</th>
                <th className="py-2 pr-3 font-normal">Support</th>
                <th className="py-2 pr-3 font-normal">Missed</th>
                <th className="py-2 font-normal">False rev.</th>
              </tr>
            </thead>
            <tbody>
              {ARM_SUMMARY.map((row) => (
                <tr key={row.arm} className="border-b border-line">
                  <td className="py-2 pr-3">
                    {ARM_LABEL[row.arm]}
                    {row.invalidHistories > 0 && <span className="mt-1 block text-xs">{row.invalidHistories} unscorable</span>}
                    {row.fieldStatus === "MECHANISM_NOT_TESTED" && (
                      <span className="mt-1 block font-mono text-xs text-muted">MECHANISM_NOT_TESTED</span>
                    )}
                  </td>
                  <td className="py-2 pr-3 font-mono">{row.grounded}/{row.histories}</td>
                  <td className="py-2 pr-3 font-mono">{row.supportAvailable}/{row.histories}</td>
                  <td className="py-2 pr-3 font-mono">{row.missedRevision}</td>
                  <td className="py-2 font-mono">{row.falseRevision}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
      <section>
        <h2 className="text-lg font-medium tracking-tight">Baselines with no grounded credit</h2>
        <p className="mt-2 text-sm text-muted">
          These guess without the required premises and support sets. Always retain names the recorded option; always revise picks the first different public option, if one exists. Action-only checks both action and option. Grounded credit still requires evidence.
        </p>
        <ul className="mt-3 divide-y divide-line border-y border-line">
          {BASELINE_SUMMARY.map((row) => (
            <li key={row.baseline} className="flex items-baseline justify-between gap-4 py-3 text-sm">
              <span>{row.label}</span>
              <span className="font-mono text-xs text-muted">
                grounded {row.grounded}/{row.histories} · action-only {row.actionOnly}/{row.histories}
                {row.invalidHistories > 0 ? ` · ${row.invalidHistories} unscorable` : ""}
              </span>
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}

function ExportPanel() {
  function saveCorpus() {
    const payload = {
      study: "HME-CM-REV-1",
      status: "ILLUSTRATIVE_FIXTURE",
      warning:
        "Not a registered evaluation. No model was called. Hybrid field status is MECHANISM_NOT_TESTED. Do not cite these oracle counts as efficacy.",
      reviewedAgainstCommit: "11b8d916b7708d3b219984d94d9919fd91519c43",
      histories: CORPUS,
    };
    download("decision_revision_v1.fixture.json", JSON.stringify(payload, null, 2), "application/json");
  }

  function saveNote() {
    download(
      "decision_revision_v1.NOTE.md",
      `# HME-CM-REV-1 illustrative fixture\n\nStatus: DESIGN. This note accompanies the workbench, not a committed HME result.\n\nSuggested repository layout when this is later copied beside CM-1, without editing CM-1:\n\n- experiments/decision_revision_v1/generator — four families, eight histories, eighty messages\n- experiments/decision_revision_v1/solver — reference actions from the policy model\n- experiments/decision_revision_v1/memory — five packet builders over public history only\n- experiments/decision_revision_v1/score — grounded selective accuracy\n- experiments/decision_revision_v1/preflight — pair diffs, leakage, budgets, field-not-tested\n\nThe lexical arms are signed-hash stand-ins. The CM-1 field readout is not linked.\n`,
      "text/markdown",
    );
  }

  return (
    <div className="max-w-3xl space-y-6">
      <section className="space-y-3 text-sm leading-relaxed">
        <h2 className="text-lg font-medium tracking-tight">Take the fixture with you</h2>
        <p>
          The running bench is the implementation: generator, independent solver, ledger, extractive summary, lexical stand-ins, scorer, and preflight. Export writes the 32 histories, including the hidden key, marked as a fixture.
        </p>
        <p className="text-muted">
          Open items before any registration remain open: exact clause matcher for paraphrased summaries, frozen margins, pinned reader and embedder, template partitions, and source hashes.
        </p>
      </section>
      <div className="flex flex-wrap gap-3">
        <button type="button" onClick={saveCorpus} className="min-h-11 bg-accent px-4 text-sm text-paper">
          Download fixture JSON
        </button>
        <button type="button" onClick={saveNote} className="min-h-11 border border-ink px-4 text-sm">
          Download layout note
        </button>
        <a href="./decision_revision_v1.zip" download="decision_revision_v1.zip" className="inline-flex min-h-11 items-center border border-ink px-4 text-sm">
          Download source zip
        </a>
      </div>
      <pre className="overflow-x-auto border border-line bg-inset p-4 font-mono text-xs leading-relaxed">
{`experiments/decision_revision_v1/
  generator     matched pairs, public messages, hidden model
  solver        RETAIN / REVISE / DEFER from effective facts
  memory        summary, lexical NN, projection, hybrid, ledger
  score         both decisions, support set, packet membership
  preflight     one-message pair diff, key leakage, 512-word cap`}
      </pre>
    </div>
  );
}
