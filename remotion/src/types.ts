import { z } from "zod";

export const WordSchema = z.object({
  text: z.string(),
  start: z.number(),
  end: z.number(),
  emphasize: z.boolean(),
});

export const CardSchema = z.object({
  start: z.number(),
  end: z.number(),
  words: z.array(WordSchema),
});

export const SubtitleStyleSchema = z.object({
  font: z.string(),
  weight: z.number(),
  color: z.string(),
  emphasisColor: z.string(),
  shadowOpacity: z.number(),
  bottomSafePct: z.number(),
  entryRisePx: z.number(),
  entryFrames: z.number(),
  emphasisScale: z.number(),
});

export const SubtitlesSchema = z.object({
  duration: z.number(),
  style: SubtitleStyleSchema,
  cards: z.array(CardSchema),
});

export type SubtitlesProps = z.infer<typeof SubtitlesSchema>;

export const GraphicItemSchema = z.object({
  type: z.enum(["list_item", "number_counter", "entity_chip", "key_line_underline"]),
  start: z.number(),
  end: z.number(),
  score: z.number(),
  text: z.string(),
  anchor_kind: z.string(),
  list_index: z.number().optional(),
});

export const PaletteSchema = z.object({
  amber: z.string(),
  malva: z.string(),
  magenta: z.string(),
  crema: z.string(),
});

export const GraphicsSchema = z.object({
  duration: z.number(),
  palette: PaletteSchema,
  graphics: z.array(GraphicItemSchema),
});

export type GraphicsProps = z.infer<typeof GraphicsSchema>;
