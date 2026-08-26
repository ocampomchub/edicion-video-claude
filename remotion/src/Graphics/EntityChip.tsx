import React from "react";
import { AbsoluteFill, interpolate, Easing } from "remotion";
import type { GraphicItemSchema, PaletteSchema } from "../types";
import type { z } from "zod";

type Props = {
  item: z.infer<typeof GraphicItemSchema>;
  palette: z.infer<typeof PaletteSchema>;
  localT: number;
  duration: number;
};

export const EntityChip: React.FC<Props> = ({ item, palette, localT, duration }) => {
  const enter = interpolate(localT, [0, 0.25], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: Easing.out(Easing.cubic),
  });
  const exit = interpolate(localT, [duration - 0.25, duration], [1, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: Easing.in(Easing.cubic),
  });
  const progress = Math.min(enter, exit);
  const translateX = (1 - enter) * 60 + (1 - exit) * -60;

  return (
    <AbsoluteFill style={{ justifyContent: "flex-start", alignItems: "flex-end" }}>
      <div
        style={{
          marginTop: "18%",
          marginRight: "6%",
          opacity: progress,
          transform: `translateX(${translateX}px)`,
          background: palette.malva,
          color: "#1a1220",
          borderRadius: 999,
          padding: "10px 26px",
          fontSize: 30,
          fontWeight: 700,
        }}
      >
        {item.text}
      </div>
    </AbsoluteFill>
  );
};
