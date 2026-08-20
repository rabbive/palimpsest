import { useState, type ReactNode } from "react";
import { AnimatePresence, motion } from "motion/react";
import {
  ArrowDown,
  ArrowRight,
  ArrowUpRight,
  Check,
  ChevronRight,
  CircleDot,
  Database,
  GitBranch,
  Github,
  Layers3,
  LockKeyhole,
  Play,
  Search,
  ShieldCheck,
  Sparkles,
  Terminal,
  X,
  Zap,
} from "lucide-react";
import { AnimatedBadge } from "@/components/motion/animated-badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/motion/tabs";
import { TextReveal } from "@/components/motion/text-animation";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";

const REPO_URL = "https://github.com/rabbive/palimpsest";

const oldFact = {
  id: "f_8_0004_052",
  subject: "user",
  predicate: "OTHER",
  object: "first 30 days as senior producer",
};

const newFact = {
  id: "f_8_0004_053",
  subject: "user",
  predicate: "OTHER",
  object: "june 15",
};

const steps = [
  { value: "timeline", label: "01 / Timeline", icon: GitBranch },
  { value: "current", label: "02 / Current view", icon: ShieldCheck },
  { value: "abstention", label: "03 / Abstention", icon: Search },
  { value: "results", label: "04 / Results", icon: Zap },
];

function LogoMark() {
  return (
    <span className="relative flex h-7 w-7 items-center justify-center rounded-[8px] border border-primary/50 bg-primary/10 text-primary">
      <span className="absolute h-3 w-3 rotate-45 rounded-[3px] border border-primary" />
      <span className="h-1.5 w-1.5 rounded-full bg-primary" />
    </span>
  );
}

function SectionKicker({ children }: { children: ReactNode }) {
  return <p className="mb-4 flex items-center gap-2 font-mono text-[11px] uppercase tracking-[0.18em] text-primary"><span className="h-1.5 w-1.5 rounded-full bg-primary shadow-[0_0_12px_rgba(119,183,255,.9)]" />{children}</p>;
}

function FactChip({ fact, status, muted = false }: { fact: typeof oldFact; status: "current" | "historical"; muted?: boolean }) {
  return (
    <motion.div
      layout
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: muted ? 0.5 : 1, y: 0 }}
      className={`rounded-lg border p-4 ${status === "current" ? "border-emerald-400/25 bg-emerald-400/[0.06]" : "border-border bg-secondary/40"}`}
    >
      <div className="mb-3 flex items-center justify-between gap-3">
        <code className="font-mono text-[11px] text-muted-foreground">{fact.id}</code>
        <AnimatedBadge status={status === "current" ? "success" : "neutral"} size="sm" contentKey={status}>{status}</AnimatedBadge>
      </div>
      <div className={status === "historical" ? "text-muted-foreground line-through decoration-muted-foreground/60" : "text-foreground"}>
        <span className="font-mono text-xs text-primary">{fact.subject}</span>
        <span className="mx-2 text-muted-foreground">—</span>
        <span className="font-mono text-xs text-amber-200/80">{fact.predicate}</span>
        <span className="mx-2 text-muted-foreground">—</span>
        <span className="text-sm">{fact.object}</span>
      </div>
    </motion.div>
  );
}

