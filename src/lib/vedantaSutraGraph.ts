import { getCollection } from "astro:content";
import govindaBhashyaSutraMap from "../data/govinda-bhashya-sutra-map.json";

// Extracts [वे.सू. …] / [ब्र.सू. …] (Vedanta-sutra / Brahma-sutra) citations
// from the three Sandarbha works' own markdown bodies at build time. Shared
// by the citation-graph page and the per-sutra research page, so both stay
// in sync with the same extraction and always regenerate from live content.
//
// Govinda-bhashya (Baladeva Vidyabhushana's own sutra-by-sutra commentary)
// is added separately: it doesn't CITE sutras by number the way the
// Sandarbhas do (it quotes each sutra's own text directly), so there's no
// "[ब्र.सू. …]" bracket to scan for -- instead govinda-bhashya-sutra-map.json
// (built by tools/docx-iast-to-devanagari/map_govinda_bhashya_sutras.py,
// grounded against the live site markdown's own `<p class="sutra">` text)
// links each sutra number straight to the adhikarana that comments on it,
// with a real deep link into that page.

export const DEVNUMS = "०१२३४५६७८९";
const DEVMAP: Record<string, number> = { "०": 0, "१": 1, "२": 2, "३": 3, "४": 4, "५": 5, "६": 6, "७": 7, "८": 8, "९": 9 };
export const toDevDigits = (n: number) => String(n).split("").map((d) => DEVNUMS[Number(d)]).join("");
export const devToNum = (s: string) => Number(s.split("").map((c) => DEVMAP[c]).join(""));
export const sutraSlug = (a: number, p: number, s: number) => `${a}.${p}.${s}`;

const CITE_RE = /\[((?:वे\.सू्?\.|ब्र\.सू्?\.)[^\]]*)\]/g;
// JS \d is ASCII-only, unlike Python's re (which matches Unicode decimal
// digits by default) -- these citations use Devanagari अंक, so match them
// explicitly rather than \d.
const NUM_RE = /([०-९]+)\.([०-९]+)\.([०-९]+)/;

const WORK_LABEL: Record<string, string> = {
	"tattva-sandarbha": "तत्त्वसन्दर्भः",
	"bhagavat-sandarbha": "भागवतसन्दर्भः",
	"paramatma-sandarbha": "परमात्मसन्दर्भः",
};
// Romanized names for the English UI chrome (stat-tile labels, panel text,
// research page) -- the graph's own node labels (work names, sutra numbers,
// section headings, quoted commentary) stay in Devanagari, since that's the
// primary-source content being visualized, not page furniture.
export const WORK_IAST: Record<string, string> = {
	तत्त्वसन्दर्भः: "Tattva-sandarbha",
	भागवतसन्दर्भः: "Bhagavat-sandarbha",
	परमात्मसन्दर्भः: "Paramatma-sandarbha",
	गोविन्दभाष्यम्: "Govinda-bhashya",
};
export const GOVINDA_BHASHYA_WORK = "गोविन्दभाष्यम्";
export const WORKS = ["तत्त्वसन्दर्भः", "भागवतसन्दर्भः", "परमात्मसन्दर्भः", GOVINDA_BHASHYA_WORK];

interface GovindaBhashyaMapEntry {
	workSlug: string;
	file: string;
	sectionIndex: number;
	heading: string;
}
const GB_SUTRA_MAP = govindaBhashyaSutraMap as unknown as Record<string, GovindaBhashyaMapEntry>;

function shortHeading(h: string | null): string {
	if (h && h.startsWith("श्री-सर्व-संवादिन्याः")) return "सार-निष्कर्षः";
	return h ?? "?";
}

export interface Cite {
	work: string;
	heading: string;
	raw: string;
	context: string;
	href?: string;
}
export interface SutraNode {
	id: string;
	adhyaya: number;
	pada: number;
	sutra: number;
	label: string;
	abbrevs: string[];
	cites: Cite[];
}
export interface SectionNode {
	id: string;
	work: string;
	heading: string;
	count: number;
	sutraIds: string[];
	href?: string;
	sortFile?: string;
	sortIndex?: number;
}

export interface VedantaSutraGraphData {
	sutras: SutraNode[];
	sections: SectionNode[];
	citationCount: number;
}

