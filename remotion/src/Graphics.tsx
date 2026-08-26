import React from "react";
import { AbsoluteFill, useCurrentFrame, useVideoConfig } from "remotion";
import type { GraphicsProps } from "./types";
import { ListCard } from "./Graphics/ListCard";
import { NumberCounter } from "./Graphics/NumberCounter";
import { EntityChip } from "./Graphics/EntityChip";
import { KeyLineUnderline } from "./Graphics/KeyLineUnderline";

export const Graphics: React.FC<GraphicsProps> = ({ palette, graphics }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const t = frame / fps;

  // Por diseño el scheduler de Python ya garantiza como máximo un gráfico
  // simultáneo; nos quedamos con el de mayor score si algo se solapase.
  const active = graphics
    .filter((g) => t >= g.start && t < g.end)
    .sort((a, b) => b.score - a.score)[0];

  if (!active) {
    return <AbsoluteFill />;
  }

  const localT = t - active.start;
  const duration = active.end - active.start;

  switch (active.type) {
    case "list_item":
      return <ListCard item={active} palette={palette} localT={localT} />;
    case "number_counter":
      return <NumberCounter item={active} palette={palette} localT={localT} />;
    case "entity_chip":
      return <EntityChip item={active} palette={palette} localT={localT} duration={duration} />;
    case "key_line_underline":
      return <KeyLineUnderline item={active} palette={palette} localT={localT} />;
    default:
      return <AbsoluteFill />;
  }
};