function TimelinePanel() {
  const [replayed, setReplayed] = useState(true);
  const replay = () => {
    setReplayed(false);
    window.setTimeout(() => setReplayed(true), 260);
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-end">
        <div>
          <p className="mb-2 font-mono text-xs text-muted-foreground">dialogue 8 / session 04</p>
          <h2 className="text-xl font-medium tracking-tight">A fact changes. The old one stays readable.</h2>
          <p className="mt-2 max-w-xl text-sm leading-6 text-muted-foreground">PALIMPSEST resolves supersession at write time, so “current” is a stored property—not a guess reconstructed for every question.</p>
        </div>
        <Button variant="outline" size="sm" onClick={replay}><Play className="size-3.5" /> Replay transition</Button>
      </div>

      <div className="relative rounded-xl border border-border bg-[#121212] p-4 sm:p-6">
        <div className="mb-5 flex items-center justify-between font-mono text-[10px] uppercase tracking-[0.14em] text-muted-foreground"><span>write path / reconciliation</span><span>strict chronology</span></div>
        <div className="grid gap-3 sm:grid-cols-[1fr_auto_1fr] sm:items-center">
          <FactChip fact={oldFact} status={replayed ? "historical" : "current"} muted={replayed} />
          <div className="flex items-center justify-center gap-2 py-1 sm:flex-col sm:py-0">
            <ArrowRight className={`size-4 transition-colors ${replayed ? "text-amber-300" : "text-muted-foreground"}`} />
            <span className="font-mono text-[10px] text-amber-200/80">SUPERSEDES</span>
          </div>
          <AnimatePresence mode="wait">
            {replayed ? <FactChip key="new" fact={newFact} status="current" /> : <FactChip key="waiting" fact={newFact} status="current" muted />}
          </AnimatePresence>
        </div>
        <div className="mt-5 flex items-center gap-2 border-t border-border pt-4 text-xs text-muted-foreground"><Check className="size-3.5 text-emerald-400" />No deletion. No read-time re-ranking. The supersession chain remains inspectable.</div>
      </div>
    </div>
  );
}

function CurrentViewPanel() {
  const [filtered, setFiltered] = useState(true);
  return (
    <div className="space-y-6">
      <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-end">
        <div>
          <p className="mb-2 font-mono text-xs text-muted-foreground">hydradb / query contract</p>
          <h2 className="text-xl font-medium tracking-tight">Current view is a hard filter.</h2>
          <p className="mt-2 max-w-xl text-sm leading-6 text-muted-foreground">The schema-declared status field moves the decision out of the language model and onto HydraDB’s query path.</p>
        </div>
        <Button variant="outline" size="sm" onClick={() => setFiltered((value) => !value)}>{filtered ? "Remove filter" : "Apply status filter"}</Button>
      </div>
      <div className="rounded-xl border border-border bg-[#121212] p-4 sm:p-6">
        <div className="flex flex-wrap items-center gap-2 font-mono text-xs"><span className="text-muted-foreground">query</span><span className="rounded-md border border-border bg-secondary px-2 py-1 text-foreground">user / OTHER</span><ArrowRight className="size-3.5 text-muted-foreground" /><span className="rounded-md border border-primary/30 bg-primary/10 px-2 py-1 text-primary">{filtered ? 'status = "current"' : "no metadata filter"}</span></div>
        <div className="mt-6 grid gap-4 md:grid-cols-2">
          <div className="rounded-lg border border-border bg-secondary/20 p-4"><div className="mb-4 flex items-center justify-between"><span className="font-mono text-[11px] uppercase tracking-wider text-muted-foreground">stored memories</span><Badge>{filtered ? "2 facts" : "2 facts"}</Badge></div><div className="space-y-2"><div className={`flex items-center gap-2 rounded-md border border-border p-3 text-xs transition-opacity ${filtered ? "opacity-45" : ""}`}><X className="size-3.5 text-rose-400" /><span className="flex-1 text-muted-foreground">{oldFact.object}</span><span className="font-mono text-[10px] text-muted-foreground">historical</span></div><div className="flex items-center gap-2 rounded-md border border-emerald-400/20 bg-emerald-400/[0.04] p-3 text-xs"><Check className="size-3.5 text-emerald-400" /><span className="flex-1">{newFact.object}</span><span className="font-mono text-[10px] text-emerald-300">current</span></div></div></div>
          <div className="rounded-lg border border-primary/20 bg-primary/[0.04] p-4"><div className="mb-4 flex items-center justify-between"><span className="font-mono text-[11px] uppercase tracking-wider text-primary">query response</span><AnimatedBadge status={filtered ? "success" : "warning"} size="sm" contentKey={String(filtered)}>{filtered ? "1 result" : "2 results"}</AnimatedBadge></div><div className="rounded-md border border-border bg-[#0d0d0d] p-3 font-mono text-xs leading-6"><span className="text-muted-foreground">metadata_filters</span><span className="text-foreground">: </span><span className="text-primary">{filtered ? '{ status: "current" }' : "none"}</span><br /><span className="text-muted-foreground">returned</span><span className="text-foreground">: </span><span className="text-emerald-300">{filtered ? 'f_8_0004_053' : '[f_8_0004_052, f_8_0004_053]'}</span></div></div>
        </div>
      </div>
    </div>
  );
}