export async function getVedantaSutraGraphData(): Promise<VedantaSutraGraphData> {
	const base = import.meta.env.BASE_URL;
	const allEntries = await getCollection("granthas");
	const relevant = allEntries.filter((e) => e.data.workSlug in WORK_LABEL);

	const sutraMap = new Map<string, SutraNode>();
	const sectionMap = new Map<string, SectionNode>();
	let citationCount = 0;

	for (const entry of relevant) {
		const work = WORK_LABEL[entry.data.workSlug];
		const lines = (entry.body ?? "").split(/\r?\n/);
		let heading: string | null = null;
		// 0-indexed position of the current "## " heading within this file,
		// matching the `id="section-{si}"` convention [id].astro assigns by
		// position -- lets a citation's href deep-link straight to it.
		let sectionIndex = -1;

		for (const line of lines) {
			const h2 = /^##\s+(.*)$/.exec(line);
			if (h2) {
				sectionIndex += 1;
				heading = h2[1].trim();
				continue;
			}
			for (const m of line.matchAll(CITE_RE)) {
				const raw = m[1];
				const numMatch = NUM_RE.exec(raw);
				if (!numMatch) continue;
				const adhyaya = devToNum(numMatch[1]);
				const pada = devToNum(numMatch[2]);
				const sutra = devToNum(numMatch[3]);
				const abbrev = raw.startsWith("वे") ? "वे.सू." : "ब्र.सू.";
				const cleanHeading = shortHeading(heading);
				const href = `${base}granthas/${entry.data.workSlug}/${entry.id}/#section-${sectionIndex}`;

				citationCount += 1;

				const sid = `s:${adhyaya}.${pada}.${sutra}`;
				let sNode = sutraMap.get(sid);
				if (!sNode) {
					sNode = {
						id: sid,
						adhyaya,
						pada,
						sutra,
						label: `${toDevDigits(adhyaya)}.${toDevDigits(pada)}.${toDevDigits(sutra)}`,
						abbrevs: [],
						cites: [],
					};
					sutraMap.set(sid, sNode);
				}
				if (!sNode.abbrevs.includes(abbrev)) sNode.abbrevs.push(abbrev);
				sNode.cites.push({ work, heading: cleanHeading, raw, context: line.trim(), href });

				const secKey = `a:${work}|${cleanHeading}`;
				let secNode = sectionMap.get(secKey);
				if (!secNode) {
					secNode = { id: secKey, work, heading: cleanHeading, count: 0, sutraIds: [], href };
					sectionMap.set(secKey, secNode);
				}
				secNode.count += 1;
				if (!secNode.sutraIds.includes(sid)) secNode.sutraIds.push(sid);
			}
		}
	}

	// Link every sutra already in the graph (cited by one of the three
	// Sandarbhas above) to the Govinda-bhashya adhikarana that comments on
	// it, where the mapping has one -- no new sutra nodes are created for
	// this, only new edges/cites onto the existing ones.
	for (const [sutraKey, entry] of Object.entries(GB_SUTRA_MAP)) {
		const sid = `s:${sutraKey}`;
		const sutraNode = sutraMap.get(sid);
		if (!sutraNode) continue; // this sutra isn't cited by any Sandarbha in the graph

		const href = `${base}granthas/${entry.workSlug}/${entry.file}/#section-${entry.sectionIndex}`;
		sutraNode.cites.push({
			work: GOVINDA_BHASHYA_WORK,
			heading: entry.heading,
			raw: "",
			context: "This sūtra is quoted and explained directly in Govinda-bhāṣya.",
			href,
		});

		const sectionKey = `a:${GOVINDA_BHASHYA_WORK}|${entry.file}|${entry.sectionIndex}`;
		let node = sectionMap.get(sectionKey);
		if (!node) {
			node = {
				id: sectionKey,
				work: GOVINDA_BHASHYA_WORK,
				heading: entry.heading,
				count: 0,
				sutraIds: [],
				href,
				sortFile: entry.file,
				sortIndex: entry.sectionIndex,
			};
			sectionMap.set(sectionKey, node);
		}
		node.count += 1;
		if (!node.sutraIds.includes(sid)) node.sutraIds.push(sid);
	}

	const sutras = [...sutraMap.values()].sort((a, b) => a.adhyaya - b.adhyaya || a.pada - b.pada || a.sutra - b.sutra);
	const sections = [...sectionMap.values()].sort((a, b) => {
		if (a.work !== b.work) return WORKS.indexOf(a.work) - WORKS.indexOf(b.work);
		if (a.sortFile !== undefined && b.sortFile !== undefined) {
			if (a.sortFile !== b.sortFile) return a.sortFile.localeCompare(b.sortFile);
			return (a.sortIndex ?? 0) - (b.sortIndex ?? 0);
		}
		const am = /अनुच्छेदः\s+(.+)$/.exec(a.heading);
		const bm = /अनुच्छेदः\s+(.+)$/.exec(b.heading);
		if (am && bm) return devToNum(am[1]) - devToNum(bm[1]);
		if (am) return -1;
		if (bm) return 1;
		return a.heading.localeCompare(b.heading);
	});

	return { sutras, sections, citationCount };
}
