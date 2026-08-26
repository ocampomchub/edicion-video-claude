import React from "react";
import { AbsoluteFill, interpolate, Easing } from "remotion";
import type { GraphicItemSchema, PaletteSchema } from "../types";
import type { z } from "zod";

type Props = {
  item: z.infer<typeof GraphicItemSchema>;
  palette: z.infer<typeof PaletteSchema>;
  localT: number;
};

const COUNT_DURATION = 0.6;

function parseNumber(text: string): number | null {
  const match = text.replace(",", ".").match(/-?\d+(\.\d+)?/);
  if (!match) return null;
  return parseFloat(match[0]);
}

export const NumberCounter: React.FC<Props> = ({ item, palette, localT }) => {
  const target = parseNumber(item.text);
  const enter = interpolate(localT, [0, 0.15], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  let display = item.text;
  if (target !== null) {
    const progress = interpolate(localT, [0, COUNT_DURATION], [0, 1], {
      extrapolateLeft: "clamp",
      extrapolateRight: "clamp",
      easing: Easing.out(Easing.cubic),
    });
    const suffix = item.text.includes("%") ? "%" : "";
    const current = target * progress;
    const rounded = Number.isInteger(target) ? Math.round(current) : Math.round(current * 10) / 10;
    display = `${rounded}${suffix}`;
  }

  return (
    <AbsoluteFill style={{ justifyContent: "flex-start", alignItems: "center" }}>
      <div
        style={{
          marginTop: "14%",
          opacity: enter,
          transform: `scale(${0.85 + 0.15 * enter})`,
          color: palette.magenta,
          fontSize: 96,
          fontWeight: 800,
          textShadow: "0 6px 18px rgba(0,0,0,0.45)",
        }}
      >
        {display}
      </div>
    </AbsoluteFill>
  );
};