function AbstentionPanel() {
  const [question, setQuestion] = useState("What is my current manager?");
  const [asked, setAsked] = useState(true);
  const answerable = question.toLowerCase().includes("date format");
  return (
    <div className="space-y-6">
      <div><p className="mb-2 font-mono text-xs text-muted-foreground">read path / coverage check</p><h2 className="text-xl font-medium tracking-tight">The system can prove when a slot is missing.</h2><p className="mt-2 max-w-xl text-sm leading-6 text-muted-foreground">Before generating an answer, PALIMPSEST decomposes the question and checks graph coverage. No coverage means no confident fiction.</p></div>
      <div className="rounded-xl border border-border bg-[#121212] p-4 sm:p-6">
        <label htmlFor="question" className="mb-2 block font-mono text-[11px] uppercase tracking-wider text-muted-foreground">ask the memory layer</label>
        <div className="flex flex-col gap-2 sm:flex-row"><input id="question" value={question} onChange={(event) => { setQuestion(event.target.value); setAsked(false); }} onKeyDown={(event) => { if (event.key === "Enter") setAsked(true); }} className="h-10 min-w-0 flex-1 rounded-lg border border-input bg-background px-3 text-sm text-foreground outline-none placeholder:text-muted-foreground focus:border-primary/60 focus:ring-2 focus:ring-primary/20" /><Button size="sm" onClick={() => setAsked(true)}>Ask <ArrowUpRight className="size-3.5" /></Button></div>
        <div className="mt-3 flex flex-wrap gap-2"><button onClick={() => { setQuestion("What is my current manager?"); setAsked(true); }} className="font-mono text-[10px] text-muted-foreground transition-colors hover:text-foreground">missing-slot example</button><span className="text-muted-foreground">·</span><button onClick={() => { setQuestion("What date format do I prefer?"); setAsked(true); }} className="font-mono text-[10px] text-muted-foreground transition-colors hover:text-foreground">answerable example</button></div>
        <AnimatePresence mode="wait">
          {asked ? <motion.div key={answerable ? "answer" : "abstain"} initial={{ opacity: 0, y: 5 }} animate={{ opacity: 1, y: 0 }} className={`mt-6 overflow-hidden rounded-lg border ${answerable ? "border-emerald-400/25" : "border-amber-400/25"}`}>
            <div className="flex items-center justify-between border-b border-border bg-secondary/40 px-4 py-3"><div className="flex items-center gap-2 font-mono text-[11px] uppercase tracking-wider text-muted-foreground"><Terminal className="size-3.5" />PALIMPSEST response</div><AnimatedBadge status={answerable ? "success" : "warning"} size="sm">{answerable ? "answered" : "abstained"}</AnimatedBadge></div>
            <pre className="overflow-x-auto bg-[#0d0d0d] p-4 font-mono text-xs leading-6 text-foreground">{answerable ? `answer: "You prefer the month day, year format."\n\nsource: HydraDB / status=current` : `abstained: true\nmissing_slots: ["user / MANAGES"]\nreason: "No fact in memory covers: user / MANAGES"\npartial_matches: []`}</pre>
          </motion.div> : <div className="mt-6 rounded-lg border border-dashed border-border p-8 text-center text-sm text-muted-foreground">Press Ask to run the deterministic demo replay.</div>}
        </AnimatePresence>
      </div>
    </div>
  );
}

