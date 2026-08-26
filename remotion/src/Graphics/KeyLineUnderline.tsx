import React from "react";
import { AbsoluteFill, interpolate, Easing, useVideoConfig } from "remotion";
import type { GraphicItemSchema, PaletteSchema } from "../types";
import type { z } from "zod";

type Props = {
  item: z.infer<typeof GraphicItemSchema>;
  palette: z.infer<typeof PaletteSchema>;
  localT: number;
};

const SUBTITLE_BOTTOM_SAFE_PCT = 0.22;

// La barra se dibuja justo debajo de donde vive la tarjeta de subtítulos.
export const KeyLineUnderline: React.FC<Props> = ({ palette, localT }) => {
  const { height } = useVideoConfig();
  const draw = interpolate(localT, [0, 0.3], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: Easing.out(Easing.cubic),
  });
  const bottom = height * (SUBTITLE_BOTTOM_SAFE_PCT - 0.045);

  return (
    <AbsoluteFill style={{ justifyContent: "flex-end", alignItems: "center" }}>
      <div
        style={{
          position: "absolute",
          bottom,
          height: 6,
          width: `${44 * draw}%`,
          background: palette.amber,
          borderRadius: 3,
          opacity: draw,
        }}
      />
    </AbsoluteFill>
  );
};
