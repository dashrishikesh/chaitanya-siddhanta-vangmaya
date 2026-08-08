import { marked } from "marked";

export interface ParsedSubsection {
	heading: string;
	html: string;
}

export interface ParsedSection {
	heading: string;
	introHtml: string;
	subsections: ParsedSubsection[];
}

export interface ParsedGrantha {
	openingHtml: string;
	sections: ParsedSection[];
}

/**
 * Splits a grantha's markdown body into level-2 sections (root verses, editorial
 * notes) and, within each, level-3 subsections (per-commentary text). Headings
 * are kept verbatim so callers can match them against frontmatter metadata
 * (e.g. `commentaries[].label`) rather than this parser hard-coding names.
 */
export function parseGranthaBody(body: string): ParsedGrantha {
	const lines = body.split(/\r?\n/);

	const preambleLines: string[] = [];
	const sections: ParsedSection[] = [];
	let currentSection: ParsedSection | null = null;
	let currentSubsection: ParsedSubsection | null = null;
	let mode: "pre" | "section-intro" | "subsection" = "pre";

	for (const line of lines) {
		const h2 = /^##\s+(.*)$/.exec(line);
		const h3 = /^###\s+(.*)$/.exec(line);

		if (h2) {
			currentSection = { heading: h2[1].trim(), introHtml: "", subsections: [] };
			sections.push(currentSection);
			currentSubsection = null;
			mode = "section-intro";
			continue;
		}

		if (h3 && currentSection) {
			currentSubsection = { heading: h3[1].trim(), html: "" };
			currentSection.subsections.push(currentSubsection);
			mode = "subsection";
			continue;
		}

		if (mode === "pre") {
			preambleLines.push(line);
		} else if (mode === "section-intro" && currentSection) {
			currentSection.introHtml += `${line}\n`;
		} else if (mode === "subsection" && currentSubsection) {
			currentSubsection.html += `${line}\n`;
		}
	}

	// "---" lines are structural separators between headings in this document
	// format, not intentional dividers within a section's own content.
	const stripSeparators = (raw: string) =>
		raw
			.split(/\r?\n/)
			.filter((line) => !/^\s*-{3,}\s*$/.test(line))
			.join("\n");

	const render = (raw: string) =>
		(marked.parse(stripSeparators(raw).trim(), { async: false }) as string).trim();

	return {
		openingHtml: render(preambleLines.join("\n")),
		sections: sections.map((section) => ({
			heading: section.heading,
			introHtml: render(section.introHtml),
			subsections: section.subsections.map((sub) => ({
				heading: sub.heading,
				html: render(sub.html),
			})),
		})),
	};
}