function ResultsPanel() {
  const scores = [{ label: "A / full-context stuffing", score: 0.46, color: "bg-muted-foreground" }, { label: "B / HydraDB default", score: 0.34, color: "bg-violet-300" }, { label: "C / PALIMPSEST", score: 0.31, color: "bg-primary" }];
  return (
    <div className="space-y-6"><div><p className="mb-2 font-mono text-xs text-muted-foreground">benchmark / measured honestly</p><h2 className="text-xl font-medium tracking-tight">The mechanism is useful—but the gate is too strict.</h2><p className="mt-2 max-w-xl text-sm leading-6 text-muted-foreground">These are the committed results over 20 questions on dialogues 7 and 8. PALIMPSEST’s answer quality suffered from over-abstention, which the ablations make visible.</p></div><div className="grid gap-3 sm:grid-cols-3">{scores.map((item) => <Card key={item.label} className="bg-[#121212]"><CardContent className="p-4"><div className="mb-3 flex items-center justify-between gap-2"><span className="font-mono text-[10px] uppercase tracking-wider text-muted-foreground">{item.label.split(" /")[0]}</span><span className="font-mono text-lg text-foreground">{item.score.toFixed(2)}</span></div><div className="h-1.5 overflow-hidden rounded-full bg-secondary"><motion.div initial={{ width: 0 }} whileInView={{ width: `${item.score * 100}%` }} viewport={{ once: true }} transition={{ duration: 0.7 }} className={`h-full rounded-full ${item.color}`} /></div><p className="mt-3 text-xs text-muted-foreground">{item.label.split(" / ")[1]}</p></CardContent></Card>)}</div><div className="grid gap-3 md:grid-cols-2"><div className="rounded-xl border border-border bg-[#121212] p-4"><div className="mb-4 flex items-center gap-2 text-sm font-medium"><Layers3 className="size-4 text-primary" />Ablation signal</div><div className="space-y-3 text-xs"><div className="flex justify-between border-b border-border pb-3"><span className="text-muted-foreground">C / full system</span><span>0.31</span></div><div className="flex justify-between border-b border-border pb-3"><span className="text-muted-foreground">C / no coverage</span><span>0.34</span></div><div className="flex justify-between"><span className="text-muted-foreground">C / neither</span><span>0.21</span></div></div></div><div className="rounded-xl border border-border bg-[#121212] p-4"><div className="mb-4 flex items-center gap-2 text-sm font-medium"><Database className="size-4 text-primary" />Cost advantage</div><p className="text-3xl font-medium tracking-tight">7×</p><p className="mt-1 text-xs leading-5 text-muted-foreground">less per question for C than the full-context baseline in the measured run.</p></div></div></div>
  );
}

function DemoShell() {
  const [activeTab, setActiveTab] = useState("timeline");
  return <section id="demo" className="scroll-mt-20 border-y border-border bg-[#0d0d0d] py-20"><div className="mx-auto max-w-6xl px-5 sm:px-8"><div className="mb-8 flex flex-col justify-between gap-4 md:flex-row md:items-end"><div><SectionKicker>interactive replay</SectionKicker><h2 className="text-2xl font-medium tracking-tight sm:text-3xl">See the memory contract in four moves.</h2></div><div className="flex items-center gap-2 font-mono text-[10px] uppercase tracking-wider text-muted-foreground"><span className="h-1.5 w-1.5 rounded-full bg-emerald-400" />verified run / no API key in browser</div></div><Card className="overflow-hidden border-border bg-[#111111] shadow-2xl shadow-black/30"><div className="border-b border-border p-2 sm:p-3"><Tabs value={activeTab} onValueChange={setActiveTab} variant="segment"><TabsList className="w-full flex-wrap justify-start bg-transparent"><TabsTrigger value="timeline" className="gap-2"><GitBranch className="size-3.5" /> <span className="hidden sm:inline">01 / </span>Timeline</TabsTrigger><TabsTrigger value="current" className="gap-2"><ShieldCheck className="size-3.5" /> <span className="hidden sm:inline">02 / </span>Current view</TabsTrigger><TabsTrigger value="abstention" className="gap-2"><Search className="size-3.5" /> <span className="hidden sm:inline">03 / </span>Abstention</TabsTrigger><TabsTrigger value="results" className="gap-2"><Zap className="size-3.5" /> <span className="hidden sm:inline">04 / </span>Results</TabsTrigger></TabsList><TabsContent value="timeline" className="px-3 pb-3 sm:px-4 sm:pb-4"><TimelinePanel /></TabsContent><TabsContent value="current" className="px-3 pb-3 sm:px-4 sm:pb-4"><CurrentViewPanel /></TabsContent><TabsContent value="abstention" className="px-3 pb-3 sm:px-4 sm:pb-4"><AbstentionPanel /></TabsContent><TabsContent value="results" className="px-3 pb-3 sm:px-4 sm:pb-4"><ResultsPanel /></TabsContent></Tabs></div></Card></div></section>;
}

