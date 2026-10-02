import { GUIDE, guideMarkdown, type GuideBlock } from "../../../experiments/decision_revision_v1/user-guide.ts";

function downloadGuide() {
  const blob = new Blob([guideMarkdown()], { type: "text/markdown" });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = "decision_revision_v1.USER_GUIDE.md";
  anchor.click();
  URL.revokeObjectURL(url);
}

function jump(id: string) {
  document.getElementById(id)?.scrollIntoView({ behavior: "smooth", block: "start" });
}

export function Guide({ onTryExample }: { onTryExample: () => void }) {
  return (
    <article className="max-w-3xl">
      <div className="flex flex-wrap items-center gap-3">
        <button type="button" onClick={onTryExample} className="min-h-11 bg-accent px-4 text-sm text-paper">
          Open the worked example
        </button>
        <button type="button" onClick={downloadGuide} className="min-h-11 border border-ink px-4 text-sm">
          Download guide
        </button>
        <a
          href="./decision_revision_v1.zip"
          download="decision_revision_v1.zip"
          className="inline-flex min-h-11 items-center border border-ink px-4 text-sm"
        >
          decision_revision_v1.zip
        </a>
      </div>
      <nav className="mt-6 flex flex-wrap gap-2" aria-label="Guide sections">
        {GUIDE.map((section) => (
          <button
            key={section.id}
            type="button"
            onClick={() => jump(section.id)}
            className="min-h-11 border border-line bg-inset px-3 text-sm text-ink"
          >
            {section.title}
          </button>
        ))}
      </nav>
      <div className="mt-8 space-y-10 text-sm leading-relaxed">
        {GUIDE.map((section) => (
          <section key={section.id} id={section.id} className="scroll-mt-4">
            <h2 className="text-lg font-medium tracking-tight">{section.title}</h2>
            <div className="mt-3 space-y-3">
              {section.blocks.map((block, index) => (
                <Block key={`${section.id}-${index}`} block={block} />
              ))}
            </div>
          </section>
        ))}
      </div>
    </article>
  );
}

function Block({ block }: { block: GuideBlock }) {
  if (block.kind === "p") return <p>{block.text}</p>;
  if (block.kind === "note") {
    return <p className="border border-line bg-paper-2 px-4 py-3 text-muted">{block.text}</p>;
  }
  if (block.kind === "ul") {
    return (
      <ul className="list-disc space-y-2 pl-5">
        {block.items.map((item) => (
          <li key={item}>{item}</li>
        ))}
      </ul>
    );
  }
  if (block.kind === "pre") {
    return (
      <pre className="overflow-x-auto border border-line bg-inset p-4 font-mono text-xs leading-relaxed">{block.text}</pre>
    );
  }
  return (
    <div className="overflow-x-auto">
      <table className="w-full border-collapse text-left">
        <thead>
          <tr className="border-b border-line font-mono text-xs tracking-wide text-muted uppercase">
            {block.headers.map((header) => (
              <th key={header} className="py-2 pr-3 font-normal">
                {header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {block.rows.map((row) => (
            <tr key={row.join("|")} className="border-b border-line">
              {row.map((cell) => (
                <td key={cell} className="py-2 pr-3 align-top">
                  {cell}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
