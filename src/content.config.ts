import { defineCollection, z } from "astro:content";
import { glob } from "astro/loaders";

const scriptSet = z.object({
	devanagari: z.string(),
	iast: z.string(),
	english: z.string().optional(),
});

const granthas = defineCollection({
	loader: glob({ pattern: "**/*.md", base: "./src/content/granthas" }),
	schema: z.object({
		title: scriptSet,
		work: scriptSet,
		corpusName: z
			.object({
				devanagari: z.string(),
				iast: z.string(),
				note: z.string().optional(),
			})
			.optional(),
		workSlug: z.string(),
		partOf: z.string(),
		sequence: z.number(),
		author: z.string(),
		authorGroup: z.string(),
		goswami: z.string(),
		category: z.string(),
		commentaries: z.array(
			z.object({
				id: z.string(),
				label: z.string(),
				labelIast: z.string(),
				commentator: z.string(),
				note: z.string().optional(),
			}),
		),
		availableScripts: z.array(z.string()),
	}),
});

export const collections = { granthas };