function Architecture() {
  const items = [
    { icon: Sparkles, number: "01", title: "Extract", text: "The LLM turns each chronological session into atomic facts with a closed predicate vocabulary." },
    { icon: GitBranch, number: "02", title: "Reconcile", text: "Every candidate becomes NEW, DUPLICATE, REFINEMENT, SUPERSESSION, or CONTRADICTION." },
    { icon: Database, number: "03", title: "Materialize", text: "Facts live in HydraDB; the SQLite ledger records the write-time chain and inspector state." },
    { icon: ShieldCheck, number: "04", title: "Abstain", text: "The read path checks graph coverage before generation and names a missing slot instead of guessing." },
  ];
  return <section id="architecture" className="scroll-mt-20 py-20"><div className="mx-auto max-w-6xl px-5 sm:px-8"><SectionKicker>under the hood</SectionKicker><div className="grid gap-10 lg:grid-cols-[.8fr_1.2fr]"><div><h2 className="max-w-md text-3xl font-medium tracking-tight sm:text-4xl">A memory system with a write path—and an exit condition.</h2><p className="mt-5 max-w-md text-sm leading-7 text-muted-foreground">Most memory systems optimize for returning something. PALIMPSEST also models the moment when a fact changes, and the moment when the graph has no evidence.</p><div className="mt-8 rounded-lg border border-border bg-card/50 p-4 font-mono text-[11px] leading-6 text-muted-foreground"><span className="text-primary">session</span> → extract → reconcile<br /><span className="text-primary">fact</span> → HydraDB + ledger → current view<br /><span className="text-primary">question</span> → coverage → answer <span className="text-amber-200">or abstention</span></div></div><div className="grid gap-3 sm:grid-cols-2">{items.map((item) => <Card key={item.number} className="group bg-[#141414] transition-colors hover:border-primary/30"><CardHeader className="pb-3"><div className="flex items-center justify-between"><item.icon className="size-4 text-primary" /><span className="font-mono text-[10px] text-muted-foreground">{item.number}</span></div><h3 className="pt-5 text-sm font-medium">{item.title}</h3></CardHeader><CardContent className="text-xs leading-6 text-muted-foreground">{item.text}</CardContent></Card>)}</div></div></div></section>;
}

