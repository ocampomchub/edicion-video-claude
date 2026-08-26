import React from "react";
import { AbsoluteFill, interpolate, Easing } from "remotion";
import type { GraphicItemSchema, PaletteSchema } from "../types";
import type { z } from "zod";

type Props = {
  item: z.infer<typeof GraphicItemSchema>;
  palette: z.infer<typeof PaletteSchema>;
  localT: number;
};

export const ListCard: React.FC<Props> = ({ item, palette, localT }) => {
  const enter = interpolate(localT, [0, 0.3], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: Easing.out(Easing.cubic),
  });
  const translateX = (1 - enter) * -40;
  const index = (item.list_index ?? 0) + 1;

  return (
    <AbsoluteFill style={{ justifyContent: "flex-start", alignItems: "center" }}>
      <div
        style={{
          marginTop: "16%",
          display: "flex",
          alignItems: "center",
          gap: 16,
          opacity: enter,
          transform: `translateX(${translateX}px)`,
          background: "rgba(20,16,12,0.55)",
          borderRadius: 20,
          padding: "14px 28px",
          maxWidth: "78%",
        }}
      >
        <div
          style={{
            width: 44,
            height: 44,
            borderRadius: "50%",
            background: palette.amber,
            color: "#1a1208",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            fontWeight: 700,
            fontSize: 24,
            flexShrink: 0,
          }}
        >
          {index}
        </div>
        <div style={{ color: palette.crema, fontSize: 34, fontWeight: 600, lineHeight: 1.2 }}>
          {item.text}
        </div>
      </div>
    </AbsoluteFill>
  );
};