export function App() {
  return <div className="min-h-screen overflow-hidden bg-background"><div className="pointer-events-none fixed inset-0 -z-0 grid-bg" /><header className="sticky top-0 z-30 border-b border-border bg-background/85 backdrop-blur-xl"><div className="mx-auto flex h-14 max-w-6xl items-center justify-between px-5 sm:px-8"><a href="#top" className="flex items-center gap-2.5 text-sm font-medium tracking-tight"><LogoMark />PALIMPSEST</a><nav className="hidden items-center gap-1 text-xs text-muted-foreground md:flex"><a href="#demo" className="rounded-md px-3 py-2 transition-colors hover:bg-accent hover:text-foreground">Demo</a><a href="#architecture" className="rounded-md px-3 py-2 transition-colors hover:bg-accent hover:text-foreground">Architecture</a><a href={`${REPO_URL}#results`} target="_blank" rel="noreferrer" className="rounded-md px-3 py-2 transition-colors hover:bg-accent hover:text-foreground">Results <ArrowUpRight className="ml-1 inline size-3" /></a></nav><a href={REPO_URL} target="_blank" rel="noreferrer" aria-label="Open PALIMPSEST on GitHub" className="rounded-md p-2 text-muted-foreground transition-colors hover:bg-accent hover:text-foreground"><Github className="size-4" /></a></div></header><main id="top" className="relative z-10"><section className="mx-auto max-w-6xl px-5 pb-20 pt-20 sm:px-8 sm:pt-28"><div className="grid items-center gap-14 lg:grid-cols-[1.1fr_.9fr]"><div><SectionKicker>hydradb / memory infrastructure</SectionKicker><TextReveal as="h1" text={["Memory that knows", "when facts change."]} split="word" whileInView className="max-w-2xl text-5xl font-medium leading-[1.04] tracking-[-0.055em] text-foreground sm:text-7xl" /><p className="mt-7 max-w-xl text-base leading-7 text-muted-foreground sm:text-lg">PALIMPSEST is a write-time reconciliation and graph-property abstention layer for HydraDB memory.</p><div className="mt-8 flex flex-wrap gap-3"><Button size="lg" onClick={() => document.getElementById("demo")?.scrollIntoView({ behavior: "smooth" })}>Explore the demo <ArrowDown className="size-4" /></Button><a href={REPO_URL} target="_blank" rel="noreferrer" className="inline-flex h-11 items-center justify-center gap-2 rounded-lg border border-border bg-transparent px-5 text-sm font-medium text-foreground transition-colors hover:bg-accent">View source <ArrowUpRight className="size-4" /></a></div><div className="mt-8 flex flex-wrap items-center gap-x-5 gap-y-2 text-xs text-muted-foreground"><span className="flex items-center gap-2"><LockKeyhole className="size-3.5" />No secrets in browser</span><span className="flex items-center gap-2"><Check className="size-3.5 text-emerald-400" />190 dialogue-8 sources indexed</span></div></div><Card className="relative overflow-hidden border-border bg-[#141414] shadow-2xl shadow-black/40"><div className="absolute inset-x-0 top-0 h-px glow-line" /><CardHeader className="border-b border-border pb-4"><div className="flex items-center justify-between"><div className="flex items-center gap-2 font-mono text-[10px] uppercase tracking-wider text-muted-foreground"><Terminal className="size-3.5" />palimpsest / run</div><AnimatedBadge status="success" size="sm">indexed</AnimatedBadge></div></CardHeader><CardContent className="space-y-5 p-5"><div className="space-y-3 font-mono text-xs"><div className="flex items-center gap-3"><span className="text-muted-foreground">01</span><span className="text-primary">extract</span><span className="ml-auto text-muted-foreground">atomic facts</span></div><div className="flex items-center gap-3"><span className="text-muted-foreground">02</span><span className="text-primary">reconcile</span><span className="ml-auto text-muted-foreground">5-way classifier</span></div><div className="flex items-center gap-3"><span className="text-muted-foreground">03</span><span className="text-primary">materialize</span><span className="ml-auto text-emerald-300">status=current</span></div><div className="flex items-center gap-3"><span className="text-muted-foreground">04</span><span className="text-primary">abstain</span><span className="ml-auto text-amber-200">when uncovered</span></div></div><Separator /><div className="rounded-lg border border-border bg-[#0e0e0e] p-3 font-mono text-[11px] leading-6"><span className="text-muted-foreground">&gt; </span><span className="text-foreground">current_view</span><br /><span className="text-muted-foreground">&gt; </span><span className="text-emerald-300">old fact hidden · replacement returned</span></div></CardContent></Card></div></section><DemoShell /><Architecture /><section className="border-t border-border py-16"><div className="mx-auto flex max-w-6xl flex-col justify-between gap-6 px-5 sm:px-8 md:flex-row md:items-center"><div><SectionKicker>honest by design</SectionKicker><h2 className="max-w-2xl text-2xl font-medium tracking-tight">The demo shows what worked—and what did not.</h2><p className="mt-3 max-w-2xl text-sm leading-6 text-muted-foreground">The benchmark found over-abstention in the current coverage gate. BYOG relations are documented as a HydraDB read-back limitation. No number is hidden behind a polished surface.</p></div><a href={`${REPO_URL}#limitations`} target="_blank" rel="noreferrer" className="inline-flex shrink-0 items-center gap-2 text-sm text-primary transition-colors hover:text-foreground">Read the limitations <ChevronRight className="size-4" /></a></div></section></main><footer className="border-t border-border"><div className="mx-auto flex max-w-6xl flex-col gap-4 px-5 py-8 text-xs text-muted-foreground sm:px-8 md:flex-row md:items-center md:justify-between"><span className="flex items-center gap-2"><LogoMark />PALIMPSEST / interactive replay</span><span>Built on HydraDB · <a className="text-foreground hover:text-primary" href={REPO_URL} target="_blank" rel="noreferrer">open source on GitHub</a></span></div></footer></div>;
}
